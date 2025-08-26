"""
Unit Tests for Migration Classes

Comprehensive tests for Sei to Solana migration functionality including:
- DataExporter functionality
- MigrationMapper transformations
- MigrationValidator validation logic
- MigrationService orchestration
- Error handling and edge cases
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from django.test import TestCase
from django.contrib.auth.models import User

from ..migration import (
    DataExporter, SeiNFTData, MigrationMapper, MigrationMapping,
    MigrationValidator, ValidationResult, MigrationService
)
from ..models import MigrationJob, SeiNFT, MigrationLog


class TestSeiNFTData(TestCase):
    """Test cases for SeiNFTData class."""
    
    def test_sei_nft_data_creation(self):
        """Test SeiNFTData creation and basic properties."""
        nft_data = SeiNFTData(
            contract_address="sei1test123456789",
            token_id="1",
            owner_address="sei1owner123456789",
            name="Test NFT",
            description="A test NFT for unit testing",
            image_url="https://example.com/nft.jpg",
            external_url="https://example.com/nft/1",
            attributes=[
                {"trait_type": "Color", "value": "Blue"},
                {"trait_type": "Rarity", "value": "Common"}
            ]
        )
        
        self.assertEqual(nft_data.contract_address, "sei1test123456789")
        self.assertEqual(nft_data.token_id, "1")
        self.assertEqual(nft_data.name, "Test NFT")
        self.assertEqual(len(nft_data.attributes), 2)
        self.assertIsNotNone(nft_data.data_hash)
    
    def test_sei_nft_data_hash_calculation(self):
        """Test data hash calculation and consistency."""
        nft_data1 = SeiNFTData(
            contract_address="sei1test123",
            token_id="1",
            owner_address="sei1owner123",
            name="Test NFT",
            description="Test description"
        )
        
        nft_data2 = SeiNFTData(
            contract_address="sei1test123",
            token_id="1",
            owner_address="sei1owner123",
            name="Test NFT",
            description="Test description"
        )
        
        # Same data should produce same hash
        self.assertEqual(nft_data1.data_hash, nft_data2.data_hash)
        
        # Different data should produce different hash
        nft_data3 = SeiNFTData(
            contract_address="sei1test123",
            token_id="2",  # Different token ID
            owner_address="sei1owner123",
            name="Test NFT",
            description="Test description"
        )
        
        self.assertNotEqual(nft_data1.data_hash, nft_data3.data_hash)
    
    def test_sei_nft_data_serialization(self):
        """Test serialization and deserialization."""
        original_data = SeiNFTData(
            contract_address="sei1test123",
            token_id="1",
            owner_address="sei1owner123",
            name="Test NFT",
            description="Test description",
            attributes=[{"trait_type": "Test", "value": "Value"}]
        )
        
        # Serialize to dict
        data_dict = original_data.to_dict()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict['contract_address'], "sei1test123")
        
        # Deserialize from dict
        restored_data = SeiNFTData.from_dict(data_dict)
        self.assertEqual(restored_data.contract_address, original_data.contract_address)
        self.assertEqual(restored_data.token_id, original_data.token_id)
        self.assertEqual(restored_data.data_hash, original_data.data_hash)


class TestDataExporter(TestCase):
    """Test cases for DataExporter class."""
    
    @pytest.mark.asyncio
    async def test_data_exporter_initialization(self):
        """Test DataExporter initialization."""
        exporter = DataExporter()
        
        self.assertIsNotNone(exporter.config)
        self.assertIsNone(exporter.session)
        
        # Test initialization
        await exporter.initialize()
        self.assertIsNotNone(exporter.session)
        
        # Cleanup
        await exporter.close()
    
    @pytest.mark.asyncio
    async def test_mock_nft_data_generation(self):
        """Test mock NFT data generation for testing."""
        exporter = DataExporter()
        
        # Generate mock data
        mock_data = exporter._generate_mock_nft_data("sei1test123", "1")
        
        self.assertIsInstance(mock_data, SeiNFTData)
        self.assertEqual(mock_data.contract_address, "sei1test123")
        self.assertEqual(mock_data.token_id, "1")
        self.assertIsNotNone(mock_data.name)
        self.assertIsNotNone(mock_data.description)
        self.assertTrue(len(mock_data.attributes) > 0)
    
    @pytest.mark.asyncio
    async def test_export_collection_data_mock(self):
        """Test export collection data with mock data."""
        exporter = DataExporter()
        await exporter.initialize()
        
        try:
            exported_nfts = []
            async for nft_data in exporter.export_collection_data(
                contract_address="sei1test123",
                max_tokens=5,
                batch_size=2
            ):
                exported_nfts.append(nft_data)
            
            self.assertEqual(len(exported_nfts), 5)
            self.assertTrue(all(isinstance(nft, SeiNFTData) for nft in exported_nfts))
            
        finally:
            await exporter.close()


class TestMigrationMapper(TestCase):
    """Test cases for MigrationMapper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mapper = MigrationMapper()
        
        self.test_nft_data = SeiNFTData(
            contract_address="sei1test123456789",
            token_id="1",
            owner_address="sei1owner123456789",
            name="Test Carbon Credit Tree",
            description="This NFT represents a carbon offset from a tree",
            image_url="ipfs://QmTest123456789",
            external_url="https://replantworld.com/tree/1",
            attributes=[
                {"trait_type": "Species", "value": "Oak"},
                {"trait_type": "Location", "value": "California"},
                {"trait_type": "Carbon Offset", "value": "2.5 tons"},
                {"trait_type": "Planting Date", "value": "2023-01-15"}
            ]
        )
    
    @pytest.mark.asyncio
    async def test_nft_data_mapping(self):
        """Test NFT data mapping functionality."""
        mapping_result = await self.mapper.map_nft_data(self.test_nft_data)
        
        self.assertIsInstance(mapping_result, MigrationMapping)
        self.assertEqual(mapping_result.sei_nft_data, self.test_nft_data)
        self.assertIsNotNone(mapping_result.solana_metadata)
        self.assertIsNotNone(mapping_result.mapping_timestamp)
    
    def test_carbon_credit_detection(self):
        """Test carbon credit NFT detection."""
        # Test with carbon credit keywords
        is_carbon_credit = self.mapper._detect_carbon_credit(self.test_nft_data, Mock())
        self.assertTrue(is_carbon_credit)
        
        # Test with non-carbon credit NFT
        regular_nft_data = SeiNFTData(
            contract_address="sei1test123",
            token_id="1",
            owner_address="sei1owner123",
            name="Regular NFT",
            description="Just a regular NFT",
            attributes=[{"trait_type": "Color", "value": "Blue"}]
        )
        
        is_carbon_credit = self.mapper._detect_carbon_credit(regular_nft_data, Mock())
        self.assertFalse(is_carbon_credit)
    
    def test_name_mapping(self):
        """Test name mapping and validation."""
        mapping = Mock()
        mapping.sei_nft_data = self.test_nft_data
        
        # Test normal name
        mapped_name = self.mapper._map_name("Test NFT", mapping)
        self.assertEqual(mapped_name, "Test NFT")
        
        # Test long name truncation
        long_name = "A" * 50  # Longer than max_name_length (32)
        mapped_name = self.mapper._map_name(long_name, mapping)
        self.assertEqual(len(mapped_name), 32)
        
        # Test empty name
        mapped_name = self.mapper._map_name("", mapping)
        self.assertTrue(mapped_name.startswith("Migrated NFT"))
    
    def test_image_url_transformation(self):
        """Test image URL transformation."""
        mapping = Mock()
        
        # Test IPFS URL transformation
        ipfs_url = "ipfs://QmTest123456789"
        mapped_url = self.mapper._map_image_url(ipfs_url, mapping)
        self.assertTrue(mapped_url.startswith("https://ipfs.io/ipfs/"))
        
        # Test regular HTTP URL
        http_url = "https://example.com/image.jpg"
        mapped_url = self.mapper._map_image_url(http_url, mapping)
        self.assertEqual(mapped_url, http_url)
    
    def test_symbol_generation(self):
        """Test symbol generation."""
        mapping = Mock()
        
        # Test symbol generation from name
        symbol = self.mapper._generate_symbol(self.test_nft_data, mapping)
        self.assertIsInstance(symbol, str)
        self.assertTrue(len(symbol) <= 10)  # Max symbol length
    
    def test_attribute_mapping(self):
        """Test attribute mapping."""
        mapping = Mock()
        
        attributes = [
            {"trait_type": "Color", "value": "Blue"},
            {"name": "Size", "val": "Large"},  # Different format
            {"trait_type": "Rarity", "value": "Common"}
        ]
        
        mapped_attributes = self.mapper._map_attributes(attributes, mapping)
        
        self.assertEqual(len(mapped_attributes), 3)
        self.assertTrue(all('trait_type' in attr for attr in mapped_attributes))
        self.assertTrue(all('value' in attr for attr in mapped_attributes))


