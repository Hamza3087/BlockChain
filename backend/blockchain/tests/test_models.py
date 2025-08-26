"""
Unit Tests for Database Models

Comprehensive tests for all blockchain database models including:
- Model creation and validation
- Relationships and constraints
- Custom methods and properties
- Data integrity and consistency
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from ..models import (
    Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData,
    SeiNFT, MigrationJob, MigrationLog,
    IntegrationTestResult, BatchMigrationStatus, PerformanceMetric
)


class TestTreeModel(TestCase):
    """Test cases for Tree model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_tree_creation(self):
        """Test basic tree creation."""
        tree = Tree.objects.create(
            mint_address='test_mint_123',
            merkle_tree_address='test_merkle_123',
            leaf_index=1,
            asset_id='test_asset_123',
            species='Oak',
            planted_date=date.today(),
            location_latitude=Decimal('37.7749'),
            location_longitude=Decimal('-122.4194'),
            location_name='San Francisco',
            status='growing',
            estimated_carbon_kg=Decimal('10.5'),
            owner=self.user,
            planter=self.user
        )
        
        self.assertEqual(tree.species, 'Oak')
        self.assertEqual(tree.status, 'growing')
        self.assertEqual(tree.owner, self.user)
        self.assertEqual(tree.planter, self.user)
        self.assertIsNotNone(tree.tree_id)
    
    def test_tree_str_representation(self):
        """Test tree string representation."""
        tree = Tree.objects.create(
            mint_address='test_mint_123',
            species='Pine',
            planted_date=date.today(),
            location_latitude=Decimal('0.0'),
            location_longitude=Decimal('0.0'),
            owner=self.user,
            planter=self.user
        )
        
        expected_str = f"Pine tree {tree.tree_id} - growing"
        self.assertEqual(str(tree), expected_str)
    
    def test_tree_age_calculation(self):
        """Test tree age calculation."""
        past_date = date.today() - timedelta(days=365)
        tree = Tree.objects.create(
            mint_address='test_mint_123',
            species='Maple',
            planted_date=past_date,
            location_latitude=Decimal('0.0'),
            location_longitude=Decimal('0.0'),
            owner=self.user,
            planter=self.user
        )
        
        age = tree.age_in_days
        self.assertGreaterEqual(age, 365)
    
    def test_tree_unique_constraints(self):
        """Test unique constraints on tree fields."""
        Tree.objects.create(
            mint_address='unique_mint_123',
            species='Oak',
            planted_date=date.today(),
            location_latitude=Decimal('0.0'),
            location_longitude=Decimal('0.0'),
            owner=self.user,
            planter=self.user
        )
        
        # Should raise IntegrityError for duplicate mint_address
        with self.assertRaises(IntegrityError):
            Tree.objects.create(
                mint_address='unique_mint_123',  # Duplicate
                species='Pine',
                planted_date=date.today(),
                location_latitude=Decimal('0.0'),
                location_longitude=Decimal('0.0'),
                owner=self.user,
                planter=self.user
            )


class TestSpeciesGrowthParametersModel(TestCase):
    """Test cases for SpeciesGrowthParameters model."""
    
    def test_species_parameters_creation(self):
        """Test species parameters creation."""
        params = SpeciesGrowthParameters.objects.create(
            species='Oak',
            growth_rate_cm_per_year=Decimal('25.5'),
            max_height_cm=Decimal('3000.0'),
            carbon_absorption_kg_per_year=Decimal('22.0'),
            optimal_temperature_min=Decimal('15.0'),
            optimal_temperature_max=Decimal('25.0'),
            optimal_rainfall_mm_per_year=Decimal('800.0')
        )
        
        self.assertEqual(params.species, 'Oak')
        self.assertEqual(params.growth_rate_cm_per_year, Decimal('25.5'))
        self.assertEqual(params.max_height_cm, Decimal('3000.0'))
    
    def test_species_unique_constraint(self):
        """Test unique constraint on species name."""
        SpeciesGrowthParameters.objects.create(
            species='Pine',
            growth_rate_cm_per_year=Decimal('20.0'),
            max_height_cm=Decimal('2500.0'),
            carbon_absorption_kg_per_year=Decimal('18.0')
        )
        
        # Should raise IntegrityError for duplicate species
        with self.assertRaises(IntegrityError):
            SpeciesGrowthParameters.objects.create(
                species='Pine',  # Duplicate
                growth_rate_cm_per_year=Decimal('25.0'),
                max_height_cm=Decimal('3000.0'),
                carbon_absorption_kg_per_year=Decimal('20.0')
            )


