"""
Blockchain models for ReplantWorld.

This module contains Django models for managing trees, carbon data,
market prices, and species growth parameters integrated with Solana blockchain.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when the record was last updated"
    )

    class Meta:
        abstract = True


class Tree(TimestampedModel):
    """
    Model representing a tree with Solana blockchain integration.

    This model stores both physical tree data and blockchain-specific
    information for compressed NFT management.
    """

    # Blockchain-specific fields
    tree_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the tree"
    )

    mint_address = models.CharField(
        max_length=44,  # Solana address length
        unique=True,
        db_index=True,
        help_text="Solana mint address for the compressed NFT"
    )

    merkle_tree_address = models.CharField(
        max_length=44,
        db_index=True,
        help_text="Address of the Merkle tree containing this NFT"
    )

    leaf_index = models.PositiveIntegerField(
        db_index=True,
        help_text="Index of the leaf in the Merkle tree"
    )

    asset_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique asset ID for the compressed NFT"
    )

    # Physical tree data
    species = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tree species name"
    )

    planted_date = models.DateField(
        db_index=True,
        help_text="Date when the tree was planted"
    )

    location_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Latitude coordinate of tree location"
    )

    location_longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Longitude coordinate of tree location"
    )

    location_name = models.CharField(
        max_length=200,
        help_text="Human-readable location name"
    )

    # Tree status and measurements
    STATUS_CHOICES = [
        ('planted', 'Planted'),
        ('growing', 'Growing'),
        ('mature', 'Mature'),
        ('harvested', 'Harvested'),
        ('dead', 'Dead'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planted',
        db_index=True,
        help_text="Current status of the tree"
    )

    height_cm = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Current height of the tree in centimeters"
    )

    diameter_cm = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Diameter at breast height in centimeters"
    )

    # Carbon and environmental data
    estimated_carbon_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(0)],
        help_text="Estimated carbon sequestered in kilograms"
    )

    verified_carbon_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Verified carbon sequestered in kilograms"
    )

    last_measurement_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last physical measurement"
    )

    # Ownership and management
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_trees',
        help_text="Owner of the tree NFT"
    )

    planter = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='planted_trees',
        null=True,
        blank=True,
        help_text="Person who planted the tree"
    )

    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the tree"
    )

    image_url = models.URLField(
        blank=True,
        help_text="URL to tree image"
    )

    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
        db_index=True,
        help_text="Verification status of the tree data"
    )

    class Meta:
        db_table = 'blockchain_tree'
        indexes = [
            models.Index(fields=['mint_address']),
            models.Index(fields=['merkle_tree_address']),
            models.Index(fields=['asset_id']),
            models.Index(fields=['species', 'status']),
            models.Index(fields=['planted_date']),
            models.Index(fields=['location_latitude', 'location_longitude']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['verification_status', 'status']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Tree'
        verbose_name_plural = 'Trees'

    def __str__(self):
        return f"{self.species} - {self.location_name} ({self.tree_id})"

    @property
    def age_days(self):
        """Calculate tree age in days."""
        return (timezone.now().date() - self.planted_date).days

    @property
    def carbon_per_day(self):
        """Calculate average carbon sequestration per day."""
        if self.age_days > 0 and self.estimated_carbon_kg > 0:
            return self.estimated_carbon_kg / self.age_days
        return Decimal('0.000')

    def get_latest_carbon_data(self):
        """Get the most recent carbon data entry."""
        return self.carbon_data.order_by('-measurement_date').first()

    def get_growth_parameters(self):
        """Get growth parameters for this tree's species."""
        return SpeciesGrowthParameters.objects.filter(species=self.species).first()


