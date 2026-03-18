from django.contrib import admin
from .models import MeatType, MeatCut, Stock, Sale, UserProfile, RemovalHistory

@admin.register(MeatType)
class MeatTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(MeatCut)
class MeatCutAdmin(admin.ModelAdmin):
    list_display = ['name', 'meat_type', 'min_stock_threshold', 'spoilage_days']
    list_filter = ['meat_type']

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['meat_cut', 'current_weight', 'receive_date', 'is_active', 'user']
    list_filter = ['is_active', 'receive_date', 'meat_cut__meat_type']
    date_hierarchy = 'receive_date'

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['stock', 'weight_sold', 'sale_price', 'sale_date', 'user']
    date_hierarchy = 'sale_date'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'shop_name']
    list_filter = ['role']

@admin.register(RemovalHistory)
class RemovalHistoryAdmin(admin.ModelAdmin):
    list_display = ['meat_cut', 'weight_removed', 'reason', 'user', 'removed_at', 'days_old_at_removal']
    list_filter = ['reason', 'removed_at', 'meat_cut__meat_type']
    date_hierarchy = 'removed_at'
    search_fields = ['meat_cut__name', 'user__username', 'notes']
    readonly_fields = ['removed_at', 'stock_id', 'days_old_at_removal']