class TestCarbonMarketPriceModel(TestCase):
    """Test cases for CarbonMarketPrice model."""
    
    def test_carbon_price_creation(self):
        """Test carbon market price creation."""
        price = CarbonMarketPrice.objects.create(
            market='VCS',
            price_per_ton_usd=Decimal('15.50'),
            currency='USD',
            date=date.today()
        )
        
        self.assertEqual(price.market, 'VCS')
        self.assertEqual(price.price_per_ton_usd, Decimal('15.50'))
        self.assertEqual(price.currency, 'USD')
    
    def test_get_latest_price(self):
        """Test get_latest_price class method."""
        # Create multiple prices
        old_price = CarbonMarketPrice.objects.create(
            market='VCS',
            price_per_ton_usd=Decimal('10.00'),
            date=date.today() - timedelta(days=1)
        )
        
        latest_price = CarbonMarketPrice.objects.create(
            market='VCS',
            price_per_ton_usd=Decimal('15.00'),
            date=date.today()
        )
        
        # Should return the latest price
        result = CarbonMarketPrice.get_latest_price('VCS')
        self.assertEqual(result, latest_price)
        self.assertEqual(result.price_per_ton_usd, Decimal('15.00'))


class TestSeiNFTModel(TestCase):
    """Test cases for SeiNFT model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.migration_job = MigrationJob.objects.create(
            name='Test Migration',
            description='Test migration job',
            sei_contract_addresses=['sei1test123'],
            created_by=self.user
        )
    
    def test_sei_nft_creation(self):
        """Test SeiNFT creation."""
        nft = SeiNFT.objects.create(
            sei_contract_address='sei1test123456',
            sei_token_id='1',
            sei_owner_address='sei1owner123',
            name='Test NFT',
            description='A test NFT',
            image_url='https://example.com/nft.jpg',
            attributes=[{'trait_type': 'Color', 'value': 'Blue'}],
            migration_job=self.migration_job,
            sei_data_hash='hash123'
        )
        
        self.assertEqual(nft.name, 'Test NFT')
        self.assertEqual(nft.migration_status, 'pending')
        self.assertEqual(nft.migration_job, self.migration_job)
    
    def test_sei_nft_unique_constraint(self):
        """Test unique constraint on contract address and token ID."""
        SeiNFT.objects.create(
            sei_contract_address='sei1unique123',
            sei_token_id='1',
            sei_owner_address='sei1owner123',
            name='NFT 1',
            migration_job=self.migration_job,
            sei_data_hash='hash1'
        )
        
        # Should raise IntegrityError for duplicate contract+token_id
        with self.assertRaises(IntegrityError):
            SeiNFT.objects.create(
                sei_contract_address='sei1unique123',  # Same contract
                sei_token_id='1',  # Same token ID
                sei_owner_address='sei1owner456',
                name='NFT 2',
                migration_job=self.migration_job,
                sei_data_hash='hash2'
            )


class TestMigrationJobModel(TestCase):
    """Test cases for MigrationJob model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_migration_job_creation(self):
        """Test MigrationJob creation."""
        job = MigrationJob.objects.create(
            name='Test Migration Job',
            description='Testing migration functionality',
            sei_contract_addresses=['sei1test123', 'sei1test456'],
            batch_size=100,
            created_by=self.user
        )
        
        self.assertEqual(job.name, 'Test Migration Job')
        self.assertEqual(job.status, 'created')
        self.assertEqual(job.batch_size, 100)
        self.assertEqual(len(job.sei_contract_addresses), 2)
        self.assertIsNotNone(job.job_id)
    
    def test_migration_job_progress_percentage(self):
        """Test progress percentage calculation."""
        job = MigrationJob.objects.create(
            name='Progress Test',
            description='Testing progress calculation',
            sei_contract_addresses=['sei1test123'],
            total_nfts=100,
            processed_nfts=25,
            created_by=self.user
        )
        
        self.assertEqual(job.progress_percentage, 25.0)
    
    def test_migration_job_success_rate(self):
        """Test success rate calculation."""
        job = MigrationJob.objects.create(
            name='Success Rate Test',
            description='Testing success rate calculation',
            sei_contract_addresses=['sei1test123'],
            processed_nfts=100,
            successful_migrations=80,
            created_by=self.user
        )
        
        self.assertEqual(job.success_rate, 80.0)
    
    def test_migration_job_duration(self):
        """Test duration calculation."""
        start_time = timezone.now() - timedelta(hours=2)
        end_time = timezone.now()
        
        job = MigrationJob.objects.create(
            name='Duration Test',
            description='Testing duration calculation',
            sei_contract_addresses=['sei1test123'],
            started_at=start_time,
            completed_at=end_time,
            created_by=self.user
        )
        
        duration = job.duration
        self.assertIsNotNone(duration)
        self.assertGreaterEqual(duration.total_seconds(), 7000)  # ~2 hours


