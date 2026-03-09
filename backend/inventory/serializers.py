from rest_framework import serializers
from django.contrib.auth.models import User
from .models import MeatType, MeatCut, Stock, Sale, UserProfile, StockRemoval

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['role', 'shop_name', 'phone_number']
        # Add default values for missing fields
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
        # Ensure profile exists when reading
        ret = super().to_representation(instance)
        if not hasattr(instance, 'profile') or instance.profile is None:
            # Create profile if missing
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
        
        # Create or update profile
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
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        
        # Update or create profile
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
    is_actually_spoiled = serializers.BooleanField(read_only=True)  # NEW
    is_low_stock = serializers.BooleanField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ['user', 'is_spoiled']

# NEW: Serializer for spoiled vs unspoiled categorization
class StockCategorizationSerializer(serializers.Serializer):
    meat_cut_id = serializers.IntegerField()
    meat_cut_name = serializers.CharField()
    meat_type_name = serializers.CharField()
    
    # Unspoiled stock
    unspoiled_items = serializers.ListField(child=serializers.DictField())
    total_unspoiled_weight = serializers.DecimalField(max_digits=10, decimal_places=2)
    unspoiled_count = serializers.IntegerField()
    
    # Spoiled stock
    spoiled_items = serializers.ListField(child=serializers.DictField())
    total_spoiled_weight = serializers.DecimalField(max_digits=10, decimal_places=2)
    spoiled_count = serializers.IntegerField()
    
    # Totals
    total_weight = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_items = serializers.IntegerField()
    
    # Alert info
    is_low_stock = serializers.BooleanField()
    min_threshold = serializers.DecimalField(max_digits=10, decimal_places=2)
    approaching_spoilage = serializers.BooleanField()

# NEW: Serializer for stock removal
class StockRemovalSerializer(serializers.ModelSerializer):
    meat_cut_name = serializers.CharField(source='meat_cut.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = StockRemoval
        fields = '__all__'
        read_only_fields = ['user', 'removal_date', 'days_at_removal']

class SaleSerializer(serializers.ModelSerializer):
    stock_details = StockSerializer(source='stock', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    meat_cut_name = serializers.CharField(source='stock.meat_cut.name', read_only=True)
    
    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['user']

class DashboardStatsSerializer(serializers.Serializer):
    total_stock = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_sales_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_weight_sold_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    low_stock_count = serializers.IntegerField()
    spoilage_warnings = serializers.IntegerField()
    recent_sales = SaleSerializer(many=True)