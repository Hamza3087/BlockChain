"""
Django management command to integrate blockchain operations with Day 4 database models.

This command demonstrates the integration between:
- Solana blockchain operations (Days 1-3)
- Database models (Day 4)

Usage: python manage.py integrate_blockchain_db
"""

import asyncio
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async
from blockchain.models import (
    Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData
)
from blockchain.services import get_solana_service
from blockchain.merkle_tree import MerkleTreeManager, MerkleTreeConfig
from blockchain.cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest


class Command(BaseCommand):
    help = 'Demonstrate integration between blockchain operations and database models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample-data',
            action='store_true',
            help='Create sample species and market data',
        )
        parser.add_argument(
            '--mint-and-store',
            action='store_true',
            help='Mint NFT and store tree data in database',
        )
        parser.add_argument(
            '--update-carbon-data',
            action='store_true',
            help='Update carbon measurements for existing trees',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔗 Starting Blockchain-Database Integration Demo')
        )
        self.stdout.write('=' * 70)
        
        try:
            if options['create_sample_data']:
                self.create_sample_data()
            
            if options['mint_and_store']:
                asyncio.run(self.mint_and_store_tree())
            
            if options['update_carbon_data']:
                self.update_carbon_measurements()
            
            if not any([options['create_sample_data'], options['mint_and_store'], options['update_carbon_data']]):
                # Run all operations by default
                self.create_sample_data()
                asyncio.run(self.mint_and_store_tree())
                self.update_carbon_measurements()
            
            self.stdout.write('=' * 70)
            self.stdout.write(
                self.style.SUCCESS('✅ Blockchain-Database Integration Complete!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Integration failed: {e}')
            )
            raise

    def create_sample_data(self):
        """Create sample species growth parameters and market prices."""
        self.stdout.write('\n📊 Creating Sample Data...')
        
        # Create species growth parameters
        species_data = [
            {
                'species': 'Quercus robur',
                'region': 'Northern Europe',
                'height_asymptote_cm': Decimal('3500.00'),
                'height_growth_rate': Decimal('0.025000'),
                'height_shape_parameter': Decimal('1.2000'),
                'diameter_asymptote_cm': Decimal('120.00'),
                'diameter_growth_rate': Decimal('0.020000'),
                'diameter_shape_parameter': Decimal('1.1000'),
                'biomass_asymptote_kg': Decimal('8500.000'),
                'biomass_growth_rate': Decimal('0.018000'),
                'biomass_shape_parameter': Decimal('1.3000'),
                'data_source': 'European Forest Research Institute',
                'study_year': 2020,
                'sample_size': 150,
                'r_squared': Decimal('0.8750')
            },
            {
                'species': 'Pinus sylvestris',
                'region': 'Scandinavia',
                'height_asymptote_cm': Decimal('2800.00'),
                'height_growth_rate': Decimal('0.030000'),
                'height_shape_parameter': Decimal('1.1000'),
                'diameter_asymptote_cm': Decimal('80.00'),
                'diameter_growth_rate': Decimal('0.025000'),
                'diameter_shape_parameter': Decimal('1.0000'),
                'biomass_asymptote_kg': Decimal('5500.000'),
                'biomass_growth_rate': Decimal('0.022000'),
                'biomass_shape_parameter': Decimal('1.2000'),
                'data_source': 'Nordic Forest Research',
                'study_year': 2019,
                'sample_size': 200,
                'r_squared': Decimal('0.9100')
            }
        ]
        
        for data in species_data:
            params, created = SpeciesGrowthParameters.objects.get_or_create(
                species=data['species'],
                region=data['region'],
                defaults=data
            )
            if created:
                self.stdout.write(f'  ✅ Created growth parameters for {params.species}')
            else:
                self.stdout.write(f'  ℹ️  Growth parameters already exist for {params.species}')
        
        # Create carbon market prices
        market_data = [
            {
                'market_name': 'California Cap-and-Trade',
                'market_type': 'compliance',
                'price_date': date.today(),
                'price_usd_per_ton': Decimal('28.50'),
                'data_source': 'California Air Resources Board',
                'data_quality': 'high'
            },
            {
                'market_name': 'EU ETS',
                'market_type': 'compliance',
                'price_date': date.today(),
                'price_usd_per_ton': Decimal('85.20'),
                'data_source': 'European Energy Exchange',
                'data_quality': 'high'
            },
            {
                'market_name': 'Voluntary Carbon Market',
                'market_type': 'voluntary',
                'price_date': date.today(),
                'price_usd_per_ton': Decimal('15.75'),
                'data_source': 'Ecosystem Marketplace',
                'data_quality': 'medium'
            }
        ]
        
        for data in market_data:
            price, created = CarbonMarketPrice.objects.get_or_create(
                market_name=data['market_name'],
                price_date=data['price_date'],
                credit_type='forestry',
                defaults=data
            )
            if created:
                self.stdout.write(f'  ✅ Created market price for {price.market_name}')
            else:
                self.stdout.write(f'  ℹ️  Market price already exists for {price.market_name}')

    async def mint_and_store_tree(self):
        """Mint a compressed NFT and store corresponding tree data in database."""
        self.stdout.write('\n🌳 Minting NFT and Storing Tree Data...')

        # Get or create test user (using sync_to_async)
        @sync_to_async
        def get_or_create_user():
            user, created = User.objects.get_or_create(
                username='tree_owner',
                defaults={
                    'email': 'owner@replantworld.com',
                    'first_name': 'Tree',
                    'last_name': 'Owner'
                }
            )
            if created:
                user.set_password('secure_password_123')
                user.save()
            return user, created

        user, created = await get_or_create_user()
        if created:
            self.stdout.write('  ✅ Created test user')

        # Initialize blockchain services
        service = await get_solana_service()
        tree_manager = MerkleTreeManager(service.client)
        
        # Load existing trees or create new one
        try:
            tree_manager.load_trees_from_file('managed_trees.json')
        except FileNotFoundError:
            pass
        
        # Get or create a Merkle tree
        trees = await tree_manager.list_trees()
        if trees:
            merkle_tree = trees[0]
            self.stdout.write(f'  ✅ Using existing Merkle tree: {merkle_tree.tree_address}')
        else:
            config = tree_manager.create_tree_config(max_depth=10)
            merkle_tree = await tree_manager.create_merkle_tree(config, 'Integration Test Tree')
            tree_manager.save_trees_to_file('managed_trees.json')
            self.stdout.write(f'  ✅ Created new Merkle tree: {merkle_tree.tree_address}')
        
        # Create NFT metadata with carbon credit information
        metadata = NFTMetadata.create_carbon_credit_metadata(
            tree_id='INT-001',
            tree_species='Quercus robur',
            location='San Francisco, CA',
            planting_date='2023-01-15',
            carbon_offset_tons=2.5,
            image_url='https://example.com/oak-tree.jpg'
        )
        
        # Mint compressed NFT
        minter = CompressedNFTMinter(tree_manager)
        mint_request = MintRequest(
            tree_address=merkle_tree.tree_address,
            recipient=str(tree_manager.authority),
            metadata=metadata
        )
        
        mint_result = await minter.mint_compressed_nft(mint_request, confirm_transaction=True)
        self.stdout.write(f'  ✅ Minted NFT: {mint_result.asset_id}')
        
        # Store tree data in database (using sync_to_async)
        @sync_to_async
        def create_tree_and_carbon_data():
            # Check if tree already exists
            existing_tree = Tree.objects.filter(mint_address=mint_result.asset_id).first()

            if existing_tree:
                tree = existing_tree
                tree_action = "Found existing"
            else:
                tree = Tree.objects.create(
                    mint_address=mint_result.asset_id,
                    merkle_tree_address=merkle_tree.tree_address,
                    leaf_index=mint_result.leaf_index,
                    asset_id=mint_result.asset_id,
                    species='Quercus robur',
                    planted_date=date(2023, 1, 15),
                    location_latitude=Decimal('37.7749'),
                    location_longitude=Decimal('-122.4194'),
                    location_name='San Francisco, CA',
                    status='growing',
                    height_cm=180,
                    diameter_cm=Decimal('12.50'),
                    estimated_carbon_kg=Decimal('85.500'),
                    owner=user,
                    planter=user,
                    notes='Tree created through blockchain-database integration',
                    image_url='https://example.com/oak-tree.jpg',
                    verification_status='verified'
                )
                tree_action = "Created"

            # Get growth parameters and predict carbon
            growth_params = tree.get_growth_parameters()
            predicted_carbon = None
            if growth_params:
                predicted_carbon = growth_params.predict_carbon(tree.age_days)

            # Create initial carbon measurement (check for existing first)
            existing_carbon = TreeCarbonData.objects.filter(
                tree=tree,
                measurement_date=date.today(),
                measurement_method='model_prediction'
            ).first()

            if existing_carbon:
                carbon_data = existing_carbon
                carbon_action = "Found existing"
            else:
                carbon_data = TreeCarbonData.objects.create(
                    tree=tree,
                    measurement_date=date.today(),
                    measurement_method='model_prediction',
                    above_ground_carbon_kg=Decimal('70.000'),
                    below_ground_carbon_kg=Decimal('15.500'),
                    total_carbon_kg=Decimal('85.500'),
                    tree_height_cm=180,
                    tree_diameter_cm=Decimal('12.50'),
                    data_quality='medium',
                    verification_status='pending',
                    market_price_usd_per_ton=Decimal('28.50'),
                    data_source='Chapman-Richards model prediction',
                    measured_by=user
                )
                carbon_action = "Created"

            return tree, carbon_data, predicted_carbon, tree_action, carbon_action

        tree, carbon_data, predicted_carbon, tree_action, carbon_action = await create_tree_and_carbon_data()

        self.stdout.write(f'  ✅ {tree_action} tree in database: {tree.tree_id}')

        if predicted_carbon:
            self.stdout.write(f'  📊 Predicted carbon: {predicted_carbon:.3f} kg')

        self.stdout.write(f'  ✅ {carbon_action} carbon measurement: {carbon_data.total_carbon_kg} kg')
        self.stdout.write(f'  💰 Carbon credit value: ${carbon_data.carbon_credit_value_usd}')
        
        return tree

    def update_carbon_measurements(self):
        """Update carbon measurements for existing trees."""
        self.stdout.write('\n📈 Updating Carbon Measurements...')

        # Use sync database operations since this is not an async method
        trees = Tree.objects.filter(status__in=['growing', 'mature'])

        for tree in trees:
            # Get growth parameters
            growth_params = tree.get_growth_parameters()
            if not growth_params:
                continue

            # Calculate predicted values
            predicted_carbon = growth_params.predict_carbon(tree.age_days)
            predicted_height = growth_params.predict_height(tree.age_days)
            predicted_diameter = growth_params.predict_diameter(tree.age_days)

            # Update tree estimates
            tree.estimated_carbon_kg = Decimal(str(predicted_carbon))
            tree.height_cm = int(predicted_height)
            tree.diameter_cm = Decimal(str(predicted_diameter))
            tree.save()

            # Create new carbon measurement (check for existing first)
            latest_price = CarbonMarketPrice.get_latest_price(credit_type='forestry')
            market_price = latest_price.price_usd_per_ton if latest_price else Decimal('25.00')

            # Check if measurement already exists for today
            existing_measurement = TreeCarbonData.objects.filter(
                tree=tree,
                measurement_date=date.today(),
                measurement_method='model_prediction'
            ).first()

            if existing_measurement:
                # Update existing measurement
                existing_measurement.above_ground_carbon_kg = Decimal(str(predicted_carbon * 0.8))
                existing_measurement.below_ground_carbon_kg = Decimal(str(predicted_carbon * 0.2))
                existing_measurement.total_carbon_kg = Decimal(str(predicted_carbon))
                existing_measurement.tree_height_cm = int(predicted_height)
                existing_measurement.tree_diameter_cm = Decimal(str(predicted_diameter))
                existing_measurement.market_price_usd_per_ton = market_price
                existing_measurement.save()
                carbon_data = existing_measurement
                action = "Updated"
            else:
                # Create new measurement
                carbon_data = TreeCarbonData.objects.create(
                    tree=tree,
                    measurement_date=date.today(),
                    measurement_method='model_prediction',
                    above_ground_carbon_kg=Decimal(str(predicted_carbon * 0.8)),
                    below_ground_carbon_kg=Decimal(str(predicted_carbon * 0.2)),
                    total_carbon_kg=Decimal(str(predicted_carbon)),
                    tree_height_cm=int(predicted_height),
                    tree_diameter_cm=Decimal(str(predicted_diameter)),
                    data_quality='medium',
                    verification_status='pending',
                    market_price_usd_per_ton=market_price,
                    data_source='Automated Chapman-Richards prediction'
                )
                action = "Created"

            self.stdout.write(
                f'  ✅ {action} {tree.species} - Carbon: {carbon_data.total_carbon_kg} kg, '
                f'Value: ${carbon_data.carbon_credit_value_usd}'
            )