class TestIntegrationTestResultModel(TestCase):
    """Test cases for IntegrationTestResult model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_integration_test_result_creation(self):
        """Test IntegrationTestResult creation."""
        test_result = IntegrationTestResult.objects.create(
            scenario='single_nft_migration',
            status='passed',
            test_data_size=10,
            start_time=timezone.now(),
            end_time=timezone.now(),
            duration_seconds=30.5,
            success_rate=95.0,
            total_nfts_processed=10,
            successful_nfts=9,
            failed_nfts=1,
            executed_by=self.user
        )
        
        self.assertEqual(test_result.scenario, 'single_nft_migration')
        self.assertEqual(test_result.status, 'passed')
        self.assertTrue(test_result.passed)
        self.assertTrue(test_result.is_completed)
    
    def test_integration_test_result_properties(self):
        """Test IntegrationTestResult properties."""
        test_result = IntegrationTestResult.objects.create(
            scenario='batch_migration',
            status='running',
            test_data_size=50,
            start_time=timezone.now(),
            executed_by=self.user
        )
        
        self.assertFalse(test_result.passed)
        self.assertFalse(test_result.is_completed)


class TestBatchMigrationStatusModel(TestCase):
    """Test cases for BatchMigrationStatus model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.migration_job = MigrationJob.objects.create(
            name='Test Migration',
            description='Test migration job',
            sei_contract_addresses=['sei1test123'],
            created_by=self.user
        )
    
    def test_batch_migration_status_creation(self):
        """Test BatchMigrationStatus creation."""
        batch_status = BatchMigrationStatus.objects.create(
            migration_job=self.migration_job,
            batch_size=50,
            batch_index=0,
            total_items=50,
            processed_items=25,
            successful_items=20,
            failed_items=5,
            start_time=timezone.now()
        )
        
        self.assertEqual(batch_status.migration_job, self.migration_job)
        self.assertEqual(batch_status.batch_size, 50)
        self.assertEqual(batch_status.progress_percentage, 50.0)
        self.assertEqual(batch_status.success_rate, 80.0)
    
    def test_batch_migration_status_duration(self):
        """Test duration calculation."""
        start_time = timezone.now() - timedelta(minutes=30)
        end_time = timezone.now()
        
        batch_status = BatchMigrationStatus.objects.create(
            migration_job=self.migration_job,
            batch_size=25,
            batch_index=0,
            total_items=25,
            start_time=start_time,
            end_time=end_time
        )
        
        duration = batch_status.duration
        self.assertIsNotNone(duration)
        self.assertGreaterEqual(duration.total_seconds(), 1700)  # ~30 minutes


