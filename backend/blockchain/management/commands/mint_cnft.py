"""
Django management command to mint compressed NFTs.
"""

import asyncio
import json
from django.core.management.base import BaseCommand, CommandError
from blockchain.services import get_solana_service
from blockchain.merkle_tree import MerkleTreeManager
from blockchain.cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest


class Command(BaseCommand):
    help = 'Mint a compressed NFT to a Merkle tree'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tree-address',
            type=str,
            required=True,
            help='Address of the Merkle tree to mint to',
        )
        parser.add_argument(
            '--recipient',
            type=str,
            help='Recipient address (defaults to tree authority)',
        )
        parser.add_argument(
            '--name',
            type=str,
            help='NFT name (auto-generated for carbon credits)',
        )
        parser.add_argument(
            '--symbol',
            type=str,
            default='CNFT',
            help='NFT symbol (default: CNFT)',
        )
        parser.add_argument(
            '--description',
            type=str,
            help='NFT description (auto-generated for carbon credits)',
        )
        parser.add_argument(
            '--image',
            type=str,
            required=True,
            help='NFT image URL',
        )
        parser.add_argument(
            '--external-url',
            type=str,
            help='External URL for more information',
        )
        parser.add_argument(
            '--carbon-credit',
            action='store_true',
            help='Create carbon credit specific metadata',
        )
        parser.add_argument(
            '--tree-id',
            type=str,
            help='Tree ID for carbon credit (required if --carbon-credit)',
        )
        parser.add_argument(
            '--tree-species',
            type=str,
            help='Tree species for carbon credit (required if --carbon-credit)',
        )
        parser.add_argument(
            '--location',
            type=str,
            help='Location for carbon credit (required if --carbon-credit)',
        )
        parser.add_argument(
            '--planting-date',
            type=str,
            help='Planting date for carbon credit (required if --carbon-credit)',
        )
        parser.add_argument(
            '--carbon-offset',
            type=float,
            help='Carbon offset in tons (required if --carbon-credit)',
        )
        parser.add_argument(
            '--save-result',
            type=str,
            help='Save mint result to specified file',
        )

    def handle(self, *args, **options):
        tree_address = options['tree_address']
        recipient = options['recipient']
        name = options['name']
        symbol = options['symbol']
        description = options['description']
        image = options['image']
        external_url = options['external_url']
        carbon_credit = options['carbon_credit']
        save_result = options['save_result']

        # Validate carbon credit options
        if carbon_credit:
            required_fields = ['tree_id', 'tree_species', 'location', 'planting_date', 'carbon_offset']
            missing_fields = [field for field in required_fields if not options[field.replace('_', '_')]]
            if missing_fields:
                raise CommandError(f"Carbon credit mode requires: {', '.join(missing_fields)}")
        else:
            # For non-carbon credit mode, name and description are required
            if not name:
                raise CommandError("--name is required when not using --carbon-credit")
            if not description:
                raise CommandError("--description is required when not using --carbon-credit")

        # Determine display name for output
        display_name = name if name else f"Carbon Credit Tree #{options['tree_id']}" if carbon_credit else "NFT"

        self.stdout.write(
            self.style.SUCCESS(f'Minting compressed NFT "{display_name}" to tree {tree_address}...')
        )
        
        try:
            # Run the minting
            result = asyncio.run(self._mint_cnft(options))
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS('\n=== Mint Results ===')
            )
            self.stdout.write(f"Mint ID: {result.mint_id}")
            self.stdout.write(f"Tree Address: {result.tree_address}")
            self.stdout.write(f"Recipient: {result.recipient}")
            self.stdout.write(f"Status: {result.status.value}")
            self.stdout.write(f"Signature: {result.signature}")
            self.stdout.write(f"Leaf Index: {result.leaf_index}")
            self.stdout.write(f"Asset ID: {result.asset_id}")
            
            # Save result if requested
            if save_result:
                result_data = result.to_dict()
                with open(save_result, 'w') as f:
                    json.dump(result_data, f, indent=2)
                self.stdout.write(f"Mint result saved to {save_result}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Compressed NFT minted successfully!'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Minting failed: {str(e)}')
            )
            raise CommandError(f"Minting failed: {str(e)}")
    
    async def _mint_cnft(self, options):
        """Mint the compressed NFT asynchronously."""
        # Get Solana service
        service = await get_solana_service()
        if not service.client:
            raise Exception("Solana client not available")
        
        # Create tree manager and minter
        tree_manager = MerkleTreeManager(service.client)

        # Load existing trees from persistent storage
        try:
            tree_manager.load_trees_from_file('managed_trees.json')
        except FileNotFoundError:
            # No existing trees file, that's okay
            pass

        minter = CompressedNFTMinter(tree_manager)
        
        # Determine recipient
        recipient = options['recipient'] or str(tree_manager.authority)
        
        # Create metadata
        if options['carbon_credit']:
            metadata = NFTMetadata.create_carbon_credit_metadata(
                tree_id=options['tree_id'],
                tree_species=options['tree_species'],
                location=options['location'],
                planting_date=options['planting_date'],
                carbon_offset_tons=options['carbon_offset'],
                image_url=options['image'],
                external_url=options['external_url']
            )
        else:
            metadata = NFTMetadata(
                name=options['name'],
                symbol=options['symbol'],
                description=options['description'],
                image=options['image'],
                external_url=options['external_url']
            )
        
        # Create mint request
        mint_request = MintRequest(
            tree_address=options['tree_address'],
            recipient=recipient,
            metadata=metadata
        )
        
        # Perform minting
        result = await minter.mint_compressed_nft(
            mint_request=mint_request,
            confirm_transaction=True
        )
        
        return result
