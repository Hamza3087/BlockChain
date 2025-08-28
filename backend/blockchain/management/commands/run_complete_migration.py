"""
Complete End-to-End Migration Pipeline

This command runs the complete pipeline:
1. Fetch NFT data from Sei blockchain (using CW721 queries)
2. Process and validate the data
3. Create Solana compressed NFTs
4. Store metadata in database
5. Generate individual NFT folders with complete processing info

No hardcoded values - all configuration from environment.
"""

import asyncio
import json
import os
import requests
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from blockchain.models import SeiNFT, MigrationJob, MigrationLog, Tree
from blockchain.clients.solana_client import SolanaClient
from blockchain.migration.data_exporter import DataExporter
from blockchain.migration.migration_mapper import MigrationMapper
from blockchain.migration.migration_validator import MigrationValidator
from blockchain.services.metadata_storage import MetadataStorageService


class SeiDataFetcher:
    """Fetch data directly from Sei blockchain using CW721 queries."""
    
    def __init__(self, contract_address=None, base_url=None):
        self.contract_address = contract_address or os.getenv('SEI_NFT_ADDRESS')
        self.base_url = base_url or os.getenv('SEI_RPC_URL', 'https://rest-testnet.sei-apis.com')
        
        if not self.contract_address:
            raise ValueError("SEI_NFT_ADDRESS environment variable is required")
    
    def query_contract(self, query_json):
        """Query the smart contract"""
        query_b64 = base64.b64encode(json.dumps(query_json).encode()).decode()
        url = f"{self.base_url}/cosmwasm/wasm/v1/contract/{self.contract_address}/smart/{query_b64}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_all_token_ids(self):
        """Get all token IDs using pagination"""
        all_tokens = []
        start_after = None
        
        while True:
            if start_after:
                query = {"all_tokens": {"start_after": start_after, "limit": 100}}
            else:
                query = {"all_tokens": {"limit": 100}}
                
            response = self.query_contract(query)
            
            if 'data' not in response or 'tokens' not in response['data']:
                break
                
            tokens = response['data']['tokens']
            if not tokens:
                break
                
            all_tokens.extend(tokens)
            start_after = tokens[-1]
            
            if len(tokens) < 100:
                break
                
        return all_tokens
    
    def get_token_info(self, token_id):
        """Get complete info for a single token"""
        token_data = {"token_id": token_id}
        
        # Get NFT info (metadata URI)
        nft_info = self.query_contract({"nft_info": {"token_id": token_id}})
        if 'data' in nft_info:
            token_data.update(nft_info['data'])
            
        # Get owner info
        owner_info = self.query_contract({"owner_of": {"token_id": token_id}})
        if 'data' in owner_info:
            token_data['owner'] = owner_info['data']['owner']
            token_data['approvals'] = owner_info['data'].get('approvals', [])
            
        # Get off-chain metadata if token_uri exists
        if 'token_uri' in token_data:
            try:
                metadata_response = requests.get(token_data['token_uri'], timeout=30)
                if metadata_response.status_code == 200:
                    metadata = metadata_response.json()
                    token_data['metadata'] = metadata
                    
                    # Extract attributes into separate fields
                    if 'attributes' in metadata:
                        for attr in metadata['attributes']:
                            key = f"attr_{attr['trait_type'].lower().replace(' ', '_').replace('/', '_')}"
                            token_data[key] = attr['value']
                            
            except Exception as e:
                token_data['metadata_error'] = str(e)
                
        return token_data
    
    def fetch_all_tokens(self, max_workers=10):
        """Fetch all token data with threading"""
        print("🔍 Fetching all token IDs from Sei blockchain...")
        all_tokens = self.get_all_token_ids()
        print(f"📊 Found {len(all_tokens)} tokens")
        
        print("📥 Fetching detailed token data...")
        all_data = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_token = {
                executor.submit(self.get_token_info, token_id): token_id 
                for token_id in all_tokens
            }
            
            for i, future in enumerate(as_completed(future_to_token)):
                token_id = future_to_token[future]
                try:
                    token_data = future.result()
                    all_data.append(token_data)
                    
                    if (i + 1) % 10 == 0:
                        print(f"   Processed {i + 1}/{len(all_tokens)} tokens...")
                        
                except Exception as e:
                    print(f"❌ Error processing token {token_id}: {e}")
                    
        return all_data