class TestPerformanceMetricModel(TestCase):
    """Test cases for PerformanceMetric model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.integration_test = IntegrationTestResult.objects.create(
            scenario='performance_benchmark',
            status='running',
            test_data_size=100,
            start_time=timezone.now(),
            executed_by=self.user
        )
    
    def test_performance_metric_creation(self):
        """Test PerformanceMetric creation."""
        metric = PerformanceMetric.objects.create(
            name='cpu_usage',
            category='system',
            value=75.5,
            unit='percent',
            context={'host': 'test-server'},
            integration_test=self.integration_test
        )
        
        self.assertEqual(metric.name, 'cpu_usage')
        self.assertEqual(metric.category, 'system')
        self.assertEqual(metric.value, 75.5)
        self.assertEqual(metric.unit, 'percent')
        self.assertEqual(metric.integration_test, self.integration_test)
    
    def test_performance_metric_str_representation(self):
        """Test PerformanceMetric string representation."""
        metric = PerformanceMetric.objects.create(
            name='memory_usage',
            value=512.0,
            unit='MB'
        )
        
        expected_str = f"memory_usage: 512.0 MB ({metric.timestamp})"
        self.assertEqual(str(metric), expected_str)


class TestModelRelationships(TestCase):
    """Test model relationships and foreign keys."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.migration_job = MigrationJob.objects.create(
            name='Relationship Test',
            description='Testing model relationships',
            sei_contract_addresses=['sei1test123'],
            created_by=self.user
        )
    
    def test_migration_job_sei_nfts_relationship(self):
        """Test MigrationJob to SeiNFT relationship."""
        # Create NFTs associated with the job
        nft1 = SeiNFT.objects.create(
            sei_contract_address='sei1test123',
            sei_token_id='1',
            sei_owner_address='sei1owner123',
            name='NFT 1',
            migration_job=self.migration_job,
            sei_data_hash='hash1'
        )
        
        nft2 = SeiNFT.objects.create(
            sei_contract_address='sei1test123',
            sei_token_id='2',
            sei_owner_address='sei1owner123',
            name='NFT 2',
            migration_job=self.migration_job,
            sei_data_hash='hash2'
        )
        
        # Test reverse relationship
        related_nfts = self.migration_job.sei_nfts.all()
        self.assertEqual(related_nfts.count(), 2)
        self.assertIn(nft1, related_nfts)
        self.assertIn(nft2, related_nfts)
    
    def test_migration_job_logs_relationship(self):
        """Test MigrationJob to MigrationLog relationship."""
        # Create logs for the job
        log1 = MigrationLog.objects.create(
            migration_job=self.migration_job,
            level='info',
            event_type='job_started',
            message='Job started'
        )
        
        log2 = MigrationLog.objects.create(
            migration_job=self.migration_job,
            level='info',
            event_type='job_completed',
            message='Job completed'
        )
        
        # Test reverse relationship
        related_logs = self.migration_job.logs.all()
        self.assertEqual(related_logs.count(), 2)
        self.assertIn(log1, related_logs)
        self.assertIn(log2, related_logs)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior."""
        # Create related objects
        nft = SeiNFT.objects.create(
            sei_contract_address='sei1test123',
            sei_token_id='1',
            sei_owner_address='sei1owner123',
            name='Test NFT',
            migration_job=self.migration_job,
            sei_data_hash='hash1'
        )
        
        log = MigrationLog.objects.create(
            migration_job=self.migration_job,
            level='info',
            event_type='test',
            message='Test log'
        )
        
        # Delete the migration job
        job_id = self.migration_job.job_id
        self.migration_job.delete()
        
        # Related objects should be deleted
        self.assertFalse(SeiNFT.objects.filter(migration_job__job_id=job_id).exists())
        self.assertFalse(MigrationLog.objects.filter(migration_job__job_id=job_id).exists())
