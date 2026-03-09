from django.contrib import admin
from .models import MeatType, MeatCut, Stock, Sale, UserProfile, StockRemoval

@admin.register(MeatType)
class MeatTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(MeatCut)
class MeatCutAdmin(admin.ModelAdmin):
    list_display = ['name', 'meat_type', 'min_stock_threshold', 'spoilage_days']
    list_filter = ['meat_type']

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['meat_cut', 'current_weight', 'receive_date', 'is_active', 'is_spoiled', 'user']
    list_filter = ['is_active', 'is_spoiled', 'receive_date', 'meat_cut__meat_type']
    date_hierarchy = 'receive_date'
    actions = ['mark_as_spoiled']
    
    def mark_as_spoiled(self, request, queryset):
        queryset.update(is_spoiled=True)
    mark_as_spoiled.short_description = "Mark selected stock as spoiled"

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['stock', 'weight_sold', 'sale_price', 'sale_date', 'user']
    date_hierarchy = 'sale_date'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'shop_name']
    list_filter = ['role']

# NEW: Admin for stock removals
@admin.register(StockRemoval)
class StockRemovalAdmin(admin.ModelAdmin):
    list_display = ['meat_cut', 'weight_removed', 'reason', 'removal_date', 'user', 'days_at_removal']
    list_filter = ['reason', 'removal_date', 'meat_cut__meat_type']
    date_hierarchy = 'removal_date'
    readonly_fields = ['removal_date', 'days_at_removal']