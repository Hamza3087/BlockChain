"""
Migration Mapper for Sei to Solana NFT Conversion

This module provides functionality to convert Sei CW721 NFT data
to Solana compressed NFT schema with proper mapping and transformation.
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import structlog

from .data_exporter import SeiNFTData
from ..cnft_minting import NFTMetadata
from ..config import get_migration_config

logger = structlog.get_logger(__name__)


@dataclass
class MigrationMapping:
    """
    Data structure for migration mapping results.
    
    This represents the mapping from Sei NFT data to Solana cNFT format
    with validation and transformation details.
    """
    
    # Source data
    sei_nft_data: SeiNFTData
    
    # Mapped data
    solana_metadata: NFTMetadata
    
    # Mapping details
    mapping_timestamp: float
    mapping_version: str = "1.0"
    
    # Transformation log
    transformations: List[Dict[str, Any]] = None
    warnings: List[str] = None
    
    # Validation results
    is_valid: bool = True
    validation_errors: List[str] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.transformations is None:
            self.transformations = []
        if self.warnings is None:
            self.warnings = []
        if self.validation_errors is None:
            self.validation_errors = []
        if not hasattr(self, 'mapping_timestamp') or self.mapping_timestamp is None:
            self.mapping_timestamp = time.time()
    
    def add_transformation(self, field: str, original_value: Any, 
                          new_value: Any, reason: str):
        """Add a transformation record."""
        self.transformations.append({
            'field': field,
            'original_value': original_value,
            'new_value': new_value,
            'reason': reason,
            'timestamp': time.time()
        })
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def add_validation_error(self, error: str):
        """Add a validation error."""
        self.validation_errors.append(error)
        self.is_valid = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = asdict(self)
        # Convert NFTMetadata to dict
        result['solana_metadata'] = self.solana_metadata.to_dict()
        result['sei_nft_data'] = self.sei_nft_data.to_dict()
        return result


class MigrationMapper:
    """
    Sei to Solana NFT migration mapper.
    
    This class handles the conversion of Sei CW721 NFT data to Solana
    compressed NFT format with proper validation and transformation.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the migration mapper.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or get_migration_config()
        self.logger = logger.bind(component="MigrationMapper")
        
        # Mapping statistics
        self.mapping_stats = {
            'total_mapped': 0,
            'successful_mappings': 0,
            'failed_mappings': 0,
            'warnings_count': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Load mapping rules
        self.mapping_rules = self._load_mapping_rules()
    
    def _load_mapping_rules(self) -> Dict[str, Any]:
        """Load mapping rules from configuration."""
        return self.config.get('mapping_rules', {
            'max_name_length': 32,
            'max_description_length': 200,
            'max_symbol_length': 10,
            'default_symbol': 'TREE',
            'image_url_transformations': {
                'ipfs_gateway': 'https://ipfs.io/ipfs/',
                'supported_formats': ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']
            },
            'attribute_mappings': {
                'trait_type': 'trait_type',
                'value': 'value',
                'display_type': 'display_type'
            },
            'required_fields': ['name', 'image'],
            'carbon_credit_detection': {
                'keywords': ['carbon', 'offset', 'credit', 'tree', 'forest', 'environmental'],
                'attribute_names': ['carbon_offset', 'co2_offset', 'environmental_impact']
            }
        })

    async def map_sei_to_solana(self, sei_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert raw Sei NFT data to Solana compressed NFT format.

        Args:
            sei_data: Raw NFT data from Sei blockchain

        Returns:
            Mapped data ready for Solana compressed NFT minting
        """
        try:
            # Convert raw data to SeiNFTData if needed
            if isinstance(sei_data, dict):
                from .data_exporter import SeiNFTData
                sei_nft_data = SeiNFTData(
                    contract_address=sei_data.get('contract_address', ''),
                    token_id=sei_data.get('token_id', ''),
                    owner_address=sei_data.get('owner', ''),
                    name=sei_data.get('metadata', {}).get('name', ''),
                    description=sei_data.get('metadata', {}).get('description', ''),
                    image_url=sei_data.get('metadata', {}).get('image', ''),
                    external_url=sei_data.get('metadata', {}).get('external_url', ''),
                    attributes=sei_data.get('metadata', {}).get('attributes', []),
                    metadata=sei_data.get('metadata', {})
                )
            else:
                sei_nft_data = sei_data

            # Use existing mapping method
            mapping_result = await self.map_nft_data(sei_nft_data)

            # Convert to the expected format
            metadata_dict = {}
            if mapping_result.solana_metadata:
                if hasattr(mapping_result.solana_metadata, 'to_dict'):
                    metadata_dict = mapping_result.solana_metadata.to_dict()
                else:
                    # If it's already a dict or has dict-like attributes
                    metadata_dict = {
                        'name': getattr(mapping_result.solana_metadata, 'name', ''),
                        'symbol': getattr(mapping_result.solana_metadata, 'symbol', ''),
                        'description': getattr(mapping_result.solana_metadata, 'description', ''),
                        'image': getattr(mapping_result.solana_metadata, 'image', ''),
                        'external_url': getattr(mapping_result.solana_metadata, 'external_url', ''),
                        'attributes': getattr(mapping_result.solana_metadata, 'attributes', [])
                    }

            return {
                'token_id': sei_nft_data.token_id,
                'owner': sei_nft_data.owner_address,
                'metadata': metadata_dict,
                'original_sei_data': {
                    'contract_address': sei_nft_data.contract_address,
                    'token_uri': sei_data.get('token_uri', ''),
                    'migration_timestamp': mapping_result.mapping_timestamp
                }
            }

        except Exception as e:
            self.logger.error(
                "Failed to map Sei to Solana format",
                token_id=sei_data.get('token_id'),
                error=str(e)
            )
            raise

    async def map_nft_data(self, sei_nft_data: SeiNFTData) -> MigrationMapping:
        """
        Map Sei NFT data to Solana compressed NFT format.
        
        Args:
            sei_nft_data: Sei NFT data to map
            
        Returns:
            MigrationMapping instance with mapping results
        """
        start_time = time.time()
        
        try:
            self.logger.info(
                "Starting NFT data mapping",
                contract_address=sei_nft_data.contract_address,
                token_id=sei_nft_data.token_id
            )
            
            # Create mapping instance
            mapping = MigrationMapping(
                sei_nft_data=sei_nft_data,
                solana_metadata=None,  # Will be set below
                mapping_timestamp=start_time
            )
            
            # Perform mapping
            solana_metadata = await self._perform_mapping(sei_nft_data, mapping)
            mapping.solana_metadata = solana_metadata
            
            # Validate mapping
            self._validate_mapping(mapping)
            
            execution_time = (time.time() - start_time) * 1000
            
            if mapping.is_valid:
                self.logger.info(
                    "NFT data mapping successful",
                    contract_address=sei_nft_data.contract_address,
                    token_id=sei_nft_data.token_id,
                    execution_time_ms=execution_time,
                    warnings_count=len(mapping.warnings),
                    transformations_count=len(mapping.transformations)
                )
                self.mapping_stats['successful_mappings'] += 1
            else:
                self.logger.error(
                    "NFT data mapping failed validation",
                    contract_address=sei_nft_data.contract_address,
                    token_id=sei_nft_data.token_id,
                    execution_time_ms=execution_time,
                    validation_errors=mapping.validation_errors
                )
                self.mapping_stats['failed_mappings'] += 1
            
            self.mapping_stats['warnings_count'] += len(mapping.warnings)
            
            return mapping
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            self.logger.error(
                "NFT data mapping failed",
                contract_address=sei_nft_data.contract_address,
                token_id=sei_nft_data.token_id,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            # Create failed mapping
            mapping = MigrationMapping(
                sei_nft_data=sei_nft_data,
                solana_metadata=None,
                mapping_timestamp=start_time,
                is_valid=False
            )
            mapping.add_validation_error(f"Mapping failed: {str(e)}")
            
            self.mapping_stats['failed_mappings'] += 1
            return mapping
        
        finally:
            self.mapping_stats['total_mapped'] += 1
    
    async def _perform_mapping(self, sei_nft_data: SeiNFTData, 
                              mapping: MigrationMapping) -> NFTMetadata:
        """Perform the actual mapping transformation."""
        
        # Map basic metadata
        name = self._map_name(sei_nft_data.name, mapping)
        description = self._map_description(sei_nft_data.description, mapping)
        image_url = self._map_image_url(sei_nft_data.image_url, mapping)
        external_url = self._map_external_url(sei_nft_data.external_url, mapping)
        
        # Map attributes
        attributes = self._map_attributes(sei_nft_data.attributes, mapping)
        
        # Generate symbol
        symbol = self._generate_symbol(sei_nft_data, mapping)
        
        # Detect if this is a carbon credit NFT
        is_carbon_credit = self._detect_carbon_credit(sei_nft_data, mapping)
        
        # Create Solana metadata
        if is_carbon_credit:
            # Use carbon credit template
            solana_metadata = NFTMetadata.create_carbon_credit_metadata(
                tree_id=f"SEI-{sei_nft_data.contract_address[-8:]}-{sei_nft_data.token_id}",
                tree_species=self._extract_tree_species(sei_nft_data, mapping),
                location=self._extract_location(sei_nft_data, mapping),
                planting_date=self._extract_planting_date(sei_nft_data, mapping),
                carbon_offset_tons=self._extract_carbon_offset(sei_nft_data, mapping),
                image_url=image_url,
                external_url=external_url
            )

            # Add additional attributes
            solana_metadata.attributes.extend(attributes)
            
            mapping.add_transformation(
                'template_type', 'generic', 'carbon_credit',
                'Detected carbon credit NFT based on metadata analysis'
            )
        else:
            # Use generic template
            solana_metadata = NFTMetadata(
                name=name,
                symbol=symbol,
                description=description,
                image=image_url,
                external_url=external_url,
                attributes=attributes,
                properties={
                    'category': 'image',
                    'creators': [],
                    'files': [{'uri': image_url, 'type': 'image'}] if image_url else []
                }
            )
        
        # Add migration metadata
        solana_metadata.attributes.append({
            'trait_type': 'Migration Source',
            'value': 'Sei Blockchain'
        })
        
        solana_metadata.attributes.append({
            'trait_type': 'Original Contract',
            'value': sei_nft_data.contract_address
        })
        
        solana_metadata.attributes.append({
            'trait_type': 'Original Token ID',
            'value': sei_nft_data.token_id
        })
        
        return solana_metadata
    
    def _map_name(self, name: str, mapping: MigrationMapping) -> str:
        """Map and validate NFT name."""
        if not name:
            name = f"Migrated NFT #{mapping.sei_nft_data.token_id}"
            mapping.add_transformation(
                'name', '', name, 'Generated name for empty original name'
            )
        
        # Truncate if too long
        max_length = self.mapping_rules['max_name_length']
        if len(name) > max_length:
            original_name = name
            name = name[:max_length].strip()
            mapping.add_transformation(
                'name', original_name, name, f'Truncated to {max_length} characters'
            )
            mapping.add_warning(f"Name truncated from {len(original_name)} to {len(name)} characters")
        
        return name
    
    def _map_description(self, description: str, mapping: MigrationMapping) -> str:
        """Map and validate NFT description."""
        if not description:
            description = "Migrated from Sei blockchain"
            mapping.add_transformation(
                'description', '', description, 'Generated description for empty original'
            )
        
        # Truncate if too long
        max_length = self.mapping_rules['max_description_length']
        if len(description) > max_length:
            original_description = description
            description = description[:max_length].strip() + "..."
            mapping.add_transformation(
                'description', original_description, description, 
                f'Truncated to {max_length} characters'
            )
            mapping.add_warning(f"Description truncated from {len(original_description)} to {len(description)} characters")
        
        return description

    def _map_image_url(self, image_url: str, mapping: MigrationMapping) -> str:
        """Map and validate image URL."""
        if not image_url:
            mapping.add_warning("No image URL provided")
            return ""

        # Transform IPFS URLs
        if image_url.startswith('ipfs://'):
            original_url = image_url
            image_url = image_url.replace('ipfs://', self.mapping_rules['image_url_transformations']['ipfs_gateway'])
            mapping.add_transformation(
                'image_url', original_url, image_url, 'Converted IPFS URL to HTTP gateway'
            )

        return image_url

    def _map_external_url(self, external_url: str, mapping: MigrationMapping) -> str:
        """Map external URL."""
        return external_url or ""

    def _map_attributes(self, attributes: List[Dict[str, Any]],
                       mapping: MigrationMapping) -> List[Dict[str, Any]]:
        """Map NFT attributes."""
        if not attributes:
            return []

        mapped_attributes = []
        attribute_mappings = self.mapping_rules['attribute_mappings']

        for attr in attributes:
            mapped_attr = {}

            # Map known fields
            for original_key, mapped_key in attribute_mappings.items():
                if original_key in attr:
                    mapped_attr[mapped_key] = attr[original_key]

            # Copy unmapped fields
            for key, value in attr.items():
                if key not in attribute_mappings:
                    mapped_attr[key] = value

            # Ensure required fields
            if 'trait_type' not in mapped_attr and 'name' in attr:
                mapped_attr['trait_type'] = attr['name']
                mapping.add_transformation(
                    f'attribute.{attr.get("name", "unknown")}.trait_type',
                    None, attr['name'], 'Mapped name to trait_type'
                )

            if 'value' not in mapped_attr and 'val' in attr:
                mapped_attr['value'] = attr['val']
                mapping.add_transformation(
                    f'attribute.{attr.get("name", "unknown")}.value',
                    None, attr['val'], 'Mapped val to value'
                )

            if mapped_attr:
                mapped_attributes.append(mapped_attr)

        return mapped_attributes

    def _generate_symbol(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> str:
        """Generate symbol for Solana NFT."""
        # Try to extract from metadata
        if 'symbol' in sei_nft_data.metadata:
            symbol = sei_nft_data.metadata['symbol']
        else:
            # Generate from name
            name_words = sei_nft_data.name.upper().split()
            if len(name_words) >= 2:
                symbol = ''.join(word[0] for word in name_words[:3])
            else:
                symbol = self.mapping_rules['default_symbol']

            mapping.add_transformation(
                'symbol', None, symbol, 'Generated symbol from name'
            )

        # Validate length
        max_length = self.mapping_rules['max_symbol_length']
        if len(symbol) > max_length:
            original_symbol = symbol
            symbol = symbol[:max_length]
            mapping.add_transformation(
                'symbol', original_symbol, symbol, f'Truncated to {max_length} characters'
            )

        return symbol

    def _detect_carbon_credit(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> bool:
        """Detect if NFT is a carbon credit based on metadata."""
        detection_rules = self.mapping_rules['carbon_credit_detection']
        keywords = detection_rules['keywords']
        attribute_names = detection_rules['attribute_names']

        # Check name and description
        text_content = f"{sei_nft_data.name} {sei_nft_data.description}".lower()
        for keyword in keywords:
            if keyword in text_content:
                return True

        # Check attributes
        for attr in sei_nft_data.attributes:
            trait_type = attr.get('trait_type', '').lower()
            if trait_type in attribute_names:
                return True

            # Check for carbon-related values
            value = str(attr.get('value', '')).lower()
            for keyword in keywords:
                if keyword in value:
                    return True

        return False

    def _extract_tree_species(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> str:
        """Extract tree species from NFT data."""
        # Look for species in attributes
        for attr in sei_nft_data.attributes:
            trait_type = attr.get('trait_type', '').lower()
            if 'species' in trait_type or 'tree' in trait_type:
                return str(attr.get('value', 'Unknown Species'))

        # Default
        return 'Unknown Species'

    def _extract_location(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> str:
        """Extract location from NFT data."""
        # Look for location in attributes
        for attr in sei_nft_data.attributes:
            trait_type = attr.get('trait_type', '').lower()
            if 'location' in trait_type or 'place' in trait_type or 'region' in trait_type:
                return str(attr.get('value', 'Unknown Location'))

        # Default
        return 'Unknown Location'

    def _extract_planting_date(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> str:
        """Extract planting date from NFT data."""
        # Look for date in attributes
        for attr in sei_nft_data.attributes:
            trait_type = attr.get('trait_type', '').lower()
            if 'date' in trait_type or 'planted' in trait_type:
                return str(attr.get('value', '2023-01-01'))

        # Default
        return '2023-01-01'

    def _extract_carbon_offset(self, sei_nft_data: SeiNFTData, mapping: MigrationMapping) -> float:
        """Extract carbon offset amount from NFT data."""
        # Look for carbon offset in attributes
        for attr in sei_nft_data.attributes:
            trait_type = attr.get('trait_type', '').lower()
            if 'carbon' in trait_type or 'offset' in trait_type or 'co2' in trait_type:
                try:
                    value = attr.get('value', '0')
                    # Extract numeric value
                    import re
                    numbers = re.findall(r'\d+\.?\d*', str(value))
                    if numbers:
                        return float(numbers[0])
                except (ValueError, TypeError):
                    continue

        # Default
        return 1.0

    def _validate_mapping(self, mapping: MigrationMapping):
        """Validate the mapping results."""
        if not mapping.solana_metadata:
            mapping.add_validation_error("No Solana metadata generated")
            return

        # Check required fields
        required_fields = self.mapping_rules['required_fields']
        for field in required_fields:
            if not getattr(mapping.solana_metadata, field, None):
                mapping.add_validation_error(f"Required field '{field}' is missing or empty")

        # Validate name length (should not happen since we truncate during mapping)
        if len(mapping.solana_metadata.name) > self.mapping_rules['max_name_length']:
            # This should not happen since we truncate during mapping, but fix it just in case
            original_name = mapping.solana_metadata.name
            mapping.solana_metadata.name = mapping.solana_metadata.name[:self.mapping_rules['max_name_length']].strip()
            mapping.add_transformation(
                'name', original_name, mapping.solana_metadata.name,
                f'Emergency truncation during validation to {self.mapping_rules["max_name_length"]} characters'
            )
            mapping.add_warning(f"Name was emergency truncated during validation from {len(original_name)} to {len(mapping.solana_metadata.name)} characters")

        # Validate symbol length (should not happen since we set default symbol)
        if len(mapping.solana_metadata.symbol) > self.mapping_rules['max_symbol_length']:
            # This should not happen since we use default symbol, but fix it just in case
            original_symbol = mapping.solana_metadata.symbol
            mapping.solana_metadata.symbol = mapping.solana_metadata.symbol[:self.mapping_rules['max_symbol_length']].strip()
            mapping.add_transformation(
                'symbol', original_symbol, mapping.solana_metadata.symbol,
                f'Emergency truncation during validation to {self.mapping_rules["max_symbol_length"]} characters'
            )
            mapping.add_warning(f"Symbol was emergency truncated during validation from {len(original_symbol)} to {len(mapping.solana_metadata.symbol)} characters")

    def get_mapping_statistics(self) -> Dict[str, Any]:
        """Get mapping statistics."""
        stats = self.mapping_stats.copy()

        if stats['total_mapped'] > 0:
            stats['success_rate'] = (stats['successful_mappings'] / stats['total_mapped']) * 100
            stats['average_warnings_per_mapping'] = stats['warnings_count'] / stats['total_mapped']

        return stats
