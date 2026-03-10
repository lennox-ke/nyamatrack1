from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, timedelta

class MeatType(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class MeatCut(models.Model):
    meat_type = models.ForeignKey(MeatType, on_delete=models.CASCADE, related_name='cuts')
    name = models.CharField(max_length=50)
    min_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    spoilage_days = models.IntegerField(default=3)
    
    def __str__(self):
        return f"{self.meat_type.name} - {self.name}"

class Stock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_entries')
    meat_cut = models.ForeignKey(MeatCut, on_delete=models.CASCADE, related_name='stock_items')
    current_weight = models.DecimalField(max_digits=10, decimal_places=2)
    receive_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Stock"
    
    def __str__(self):
        return f"{self.meat_cut.name} - {self.current_weight}kg"
    
    @property
    def days_since_received(self):
        return (datetime.now().replace(tzinfo=None) - self.receive_date.replace(tzinfo=None)).days
    
    @property
    def is_spoilage_warning(self):
        return self.days_since_received >= self.meat_cut.spoilage_days - 1
    
    @property
    def is_low_stock(self):
        return self.current_weight <= self.meat_cut.min_stock_threshold

class Sale(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='sales')
    weight_sold = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.stock.meat_cut.name} - {self.weight_sold}kg - KES {self.sale_price}"
    
    def save(self, *args, **kwargs):
        # Deduct from stock
        self.stock.current_weight -= self.weight_sold
        if self.stock.current_weight <= 0:
            self.stock.is_active = False
        self.stock.save()
        super().save(*args, **kwargs)

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Shop Owner'),
        ('keeper', 'Stock Keeper'),
        ('butcher', 'Butcher'),
        ('admin', 'System Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='butcher')
    shop_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"

# Signal to create UserProfile automatically when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.create(user=instance)