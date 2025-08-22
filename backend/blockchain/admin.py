"""
Django admin configuration for blockchain models.

This module provides comprehensive admin interfaces for managing
trees, carbon data, market prices, and species growth parameters.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData


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
