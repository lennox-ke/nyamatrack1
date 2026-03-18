from rest_framework import serializers
from django.contrib.auth.models import User
from .models import MeatType, MeatCut, Stock, Sale, UserProfile, RemovalHistory

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['role', 'shop_name', 'phone_number']
        extra_kwargs = {
            'role': {'default': 'butcher'},
            'shop_name': {'default': ''},
            'phone_number': {'default': ''}
        }

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password', 'profile', 'date_joined']
    
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if not hasattr(instance, 'profile') or instance.profile is None:
            UserProfile.objects.create(user=instance)
            instance.refresh_from_db()
        try:
            ret['profile'] = UserProfileSerializer(instance.profile).data
        except UserProfile.DoesNotExist:
            ret['profile'] = {'role': 'butcher', 'shop_name': '', 'phone_number': ''}
        return ret
    
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password', None)
        
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': profile_data.get('role', 'butcher'),
                'shop_name': profile_data.get('shop_name', ''),
                'phone_number': profile_data.get('phone_number', '')
            }
        )
        
        return user
    
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        
        UserProfile.objects.update_or_create(
            user=instance,
            defaults={
                'role': profile_data.get('role', instance.profile.role if hasattr(instance, 'profile') else 'butcher'),
                'shop_name': profile_data.get('shop_name', instance.profile.shop_name if hasattr(instance, 'profile') else ''),
                'phone_number': profile_data.get('phone_number', instance.profile.phone_number if hasattr(instance, 'profile') else '')
            }
        )
        
        return instance

class MeatTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeatType
        fields = '__all__'

class MeatCutSerializer(serializers.ModelSerializer):
    meat_type_name = serializers.CharField(source='meat_type.name', read_only=True)
    
    class Meta:
        model = MeatCut
        fields = '__all__'

class StockSerializer(serializers.ModelSerializer):
    meat_cut_details = MeatCutSerializer(source='meat_cut', read_only=True)
    days_since_received = serializers.IntegerField(read_only=True)
    is_spoilage_warning = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    total_weight = serializers.SerializerMethodField()
    stock_entries = serializers.SerializerMethodField()
    
    class Meta:
        model = Stock
        fields = ['id', 'meat_cut', 'meat_cut_details', 'current_weight', 'total_weight', 
                  'receive_date', 'is_active', 'user', 'username', 'days_since_received',
                  'is_spoilage_warning', 'is_low_stock', 'stock_entries']
        read_only_fields = ['user']
    
    def get_total_weight(self, obj):
        if hasattr(obj, 'total_weight'):
            return obj.total_weight
        return obj.current_weight
    
    def get_stock_entries(self, obj):
        if hasattr(obj, 'stock_entries'):
            return obj.stock_entries
        return None

class SaleSerializer(serializers.ModelSerializer):
    stock_details = StockSerializer(source='stock', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    meat_cut_name = serializers.CharField(source='stock.meat_cut.name', read_only=True)
    fifo_details = serializers.JSONField(required=False, read_only=True)
    
    class Meta:
        model = Sale
        fields = ['id', 'stock', 'stock_details', 'weight_sold', 'sale_price', 
                  'sale_date', 'user', 'username', 'meat_cut_name', 'fifo_details']
        read_only_fields = ['user']

class RemovalHistorySerializer(serializers.ModelSerializer):
    meat_cut_name = serializers.CharField(source='meat_cut.name', read_only=True)
    meat_type_name = serializers.CharField(source='meat_cut.meat_type.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = RemovalHistory
        fields = ['id', 'meat_cut', 'meat_cut_name', 'meat_type_name', 'stock_id',
                  'weight_removed', 'reason', 'reason_display', 'custom_reason',
                  'days_old_at_removal', 'receive_date', 'removed_at', 'notes', 'username']

class DashboardStatsSerializer(serializers.Serializer):
    total_stock = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_sales_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_weight_sold_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_count = serializers.IntegerField()
    spoilage_warnings = serializers.IntegerField()
    recent_sales = SaleSerializer(many=True)