class TestMigrationValidator(TestCase):
    """Test cases for MigrationValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = MigrationValidator()
        
        self.test_nft_data = SeiNFTData(
            contract_address="sei1test123456789",
            token_id="1",
            owner_address="sei1owner123456789",
            name="Test NFT",
            description="A test NFT",
            image_url="https://example.com/nft.jpg",
            attributes=[{"trait_type": "Test", "value": "Value"}]
        )
    
    @pytest.mark.asyncio
    async def test_migration_data_validation(self):
        """Test migration data validation."""
        validation_result = await self.validator.validate_migration_data(self.test_nft_data)
        
        self.assertIsInstance(validation_result, ValidationResult)
        self.assertIsNotNone(validation_result.validation_id)
        self.assertIsNotNone(validation_result.validation_timestamp)
        self.assertGreater(validation_result.validation_duration_ms, 0)
    
    @pytest.mark.asyncio
    async def test_data_integrity_validation(self):
        """Test data integrity validation."""
        result = ValidationResult(
            validation_id="test_validation",
            validation_timestamp=datetime.utcnow().timestamp()
        )
        
        # Test with valid data
        await self.validator._validate_data_integrity(self.test_nft_data, result)
        
        # Should have no errors for valid data
        self.assertTrue(result.data_integrity_valid)
    
    @pytest.mark.asyncio
    async def test_metadata_integrity_validation(self):
        """Test metadata integrity validation."""
        result = ValidationResult(
            validation_id="test_validation",
            validation_timestamp=datetime.utcnow().timestamp()
        )
        
        # Test with valid metadata
        await self.validator._validate_metadata_integrity(self.test_nft_data, result)
        
        # Should validate successfully
        self.assertTrue(result.metadata_integrity_valid)
    
    @pytest.mark.asyncio
    async def test_blockchain_integrity_validation(self):
        """Test blockchain integrity validation."""
        result = ValidationResult(
            validation_id="test_validation",
            validation_timestamp=datetime.utcnow().timestamp()
        )
        
        # Test with valid blockchain data
        await self.validator._validate_blockchain_integrity(self.test_nft_data, result)
        
        # Should validate successfully
        self.assertTrue(result.blockchain_integrity_valid)
    
    def test_validation_result_properties(self):
        """Test ValidationResult properties and methods."""
        result = ValidationResult(
            validation_id="test_validation",
            validation_timestamp=datetime.utcnow().timestamp()
        )
        
        # Test adding errors
        result.add_error("Test error")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.validation_errors), 1)
        
        # Test adding warnings
        result.add_warning("Test warning")
        self.assertEqual(len(result.validation_warnings), 1)


class TestMigrationService(TestCase):
    """Test cases for MigrationService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    @pytest.mark.asyncio
    async def test_migration_service_initialization(self):
        """Test MigrationService initialization."""
        service = MigrationService()
        
        # Test initialization
        initialized = await service.initialize()
        
        if initialized:  # Only test if initialization succeeded
            self.assertIsNotNone(service.data_exporter)
            self.assertIsNotNone(service.migration_mapper)
            self.assertIsNotNone(service.migration_validator)
            
            # Cleanup
            await service.close()
    
    @pytest.mark.asyncio
    async def test_create_migration_job(self):
        """Test migration job creation."""
        service = MigrationService()
        
        migration_job = await service.create_migration_job(
            name="Test Migration Job",
            description="Testing migration job creation",
            sei_contract_addresses=["sei1test123", "sei1test456"],
            created_by=self.user,
            batch_size=50
        )
        
        self.assertIsInstance(migration_job, MigrationJob)
        self.assertEqual(migration_job.name, "Test Migration Job")
        self.assertEqual(migration_job.batch_size, 50)
        self.assertEqual(len(migration_job.sei_contract_addresses), 2)
        self.assertEqual(migration_job.created_by, self.user)
    
    def test_service_statistics(self):
        """Test service statistics tracking."""
        service = MigrationService()
        
        stats = service.get_service_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('migrations_started', stats)
        self.assertIn('migrations_completed', stats)
        self.assertIn('migrations_failed', stats)
        self.assertIn('total_nfts_migrated', stats)