class CompleteMigrationPipeline:
    """Complete end-to-end migration pipeline."""
    
    def __init__(self):
        self.sei_fetcher = SeiDataFetcher()
        self.data_exporter = DataExporter()
        self.migration_mapper = MigrationMapper()
        self.migration_validator = MigrationValidator()
        self.metadata_storage = MetadataStorageService()
        self.solana_client = None

        # Create output directory
        self.output_dir = Path("migration_output") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"📁 Output directory: {self.output_dir}")
    
    async def initialize(self):
        """Initialize all components"""
        print("🚀 Initializing migration pipeline...")

        # Initialize Solana client with default endpoints
        from blockchain.config import get_rpc_endpoints
        rpc_endpoints = get_rpc_endpoints()
        self.solana_client = SolanaClient(rpc_endpoints=rpc_endpoints)
        await self.solana_client.connect()

        # Initialize data exporter
        await self.data_exporter.initialize()

        print("✅ Pipeline initialized successfully")
    
    async def process_single_nft(self, token_data, migration_job):
        """Process a single NFT through the complete pipeline"""
        token_id = token_data['token_id']
        
        try:
            # Create NFT folder
            nft_folder = self.output_dir / f"nft_{token_id}"
            nft_folder.mkdir(exist_ok=True)
            
            # Step 1: Save original Sei data
            with open(nft_folder / "01_sei_original_data.json", 'w') as f:
                json.dump(token_data, f, indent=2)
            
            # Step 2: Map to Solana format
            # Add contract address to token data if missing
            if 'contract_address' not in token_data:
                token_data['contract_address'] = self.sei_fetcher.contract_address

            mapped_data = await self.migration_mapper.map_sei_to_solana(token_data)
            with open(nft_folder / "02_solana_mapped_data.json", 'w') as f:
                json.dump(mapped_data, f, indent=2)
            
            # Step 3: Validate data (create SeiNFTData object for validation)
            from blockchain.migration.data_exporter import SeiNFTData
            sei_nft_for_validation = SeiNFTData(
                contract_address=token_data['contract_address'],
                token_id=token_data['token_id'],
                owner_address=token_data.get('owner', ''),
                name=token_data.get('metadata', {}).get('name', ''),
                description=token_data.get('metadata', {}).get('description', ''),
                image_url=token_data.get('metadata', {}).get('image', ''),
                external_url=token_data.get('metadata', {}).get('external_url', ''),
                attributes=token_data.get('metadata', {}).get('attributes', []),
                metadata=token_data.get('metadata', {})
            )

            validation_result = await self.migration_validator.validate_migration_data(sei_nft_for_validation)

            # Convert validation result to dict for JSON serialization
            validation_dict = {
                'is_valid': validation_result.is_valid,
                'errors': validation_result.validation_errors,
                'warnings': validation_result.validation_warnings,
                'validation_timestamp': validation_result.validation_timestamp
            }

            with open(nft_folder / "03_validation_result.json", 'w') as f:
                json.dump(validation_dict, f, indent=2)

            if not validation_result.is_valid:
                raise Exception(f"Validation failed: {validation_result.validation_errors}")
            
            # Step 4: Prepare and store metadata first (so on-chain points to our off-chain JSON)
            print(f"💾 Preparing and storing metadata for token {token_id}...")
            original_metadata = token_data.get('metadata', {})
            solana_metadata = self.metadata_storage.create_solana_metadata(original_metadata, token_id)

            metadata_storage_result = await self.metadata_storage.store_metadata(
                original_metadata=original_metadata,
                solana_metadata=solana_metadata,
                token_id=token_id,
                contract_address=self.sei_fetcher.contract_address
            )

            with open(nft_folder / "04_metadata_storage_result.json", 'w') as f:
                json.dump(metadata_storage_result, f, indent=2)

            # Step 5: Create compressed NFT on Solana, using our off-chain URI
            print(f"🌱 Minting compressed NFT for token {token_id}...")
            mint_metadata = {
                **solana_metadata,
                'uri': metadata_storage_result.get('offchain_uri') or metadata_storage_result.get('solana_uri')
            }
            mint_result = await self.solana_client.mint_compressed_nft(
                metadata=mint_metadata,
                recipient=mapped_data['owner']
            )

            with open(nft_folder / "05_solana_mint_result.json", 'w') as f:
                json.dump(mint_result, f, indent=2)

            # Step 6: Store in database
            @sync_to_async
            def create_database_records():
                with transaction.atomic():
                    # Create SeiNFT record with correct field names and real on-chain data
                    metadata = token_data.get('metadata', {})

                    # Generate data hash for integrity verification
                    import hashlib
                    data_hash = hashlib.sha256(json.dumps(token_data, sort_keys=True).encode()).hexdigest()

                    # Check if NFT already exists and update or create
                    sei_nft, created = SeiNFT.objects.update_or_create(
                        sei_contract_address=self.sei_fetcher.contract_address,
                        sei_token_id=token_data['token_id'],
                        defaults={
                            'sei_owner_address': token_data.get('owner', ''),
                            'name': metadata.get('name', f"Tree #{token_data['token_id']}"),
                            'description': metadata.get('description', ''),
                            'image_url': metadata.get('image', ''),
                            'external_url': metadata.get('external_url', ''),
                            'attributes': metadata.get('attributes', []),
                            'migration_job': migration_job,
                            # Real on-chain Solana data
                            'solana_mint_address': mint_result.get('mint_address') or mint_result.get('asset_id') or '',
                            'solana_asset_id': mint_result.get('asset_id') or mint_result.get('mint_address') or '',
                            'solana_tree_address': mint_result.get('tree_address', ''),
                            'solana_transaction_signature': mint_result.get('transaction_signature', ''),
                            'solana_metadata_uri': metadata_storage_result.get('solana_uri', ''),
                            'is_real_onchain': mint_result.get('status') == 'success' and mint_result.get('type') == 'real_onchain_compressed_nft',
                            'migration_date': datetime.now(),
                            'sei_data_hash': data_hash
                        }
                    )

                    if created:
                        print(f"✅ Created new SeiNFT record for token {token_id}")
                    else:
                        print(f"🔄 Updated existing SeiNFT record for token {token_id}")

                    # Create Tree record if it's a tree NFT
                    tree = None
                    if 'metadata' in token_data and token_data['metadata']:
                        metadata = token_data['metadata']
                        attributes = {attr['trait_type']: attr['value']
                                    for attr in metadata.get('attributes', [])}

                        # Create or get planter user if planter name exists
                        planter_user = None
                        planter_name = attributes.get('planter', '')
                        if planter_name:
                            planter_user, created = User.objects.get_or_create(
                                username=f"planter_{planter_name.lower().replace(' ', '_').replace('-', '_')}",
                                defaults={
                                    'email': f"{planter_name.lower().replace(' ', '').replace('-', '')}@replantworld.io",
                                    'first_name': planter_name.split(' ')[0] if ' ' in planter_name else planter_name,
                                    'last_name': ' '.join(planter_name.split(' ')[1:]) if ' ' in planter_name else ''
                                }
                            )

                        # Parse planting date
                        planting_date = None
                        date_str = attributes.get('Date planted', '')
                        if date_str:
                            try:
                                planting_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    planting_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                                except ValueError:
                                    planting_date = None

                        # Get or create system user as default owner
                        system_user, created = User.objects.get_or_create(
                            username='system_migration',
                            defaults={
                                'email': 'system@replantworld.io',
                                'first_name': 'System',
                                'last_name': 'Migration'
                            }
                        )
                        owner_user = system_user

                        # Use mint_address as unique identifier, or tree_address if mint_address is empty
                        unique_identifier = mint_result.get('mint_address', '') or mint_result.get('tree_address', '') or f"temp_{token_id}"

                        tree, tree_created = Tree.objects.update_or_create(
                            mint_address=unique_identifier,
                            defaults={
                                'merkle_tree_address': mint_result.get('tree_address', ''),
                                'leaf_index': 0,  # Default value, would be set by actual Solana minting
                                'asset_id': mint_result.get('mint_address', '') or unique_identifier,  # Use mint address as asset ID
                                'species': attributes.get('Botanical Name', 'Unknown Species'),
                                'planted_date': planting_date or datetime.now().date(),
                                'location_latitude': float(attributes.get('Latitude', 0)) if attributes.get('Latitude') else 0,
                                'location_longitude': float(attributes.get('Longitude', 0)) if attributes.get('Longitude') else 0,
                                'location_name': attributes.get('Country', 'Unknown Location'),
                                'owner': owner_user,
                                'planter': planter_user,
                                'image_url': metadata.get('image', ''),
                                'notes': f"Migrated from Sei NFT #{token_data['token_id']}. Sponsor: {attributes.get('Sponsor', 'N/A')}. Organization: {attributes.get('Org/Community', 'N/A')}. IUCN Status: {attributes.get('IUCN status', 'N/A')}."
                            }
                        )

                        if tree_created:
                            print(f"✅ Created new Tree record for token {token_id}")
                        else:
                            print(f"🔄 Updated existing Tree record for token {token_id}")

                    return sei_nft, tree

            sei_nft, tree = await create_database_records()
            
            # Step 7: Create verification commands
            verification_script = ""
            if mint_result.get('transaction_signature'):
                # Transaction verification
                verification_script += self.metadata_storage.create_verification_command(
                    mint_result['transaction_signature']
                )
                verification_script += "\n\n"

            if mint_result.get('tree_address'):
                # Tree verification
                tree_address = mint_result['tree_address']
                verification_script += f"""
# Verify Merkle Tree Account
echo "=== Verifying Merkle Tree Account ==="
solana account {tree_address} --url https://api.devnet.solana.com

# Check tree account info via RPC
echo "=== Tree Account Info via RPC ==="
curl -X POST -H "Content-Type: application/json" -d '{{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getAccountInfo",
    "params": [
        "{tree_address}",
        {{
            "encoding": "base64"
        }}
    ]
}}' https://api.devnet.solana.com

# View on Solana Explorer
echo "View Tree on Solana Explorer: https://explorer.solana.com/address/{tree_address}?cluster=devnet"
"""

            if verification_script:
                with open(nft_folder / "06_verification_commands.sh", 'w') as f:
                    f.write(verification_script)

                print(f"✅ Verification commands saved to: {nft_folder / '06_verification_commands.sh'}")

                # Make the script executable
                import os
                os.chmod(nft_folder / "06_verification_commands.sh", 0o755)

            # Step 8: Create summary
            summary = {
                'token_id': token_id,
                'sei_contract': self.sei_fetcher.contract_address,
                'solana_mint': mint_result.get('mint_address'),
                'tree_address': mint_result.get('tree_address'),
                'transaction_signature': mint_result.get('transaction_signature'),
                'is_real_onchain': mint_result.get('status') == 'success' and mint_result.get('type') == 'real_onchain_compressed_nft',
                'metadata_uris': {
                    'solana_uri': metadata_storage_result.get('solana_uri'),
                    'offchain_uri': metadata_storage_result.get('offchain_uri'),
                    'original_uri': metadata_storage_result.get('original_uri')
                },
                'verification_url': mint_result.get('verification_url'),
                'processing_time': datetime.now().isoformat(),
                'status': 'completed',
                'database_records': {
                    'sei_nft_id': sei_nft.id,
                    'tree_id': getattr(tree, 'id', None) if tree else None
                }
            }

            with open(nft_folder / "07_migration_summary.json", 'w') as f:
                json.dump(summary, f, indent=2)
            
            print(f"✅ Successfully processed NFT {token_id}")
            return summary
            
        except Exception as e:
            error_summary = {
                'token_id': token_id,
                'status': 'failed',
                'error': str(e),
                'processing_time': datetime.now().isoformat()
            }
            
            with open(nft_folder / "error_log.json", 'w') as f:
                json.dump(error_summary, f, indent=2)
            
            print(f"❌ Failed to process NFT {token_id}: {e}")
            return error_summary
    
    async def run_complete_pipeline(self, max_nfts=None):
        """Run the complete migration pipeline"""
        print("🌟 Starting Complete NFT Migration Pipeline")
        print("=" * 60)
        
        # Create or get system user
        system_user, created = await sync_to_async(User.objects.get_or_create)(
            username='system_migration',
            defaults={
                'email': 'system@replantworld.io',
                'first_name': 'System',
                'last_name': 'Migration'
            }
        )

        # Create migration job
        migration_job = await sync_to_async(MigrationJob.objects.create)(
            name=f'Migration from {self.sei_fetcher.contract_address}',
            description=f'Complete NFT migration from Sei contract {self.sei_fetcher.contract_address} to Solana',
            sei_contract_addresses=[self.sei_fetcher.contract_address],
            status='running',
            created_by=system_user
        )
        
        try:
            # Step 1: Fetch all NFT data from Sei
            print("\n📡 STEP 1: Fetching NFT data from Sei blockchain")
            all_token_data = self.sei_fetcher.fetch_all_tokens()
            
            if max_nfts:
                all_token_data = all_token_data[:max_nfts]
                print(f"🔢 Limited to {max_nfts} NFTs for testing")
            
            print(f"📊 Total NFTs to process: {len(all_token_data)}")
            
            # Step 2: Process each NFT
            print(f"\n🔄 STEP 2: Processing {len(all_token_data)} NFTs")
            results = []
            
            for i, token_data in enumerate(all_token_data):
                print(f"\n--- Processing NFT {i+1}/{len(all_token_data)} ---")
                result = await self.process_single_nft(token_data, migration_job)
                results.append(result)
                
                # Small delay to avoid overwhelming the networks
                await asyncio.sleep(0.5)
            
            # Step 3: Generate final report
            print(f"\n📋 STEP 3: Generating final report")
            successful = [r for r in results if r['status'] == 'completed']
            failed = [r for r in results if r['status'] == 'failed']
            
            final_report = {
                'migration_job_id': getattr(migration_job, 'id', 'unknown'),
                'total_processed': len(results),
                'successful': len(successful),
                'failed': len(failed),
                'success_rate': len(successful) / len(results) * 100 if results else 0,
                'processing_time': datetime.now().isoformat(),
                'output_directory': str(self.output_dir),
                'successful_nfts': successful,
                'failed_nfts': failed
            }
            
            with open(self.output_dir / "FINAL_MIGRATION_REPORT.json", 'w') as f:
                json.dump(final_report, f, indent=2)
            
            # Update migration job
            await sync_to_async(self._update_migration_job)(
                migration_job, results, successful, failed
            )
            
            print(f"\n🎉 MIGRATION COMPLETE!")
            print(f"✅ Successful: {len(successful)}")
            print(f"❌ Failed: {len(failed)}")
            print(f"📊 Success Rate: {final_report['success_rate']:.1f}%")
            print(f"📁 Output: {self.output_dir}")
            
        except Exception as e:
            await sync_to_async(self._set_job_failed)(migration_job)
            print(f"💥 Pipeline failed: {e}")
            raise
        
        finally:
            await self.cleanup()

    def _update_migration_job(self, migration_job, results, successful, failed):
        """Update migration job with results."""
        migration_job.status = 'completed' if not failed else 'partial'
        migration_job.total_nfts = len(results)
        migration_job.successful_nfts = len(successful)
        migration_job.failed_nfts = len(failed)
        migration_job.save()

    def _set_job_failed(self, migration_job):
        """Set migration job as failed."""
        migration_job.status = 'failed'
        migration_job.save()

    async def cleanup(self):
        """Cleanup resources"""
        if self.solana_client:
            await self.solana_client.close()
        if self.data_exporter:
            await self.data_exporter.close()


class Command(BaseCommand):
    help = 'Run complete end-to-end NFT migration pipeline'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-nfts',
            type=int,
            help='Maximum number of NFTs to process (for testing)'
        )
        parser.add_argument(
            '--contract',
            type=str,
            help='Sei contract address (overrides SEI_NFT_ADDRESS)'
        )

    def handle(self, *args, **options):
        """Execute the complete migration pipeline."""
        self.stdout.write('🚀 COMPLETE NFT MIGRATION PIPELINE')
        self.stdout.write('=' * 60)
        
        # Override contract if provided
        if options.get('contract'):
            os.environ['SEI_NFT_ADDRESS'] = options['contract']
        
        # Run the pipeline
        pipeline = CompleteMigrationPipeline()
        asyncio.run(self._run_pipeline(pipeline, options))

    async def _run_pipeline(self, pipeline, options):
        """Run the async pipeline"""
        await pipeline.initialize()
        await pipeline.run_complete_pipeline(
            max_nfts=options.get('max_nfts')
        )
