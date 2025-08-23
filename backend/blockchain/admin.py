"""
Django admin configuration for blockchain models.

This module provides comprehensive admin interfaces for managing
trees, carbon data, market prices, and species growth parameters.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData,
    SeiNFT, MigrationJob, MigrationLog
)


@admin.register(Tree)
class TreeAdmin(admin.ModelAdmin):
    """Admin interface for Tree model."""

    list_display = [
        'tree_id', 'species', 'location_name', 'status',
        'planted_date', 'estimated_carbon_kg', 'verification_status',
        'owner', 'created_at'
    ]

    list_filter = [
        'status', 'verification_status', 'species', 'planted_date',
        'created_at', 'updated_at'
    ]

    search_fields = [
        'tree_id', 'species', 'location_name', 'mint_address',
        'asset_id', 'owner__username', 'owner__email'
    ]

    readonly_fields = [
        'tree_id', 'created_at', 'updated_at', 'age_days',
        'carbon_per_day', 'mint_address', 'asset_id'
    ]

    fieldsets = (
        ('Blockchain Information', {
            'fields': (
                'tree_id', 'mint_address', 'merkle_tree_address',
                'leaf_index', 'asset_id'
            )
        }),
        ('Tree Information', {
            'fields': (
                'species', 'planted_date', 'status', 'height_cm',
                'diameter_cm', 'last_measurement_date'
            )
        }),
        ('Location', {
            'fields': (
                'location_name', 'location_latitude', 'location_longitude'
            )
        }),
        ('Carbon Data', {
            'fields': (
                'estimated_carbon_kg', 'verified_carbon_kg'
            )
        }),
        ('Ownership & Management', {
            'fields': (
                'owner', 'planter', 'verification_status'
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes', 'image_url'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at', 'age_days', 'carbon_per_day'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('owner', 'planter')


@admin.register(SpeciesGrowthParameters)
class SpeciesGrowthParametersAdmin(admin.ModelAdmin):
    """Admin interface for SpeciesGrowthParameters model."""

    list_display = [
        'species', 'region', 'data_source', 'study_year',
        'r_squared', 'is_active', 'created_at'
    ]

    list_filter = [
        'is_active', 'study_year', 'region', 'created_at'
    ]

    search_fields = [
        'species', 'region', 'data_source'
    ]

    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'species', 'region', 'is_active'
            )
        }),
        ('Height Parameters', {
            'fields': (
                'height_asymptote_cm', 'height_growth_rate', 'height_shape_parameter'
            )
        }),
        ('Diameter Parameters', {
            'fields': (
                'diameter_asymptote_cm', 'diameter_growth_rate', 'diameter_shape_parameter'
            )
        }),
        ('Biomass/Carbon Parameters', {
            'fields': (
                'biomass_asymptote_kg', 'biomass_growth_rate', 'biomass_shape_parameter',
                'carbon_conversion_factor'
            )
        }),
        ('Data Source', {
            'fields': (
                'data_source', 'study_year', 'sample_size', 'r_squared'
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )


@admin.register(CarbonMarketPrice)
class CarbonMarketPriceAdmin(admin.ModelAdmin):
    """Admin interface for CarbonMarketPrice model."""

    list_display = [
        'market_name', 'price_date', 'price_usd_per_ton',
        'market_type', 'credit_type', 'data_quality', 'is_active'
    ]

    list_filter = [
        'market_type', 'credit_type', 'data_quality', 'is_active',
        'price_date', 'created_at'
    ]

    search_fields = [
        'market_name', 'data_source', 'certification_standard'
    ]

    readonly_fields = ['created_at', 'updated_at']

    date_hierarchy = 'price_date'

    fieldsets = (
        ('Market Information', {
            'fields': (
                'market_name', 'market_type', 'price_date', 'is_active'
            )
        }),
        ('Price Data', {
            'fields': (
                'price_usd_per_ton', 'currency', 'opening_price',
                'closing_price', 'high_price', 'low_price', 'volume_tons'
            )
        }),
        ('Credit Information', {
            'fields': (
                'credit_type', 'vintage_year', 'certification_standard'
            )
        }),
        ('Data Source', {
            'fields': (
                'data_source', 'source_url', 'data_quality'
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )


class TreeCarbonDataInline(admin.TabularInline):
    """Inline admin for TreeCarbonData within Tree admin."""

    model = TreeCarbonData
    extra = 0
    readonly_fields = ['created_at', 'carbon_tons', 'days_since_measurement']
    fields = [
        'measurement_date', 'measurement_method', 'total_carbon_kg',
        'verification_status', 'data_quality', 'carbon_tons'
    ]


@admin.register(TreeCarbonData)
class TreeCarbonDataAdmin(admin.ModelAdmin):
    """Admin interface for TreeCarbonData model."""

    list_display = [
        'tree', 'measurement_date', 'total_carbon_kg', 'measurement_method',
        'verification_status', 'data_quality', 'carbon_credit_value_usd'
    ]

    list_filter = [
        'measurement_method', 'verification_status', 'data_quality',
        'measurement_date', 'created_at'
    ]

    search_fields = [
        'tree__species', 'tree__location_name', 'tree__tree_id',
        'data_source', 'measured_by__username'
    ]

    readonly_fields = [
        'created_at', 'updated_at', 'carbon_tons', 'days_since_measurement'
    ]

    date_hierarchy = 'measurement_date'

    fieldsets = (
        ('Tree & Measurement', {
            'fields': (
                'tree', 'measurement_date', 'measurement_method'
            )
        }),
        ('Carbon Measurements', {
            'fields': (
                'above_ground_carbon_kg', 'below_ground_carbon_kg',
                'total_carbon_kg', 'carbon_tons'
            )
        }),
        ('Supporting Data', {
            'fields': (
                'tree_height_cm', 'tree_diameter_cm', 'biomass_kg'
            )
        }),
        ('Data Quality & Verification', {
            'fields': (
                'data_quality', 'verification_status', 'verified_by',
                'verification_date', 'confidence_interval'
            )
        }),
        ('Market Valuation', {
            'fields': (
                'market_price_usd_per_ton', 'carbon_credit_value_usd'
            )
        }),
        ('Methodology', {
            'fields': (
                'data_source', 'measurement_equipment', 'allometric_equation'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'notes', 'weather_conditions', 'measured_by'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at', 'days_since_measurement'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'tree', 'verified_by', 'measured_by'
        )


# Add the inline to TreeAdmin
TreeAdmin.inlines = [TreeCarbonDataInline]


# Day 5 Admin - Migration Models

@admin.register(SeiNFT)
class SeiNFTAdmin(admin.ModelAdmin):
    """Admin interface for SeiNFT model."""

    list_display = [
        'name', 'sei_contract_address', 'sei_token_id', 'migration_status',
        'solana_mint_address', 'migration_date', 'created_at'
    ]

    list_filter = [
        'migration_status', 'migration_date', 'created_at', 'updated_at'
    ]

    search_fields = [
        'name', 'sei_contract_address', 'sei_token_id', 'sei_owner_address',
        'solana_mint_address', 'solana_asset_id'
    ]

    readonly_fields = ['created_at', 'updated_at', 'sei_data_hash']

    fieldsets = (
        ('Sei Blockchain Information', {
            'fields': (
                'sei_contract_address', 'sei_token_id', 'sei_owner_address',
                'sei_data_hash'
            )
        }),
        ('NFT Metadata', {
            'fields': (
                'name', 'description', 'image_url', 'external_url', 'attributes'
            )
        }),
        ('Migration Status', {
            'fields': (
                'migration_status', 'migration_job', 'migration_date',
                'validation_errors'
            )
        }),
        ('Solana Mapping', {
            'fields': (
                'solana_mint_address', 'solana_asset_id'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('migration_job')


@admin.register(MigrationJob)
class MigrationJobAdmin(admin.ModelAdmin):
    """Admin interface for MigrationJob model."""

    list_display = [
        'name', 'status', 'total_nfts', 'processed_nfts', 'successful_migrations',
        'failed_migrations', 'progress_percentage', 'created_by', 'created_at'
    ]

    list_filter = [
        'status', 'created_at', 'started_at', 'completed_at'
    ]

    search_fields = [
        'name', 'description', 'created_by__username'
    ]

    readonly_fields = [
        'job_id', 'created_at', 'updated_at', 'progress_percentage',
        'success_rate', 'duration'
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'job_id', 'name', 'description', 'created_by'
            )
        }),
        ('Configuration', {
            'fields': (
                'sei_contract_addresses', 'batch_size', 'configuration'
            )
        }),
        ('Status & Progress', {
            'fields': (
                'status', 'total_nfts', 'processed_nfts', 'successful_migrations',
                'failed_migrations', 'progress_percentage', 'success_rate'
            )
        }),
        ('Timing', {
            'fields': (
                'started_at', 'completed_at', 'duration'
            )
        }),
        ('Results & Errors', {
            'fields': (
                'results', 'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('created_by')


class MigrationLogInline(admin.TabularInline):
    """Inline admin for MigrationLog within MigrationJob admin."""

    model = MigrationLog
    extra = 0
    readonly_fields = ['log_id', 'created_at', 'execution_time_ms']
    fields = [
        'level', 'event_type', 'message', 'execution_time_ms', 'created_at'
    ]
    ordering = ['-created_at']


@admin.register(MigrationLog)
class MigrationLogAdmin(admin.ModelAdmin):
    """Admin interface for MigrationLog model."""

    list_display = [
        'event_type', 'level', 'message', 'migration_job', 'sei_nft',
        'execution_time_ms', 'created_at'
    ]

    list_filter = [
        'level', 'event_type', 'created_at'
    ]

    search_fields = [
        'message', 'migration_job__name', 'sei_nft__name', 'error_code'
    ]

    readonly_fields = ['log_id', 'created_at', 'updated_at']

    date_hierarchy = 'created_at'

    fieldsets = (
        ('Log Information', {
            'fields': (
                'log_id', 'migration_job', 'sei_nft', 'level', 'event_type'
            )
        }),
        ('Message & Details', {
            'fields': (
                'message', 'details', 'execution_time_ms'
            )
        }),
        ('Error Information', {
            'fields': (
                'error_code', 'stack_trace'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'migration_job', 'sei_nft'
        )


# Add the inline to MigrationJobAdmin
MigrationJobAdmin.inlines = [MigrationLogInline]