class SpeciesGrowthParameters(TimestampedModel):
    """
    Model for storing Chapman-Richards growth parameters for different tree species.

    The Chapman-Richards model is used to predict tree growth over time:
    Y = A * (1 - exp(-k * t))^p

    Where:
    - Y = predicted value (height, diameter, biomass)
    - A = asymptotic maximum value
    - k = growth rate parameter
    - t = time (age)
    - p = shape parameter
    """

    species = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tree species name"
    )

    region = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Geographic region where parameters apply"
    )

    # Chapman-Richards parameters for height prediction
    height_asymptote_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Asymptotic maximum height (A parameter) in centimeters"
    )

    height_growth_rate = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        help_text="Height growth rate parameter (k)"
    )

    height_shape_parameter = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Height shape parameter (p)"
    )

    # Chapman-Richards parameters for diameter prediction
    diameter_asymptote_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Asymptotic maximum diameter (A parameter) in centimeters"
    )

    diameter_growth_rate = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        help_text="Diameter growth rate parameter (k)"
    )

    diameter_shape_parameter = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Diameter shape parameter (p)"
    )

    # Chapman-Richards parameters for biomass/carbon prediction
    biomass_asymptote_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        help_text="Asymptotic maximum biomass (A parameter) in kilograms"
    )

    biomass_growth_rate = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        help_text="Biomass growth rate parameter (k)"
    )

    biomass_shape_parameter = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Biomass shape parameter (p)"
    )

    # Carbon conversion factor
    carbon_conversion_factor = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal('0.470'),  # Typical value: 47% of biomass is carbon
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Factor to convert biomass to carbon content (0-1)"
    )

    # Data source and validity
    data_source = models.CharField(
        max_length=200,
        help_text="Source of the growth parameters data"
    )

    study_year = models.PositiveIntegerField(
        help_text="Year when the study was conducted"
    )

    sample_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of trees in the study sample"
    )

    r_squared = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="R-squared value indicating model fit quality"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether these parameters are currently active"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the parameters"
    )

    class Meta:
        db_table = 'blockchain_species_growth_parameters'
        indexes = [
            models.Index(fields=['species']),
            models.Index(fields=['region']),
            models.Index(fields=['species', 'region']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['species', 'region']]
        ordering = ['species', 'region']
        verbose_name = 'Species Growth Parameters'
        verbose_name_plural = 'Species Growth Parameters'

    def __str__(self):
        return f"{self.species} - {self.region}"

    def predict_height(self, age_days):
        """Predict tree height using Chapman-Richards model."""
        import math
        age_years = age_days / 365.25
        return float(float(self.height_asymptote_cm) *
                    (1 - math.exp(-float(self.height_growth_rate) * age_years)) **
                    float(self.height_shape_parameter))

    def predict_diameter(self, age_days):
        """Predict tree diameter using Chapman-Richards model."""
        import math
        age_years = age_days / 365.25
        return float(float(self.diameter_asymptote_cm) *
                    (1 - math.exp(-float(self.diameter_growth_rate) * age_years)) **
                    float(self.diameter_shape_parameter))

    def predict_carbon(self, age_days):
        """Predict carbon sequestration using Chapman-Richards model."""
        import math
        age_years = age_days / 365.25
        biomass = float(float(self.biomass_asymptote_kg) *
                       (1 - math.exp(-float(self.biomass_growth_rate) * age_years)) **
                       float(self.biomass_shape_parameter))
        return biomass * float(self.carbon_conversion_factor)


class SeiNFT(TimestampedModel):
    """
    Model for storing Sei blockchain NFT data before migration.

    This model captures the original Sei CW721 NFT data structure
    for migration tracking and validation purposes.
    """

    # Sei blockchain identifiers
    sei_contract_address = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Sei contract address for the NFT collection"
    )

    sei_token_id = models.CharField(
        max_length=128,
        db_index=True,
        help_text="Token ID on Sei blockchain"
    )

    sei_owner_address = models.CharField(
        max_length=64,
        help_text="Current owner address on Sei blockchain"
    )

    # NFT metadata
    name = models.CharField(
        max_length=200,
        help_text="NFT name"
    )

    description = models.TextField(
        blank=True,
        help_text="NFT description"
    )

    image_url = models.URLField(
        blank=True,
        help_text="URL to NFT image"
    )

    external_url = models.URLField(
        blank=True,
        help_text="External URL for additional information"
    )

    # Metadata attributes (stored as JSON)
    attributes = models.JSONField(
        default=dict,
        help_text="NFT attributes and traits"
    )

    # Migration status
    MIGRATION_STATUS_CHOICES = [
        ('pending', 'Pending Migration'),
        ('in_progress', 'Migration In Progress'),
        ('completed', 'Migration Completed'),
        ('failed', 'Migration Failed'),
        ('rolled_back', 'Migration Rolled Back'),
    ]

    migration_status = models.CharField(
        max_length=20,
        choices=MIGRATION_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current migration status"
    )

    # Solana mapping (populated after migration)
    solana_mint_address = models.CharField(
        max_length=44,
        blank=True,
        db_index=True,
        help_text="Solana mint address after migration"
    )

    solana_asset_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Solana compressed NFT asset ID"
    )

    # Migration tracking
    migration_job = models.ForeignKey(
        'MigrationJob',
        on_delete=models.CASCADE,
        related_name='sei_nfts',
        null=True,
        blank=True,
        help_text="Associated migration job"
    )

    migration_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when migration was completed"
    )

    # Data integrity
    sei_data_hash = models.CharField(
        max_length=64,
        help_text="Hash of original Sei data for integrity verification"
    )

    validation_errors = models.JSONField(
        default=list,
        help_text="List of validation errors encountered"
    )

    class Meta:
        db_table = 'blockchain_sei_nft'
        indexes = [
            models.Index(fields=['sei_contract_address', 'sei_token_id']),
            models.Index(fields=['migration_status']),
            models.Index(fields=['solana_mint_address']),
            models.Index(fields=['migration_job']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['sei_contract_address', 'sei_token_id']]
        ordering = ['-created_at']
        verbose_name = 'Sei NFT'
        verbose_name_plural = 'Sei NFTs'

    def __str__(self):
        return f"{self.name} ({self.sei_contract_address}:{self.sei_token_id})"

    @property
    def is_migrated(self):
        """Check if NFT has been successfully migrated."""
        return self.migration_status == 'completed' and self.solana_mint_address

    def get_migration_logs(self):
        """Get migration logs for this NFT."""
        return MigrationLog.objects.filter(
            sei_nft=self
        ).order_by('-created_at')


class MigrationJob(TimestampedModel):
    """
    Model for tracking migration jobs and their progress.

    A migration job represents a batch migration operation
    from Sei to Solana blockchain.
    """

    job_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the migration job"
    )

    name = models.CharField(
        max_length=200,
        help_text="Human-readable name for the migration job"
    )

    description = models.TextField(
        blank=True,
        help_text="Description of the migration job"
    )

    # Job configuration
    sei_contract_addresses = models.JSONField(
        default=list,
        help_text="List of Sei contract addresses to migrate"
    )

    batch_size = models.PositiveIntegerField(
        default=100,
        help_text="Number of NFTs to process in each batch"
    )

    # Job status
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='created',
        db_index=True,
        help_text="Current job status"
    )

    # Progress tracking
    total_nfts = models.PositiveIntegerField(
        default=0,
        help_text="Total number of NFTs to migrate"
    )

    processed_nfts = models.PositiveIntegerField(
        default=0,
        help_text="Number of NFTs processed"
    )

    successful_migrations = models.PositiveIntegerField(
        default=0,
        help_text="Number of successful migrations"
    )

    failed_migrations = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed migrations"
    )

    # Timing
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job started"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job completed"
    )

    # Configuration and results
    configuration = models.JSONField(
        default=dict,
        help_text="Job configuration parameters"
    )

    results = models.JSONField(
        default=dict,
        help_text="Job execution results and statistics"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if job failed"
    )

    # User tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_migration_jobs',
        help_text="User who created the migration job"
    )

    class Meta:
        db_table = 'blockchain_migration_job'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['started_at']),
            models.Index(fields=['completed_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Migration Job'
        verbose_name_plural = 'Migration Jobs'

    def __str__(self):
        return f"{self.name} ({self.status})"

    @property
    def progress_percentage(self):
        """Calculate migration progress percentage."""
        if self.total_nfts == 0:
            return 0
        return (self.processed_nfts / self.total_nfts) * 100

    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.processed_nfts == 0:
            return 0
        return (self.successful_migrations / self.processed_nfts) * 100

    @property
    def duration(self):
        """Calculate job duration."""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return end_time - self.started_at

    def get_migration_logs(self):
        """Get all migration logs for this job."""
        return MigrationLog.objects.filter(
            migration_job=self
        ).order_by('-created_at')


class MigrationLog(TimestampedModel):
    """
    Model for logging migration events and operations.

    This model provides comprehensive logging for migration transparency,
    debugging, and audit purposes.
    """

    log_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the log entry"
    )

    # Related objects
    migration_job = models.ForeignKey(
        MigrationJob,
        on_delete=models.CASCADE,
        related_name='logs',
        help_text="Associated migration job"
    )

    sei_nft = models.ForeignKey(
        SeiNFT,
        on_delete=models.CASCADE,
        related_name='logs',
        null=True,
        blank=True,
        help_text="Associated Sei NFT (if applicable)"
    )

    # Log details
    LOG_LEVEL_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    level = models.CharField(
        max_length=10,
        choices=LOG_LEVEL_CHOICES,
        default='info',
        db_index=True,
        help_text="Log level"
    )

    EVENT_TYPE_CHOICES = [
        ('job_started', 'Job Started'),
        ('job_completed', 'Job Completed'),
        ('job_failed', 'Job Failed'),
        ('job_cancelled', 'Job Cancelled'),
        ('data_export', 'Data Export'),
        ('data_mapping', 'Data Mapping'),
        ('data_validation', 'Data Validation'),
        ('nft_migration', 'NFT Migration'),
        ('rollback', 'Rollback'),
        ('error', 'Error'),
    ]

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of event being logged"
    )

    message = models.TextField(
        help_text="Log message"
    )

    # Additional data
    details = models.JSONField(
        default=dict,
        help_text="Additional details and context"
    )

    # Performance metrics
    execution_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Execution time in milliseconds"
    )

    # Error information
    error_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Error code (if applicable)"
    )

    stack_trace = models.TextField(
        blank=True,
        null=True,
        help_text="Stack trace for errors"
    )

    class Meta:
        db_table = 'blockchain_migration_log'
        indexes = [
            models.Index(fields=['migration_job', 'created_at']),
            models.Index(fields=['sei_nft', 'created_at']),
            models.Index(fields=['level']),
            models.Index(fields=['event_type']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Migration Log'
        verbose_name_plural = 'Migration Logs'

    def __str__(self):
        return f"{self.event_type} - {self.level} - {self.created_at}"

    @classmethod
    def log_event(cls, migration_job, event_type, message, level='info',
                  sei_nft=None, details=None, execution_time_ms=None,
                  error_code=None, stack_trace=None):
        """
        Convenience method to create log entries.

        Args:
            migration_job: MigrationJob instance
            event_type: Type of event
            message: Log message
            level: Log level (default: 'info')
            sei_nft: Associated SeiNFT instance (optional)
            details: Additional details dict (optional)
            execution_time_ms: Execution time in milliseconds (optional)
            error_code: Error code (optional)
            stack_trace: Stack trace for errors (optional)

        Returns:
            MigrationLog instance
        """
        return cls.objects.create(
            migration_job=migration_job,
            sei_nft=sei_nft,
            level=level,
            event_type=event_type,
            message=message,
            details=details or {},
            execution_time_ms=execution_time_ms,
            error_code=error_code,
            stack_trace=stack_trace
        )


class CarbonMarketPrice(TimestampedModel):
    """
    Model for storing carbon market prices from various sources and markets.

    This model tracks carbon credit prices over time to enable accurate
    valuation of tree carbon sequestration.
    """

    # Market identification
    market_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Name of the carbon market (e.g., 'California Cap-and-Trade')"
    )

    market_type = models.CharField(
        max_length=50,
        choices=[
            ('compliance', 'Compliance Market'),
            ('voluntary', 'Voluntary Market'),
            ('regional', 'Regional Market'),
            ('international', 'International Market'),
        ],
        db_index=True,
        help_text="Type of carbon market"
    )

    # Price data
    price_date = models.DateField(
        db_index=True,
        help_text="Date of the price quote"
    )

    price_usd_per_ton = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Price in USD per metric ton of CO2 equivalent"
    )

    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217)"
    )

    # Volume and market data
    volume_tons = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Trading volume in metric tons"
    )

    opening_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Opening price for the trading day"
    )

    closing_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Closing price for the trading day"
    )

    high_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Highest price during the trading day"
    )

    low_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Lowest price during the trading day"
    )

    # Data source and quality
    data_source = models.CharField(
        max_length=200,
        help_text="Source of the price data"
    )

    source_url = models.URLField(
        blank=True,
        help_text="URL to the original data source"
    )

    data_quality = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High Quality'),
            ('medium', 'Medium Quality'),
            ('low', 'Low Quality'),
            ('estimated', 'Estimated'),
        ],
        default='medium',
        db_index=True,
        help_text="Quality assessment of the price data"
    )

    # Credit type specifications
    credit_type = models.CharField(
        max_length=100,
        default='forestry',
        help_text="Type of carbon credit (e.g., 'forestry', 'renewable_energy')"
    )

    vintage_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Vintage year of the carbon credits"
    )

    certification_standard = models.CharField(
        max_length=100,
        blank=True,
        help_text="Certification standard (e.g., 'VCS', 'Gold Standard')"
    )

    # Additional metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the price data"
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this price data is currently active"
    )

    class Meta:
        db_table = 'blockchain_carbon_market_price'
        indexes = [
            models.Index(fields=['market_name']),
            models.Index(fields=['market_type']),
            models.Index(fields=['price_date']),
            models.Index(fields=['market_name', 'price_date']),
            models.Index(fields=['credit_type']),
            models.Index(fields=['data_quality']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['market_name', 'price_date', 'credit_type']]
        ordering = ['-price_date', 'market_name']
        verbose_name = 'Carbon Market Price'
        verbose_name_plural = 'Carbon Market Prices'

    def __str__(self):
        return f"{self.market_name} - {self.price_date} - ${self.price_usd_per_ton}/ton"

    @classmethod
    def get_latest_price(cls, market_name=None, credit_type='forestry'):
        """Get the most recent price for a specific market and credit type."""
        queryset = cls.objects.filter(is_active=True, credit_type=credit_type)
        if market_name:
            queryset = queryset.filter(market_name=market_name)
        return queryset.order_by('-price_date').first()

    @classmethod
    def get_average_price(cls, days=30, credit_type='forestry'):
        """Get average price over the last N days."""
        from django.utils import timezone
        from django.db.models import Avg

        cutoff_date = timezone.now().date() - timezone.timedelta(days=days)
        return cls.objects.filter(
            price_date__gte=cutoff_date,
            is_active=True,
            credit_type=credit_type
        ).aggregate(avg_price=Avg('price_usd_per_ton'))['avg_price']


class TreeCarbonData(TimestampedModel):
    """
    Model for storing historical and current carbon sequestration data for trees.

    This model tracks carbon measurements over time, enabling accurate
    carbon credit calculations and verification.
    """

    # Foreign key to tree
    tree = models.ForeignKey(
        Tree,
        on_delete=models.CASCADE,
        related_name='carbon_data',
        help_text="Tree this carbon data belongs to"
    )

    # Measurement details
    measurement_date = models.DateField(
        db_index=True,
        help_text="Date when the measurement was taken"
    )

    measurement_method = models.CharField(
        max_length=50,
        choices=[
            ('direct', 'Direct Measurement'),
            ('allometric', 'Allometric Equation'),
            ('remote_sensing', 'Remote Sensing'),
            ('model_prediction', 'Model Prediction'),
            ('estimated', 'Estimated'),
        ],
        db_index=True,
        help_text="Method used to determine carbon content"
    )

    # Carbon measurements
    above_ground_carbon_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        help_text="Above-ground carbon content in kilograms"
    )

    below_ground_carbon_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Below-ground (root) carbon content in kilograms"
    )

    total_carbon_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        help_text="Total carbon content in kilograms"
    )

    # Supporting measurements
    tree_height_cm = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Tree height at time of measurement in centimeters"
    )

    tree_diameter_cm = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Tree diameter at breast height in centimeters"
    )

    biomass_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Total biomass in kilograms"
    )

    # Data quality and verification
    data_quality = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High Quality'),
            ('medium', 'Medium Quality'),
            ('low', 'Low Quality'),
            ('estimated', 'Estimated'),
        ],
        default='medium',
        db_index=True,
        help_text="Quality assessment of the carbon data"
    )

    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Verification'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('disputed', 'Disputed'),
        ],
        default='pending',
        db_index=True,
        help_text="Verification status of the carbon data"
    )

    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_carbon_data',
        help_text="User who verified this carbon data"
    )

    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when the data was verified"
    )

    # Market valuation
    market_price_usd_per_ton = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Market price used for valuation (USD per ton)"
    )

    carbon_credit_value_usd = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Calculated carbon credit value in USD"
    )

    # Data source and methodology
    data_source = models.CharField(
        max_length=200,
        help_text="Source of the carbon measurement data"
    )

    measurement_equipment = models.CharField(
        max_length=200,
        blank=True,
        help_text="Equipment used for measurement"
    )

    allometric_equation = models.CharField(
        max_length=500,
        blank=True,
        help_text="Allometric equation used for calculation"
    )

    confidence_interval = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Confidence interval percentage for the measurement"
    )

    # Additional metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the carbon measurement"
    )

    weather_conditions = models.CharField(
        max_length=200,
        blank=True,
        help_text="Weather conditions during measurement"
    )

    measured_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='measured_carbon_data',
        help_text="User who took the measurement"
    )

    class Meta:
        db_table = 'blockchain_tree_carbon_data'
        indexes = [
            models.Index(fields=['tree']),
            models.Index(fields=['measurement_date']),
            models.Index(fields=['tree', 'measurement_date']),
            models.Index(fields=['measurement_method']),
            models.Index(fields=['verification_status']),
            models.Index(fields=['data_quality']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['tree', 'measurement_date', 'measurement_method']]
        ordering = ['-measurement_date']
        verbose_name = 'Tree Carbon Data'
        verbose_name_plural = 'Tree Carbon Data'

    def __str__(self):
        return f"{self.tree.species} - {self.measurement_date} - {self.total_carbon_kg}kg CO2"

    def save(self, *args, **kwargs):
        """Override save to calculate total carbon and market value."""
        # Calculate total carbon if not provided
        if not self.total_carbon_kg and self.above_ground_carbon_kg:
            self.total_carbon_kg = self.above_ground_carbon_kg
            if self.below_ground_carbon_kg:
                self.total_carbon_kg += self.below_ground_carbon_kg

        # Calculate market value if price is available
        if self.market_price_usd_per_ton and self.total_carbon_kg:
            # Convert kg to metric tons
            carbon_tons = self.total_carbon_kg / 1000
            self.carbon_credit_value_usd = carbon_tons * self.market_price_usd_per_ton

        super().save(*args, **kwargs)

    @property
    def carbon_tons(self):
        """Convert carbon from kg to metric tons."""
        return self.total_carbon_kg / 1000 if self.total_carbon_kg else 0

    @property
    def days_since_measurement(self):
        """Calculate days since measurement was taken."""
        return (timezone.now().date() - self.measurement_date).days

    def calculate_growth_rate(self):
        """Calculate carbon growth rate compared to previous measurement."""
        previous_measurement = TreeCarbonData.objects.filter(
            tree=self.tree,
            measurement_date__lt=self.measurement_date
        ).order_by('-measurement_date').first()

        if previous_measurement:
            days_diff = (self.measurement_date - previous_measurement.measurement_date).days
            carbon_diff = self.total_carbon_kg - previous_measurement.total_carbon_kg
            if days_diff > 0:
                return carbon_diff / days_diff  # kg per day
        return None