class TestMigrationIntegration(TestCase):
    """Integration tests for migration components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    @pytest.mark.asyncio
    async def test_end_to_end_migration_flow(self):
        """Test complete migration flow from export to validation."""
        # Initialize components
        exporter = DataExporter()
        mapper = MigrationMapper()
        validator = MigrationValidator()
        
        await exporter.initialize()
        
        try:
            # Step 1: Export NFT data (mock)
            nft_data = exporter._generate_mock_nft_data("sei1test123", "1")
            
            # Step 2: Map the data
            mapping_result = await mapper.map_nft_data(nft_data)
            
            # Step 3: Validate the mapping
            validation_result = await validator.validate_migration_mapping(mapping_result)
            
            # Verify the flow
            self.assertIsInstance(nft_data, SeiNFTData)
            self.assertIsInstance(mapping_result, MigrationMapping)
            self.assertIsInstance(validation_result, ValidationResult)
            
            # Check that data flows correctly
            self.assertEqual(mapping_result.sei_nft_data, nft_data)
            
        finally:
            await exporter.close()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_migration_flow(self):
        """Test error handling throughout migration flow."""
        mapper = MigrationMapper()
        validator = MigrationValidator()
        
        # Create invalid NFT data
        invalid_nft_data = SeiNFTData(
            contract_address="",  # Invalid empty contract address
            token_id="",  # Invalid empty token ID
            owner_address="",  # Invalid empty owner address
            name="",  # Invalid empty name
            description=""
        )
        
        # Test mapping with invalid data
        mapping_result = await mapper.map_nft_data(invalid_nft_data)
        
        # Test validation with invalid mapping
        validation_result = await validator.validate_migration_mapping(mapping_result)
        
        # Should handle errors gracefully
        self.assertIsInstance(mapping_result, MigrationMapping)
        self.assertIsInstance(validation_result, ValidationResult)
        
        # Validation should fail for invalid data
        self.assertFalse(validation_result.is_valid)
        self.assertTrue(len(validation_result.validation_errors) > 0)


# Mock factories for testing
class MigrationTestFactory:
    """Factory for creating test migration objects."""
    
    @staticmethod
    def create_test_nft_data(contract_address="sei1test123", token_id="1"):
        """Create test SeiNFTData."""
        return SeiNFTData(
            contract_address=contract_address,
            token_id=token_id,
            owner_address="sei1owner123",
            name="Test NFT",
            description="A test NFT for unit testing",
            image_url="https://example.com/nft.jpg",
            attributes=[
                {"trait_type": "Test", "value": "True"},
                {"trait_type": "Environment", "value": "Testing"}
            ]
        )
    
    @staticmethod
    def create_test_migration_job(user, name="Test Migration"):
        """Create test MigrationJob."""
        return MigrationJob.objects.create(
            name=name,
            description="Test migration job",
            sei_contract_addresses=["sei1test123"],
            batch_size=10,
            created_by=user
        )
    
    @staticmethod
    def create_test_sei_nft(migration_job, token_id="1"):
        """Create test SeiNFT."""
        return SeiNFT.objects.create(
            sei_contract_address="sei1test123",
            sei_token_id=token_id,
            sei_owner_address="sei1owner123",
            name=f"Test NFT {token_id}",
            description="Test NFT for unit testing",
            migration_job=migration_job,
            sei_data_hash=f"hash{token_id}"
        )
