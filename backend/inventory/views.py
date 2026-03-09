from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from datetime import timedelta, datetime

from .models import MeatType, MeatCut, Stock, Sale, UserProfile, StockRemoval
from .serializers import (
    UserSerializer, MeatTypeSerializer, MeatCutSerializer,
    StockSerializer, SaleSerializer, DashboardStatsSerializer,
    StockRemovalSerializer, StockCategorizationSerializer
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        serializer.save()

class MeatTypeViewSet(viewsets.ModelViewSet):
    queryset = MeatType.objects.all()
    serializer_class = MeatTypeSerializer
    permission_classes = [IsAuthenticated]

class MeatCutViewSet(viewsets.ModelViewSet):
    queryset = MeatCut.objects.all()
    serializer_class = MeatCutSerializer
    permission_classes = [IsAuthenticated]

class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only return active, non-spoiled stock for listing by default
        queryset = Stock.objects.filter(is_active=True, is_spoiled=False)
        meat_type = self.request.query_params.get('meat_type', None)
        if meat_type:
            queryset = queryset.filter(meat_cut__meat_type__id=meat_type)
        return queryset.order_by('-receive_date')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        # Soft delete - mark as inactive instead of deleting
        instance.is_active = False
        instance.save()

    # NEW: Get all stock (spoiled and unspoiled) categorized by cut
    @action(detail=False, methods=['get'])
    def categorized(self, request):
        """Get stock categorized by cut, showing spoiled vs unspoiled"""
        meat_cut_id = request.query_params.get('meat_cut', None)
        
        # Base queryset - all active stock
        queryset = Stock.objects.filter(is_active=True)
        if meat_cut_id:
            queryset = queryset.filter(meat_cut__id=meat_cut_id)
        
        # Group by meat cut
        cuts = MeatCut.objects.all()
        if meat_cut_id:
            cuts = cuts.filter(id=meat_cut_id)
        
        result = []
        for cut in cuts:
            cut_stock = queryset.filter(meat_cut=cut)
            
            # Separate spoiled and unspoiled
            unspoiled = cut_stock.filter(is_spoiled=False)
            spoiled = cut_stock.filter(is_spoiled=True)
            
            # Calculate totals for unspoiled
            unspoiled_items = []
            total_unspoiled_weight = 0
            for item in unspoiled:
                days_old = item.days_since_received
                is_warning = days_old >= cut.spoilage_days - 1
                unspoiled_items.append({
                    'id': item.id,
                    'weight': float(item.current_weight),
                    'receive_date': item.receive_date,
                    'days_old': days_old,
                    'is_spoilage_warning': is_warning,
                    'added_by': item.user.username
                })
                total_unspoiled_weight += float(item.current_weight)
            
            # Calculate totals for spoiled
            spoiled_items = []
            total_spoiled_weight = 0
            for item in spoiled:
                days_old = item.days_since_received
                spoiled_items.append({
                    'id': item.id,
                    'weight': float(item.current_weight),
                    'receive_date': item.receive_date,
                    'days_old': days_old,
                    'removed_date': item.removals.first().removal_date if item.removals.exists() else None,
                    'added_by': item.user.username
                })
                total_spoiled_weight += float(item.current_weight)
            
            # Check if total unspoiled weight is low
            is_low_stock = total_unspoiled_weight <= cut.min_stock_threshold
            
            # Check if any unspoiled items are approaching spoilage
            approaching_spoilage = any(item['is_spoilage_warning'] for item in unspoiled_items)
            
            result.append({
                'meat_cut_id': cut.id,
                'meat_cut_name': cut.name,
                'meat_type_name': cut.meat_type.name,
                'unspoiled_items': unspoiled_items,
                'total_unspoiled_weight': total_unspoiled_weight,
                'unspoiled_count': len(unspoiled_items),
                'spoiled_items': spoiled_items,
                'total_spoiled_weight': total_spoiled_weight,
                'spoiled_count': len(spoiled_items),
                'total_weight': total_unspoiled_weight + total_spoiled_weight,
                'total_items': len(unspoiled_items) + len(spoiled_items),
                'is_low_stock': is_low_stock,
                'min_threshold': float(cut.min_stock_threshold),
                'approaching_spoilage': approaching_spoilage,
                'spoilage_days': cut.spoilage_days
            })
        
        return Response(result)
    
    # NEW: Mark stock as spoiled (before removal)
    @action(detail=True, methods=['post'])
    def mark_spoiled(self, request, pk=None):
        """Mark a stock item as spoiled"""
        stock = self.get_object()
        stock.is_spoiled = True
        stock.save()
        return Response({'status': 'marked as spoiled'})
    
    # NEW: Remove spoiled stock and create removal record
    @action(detail=True, methods=['post'])
    def remove_spoiled(self, request, pk=None):
        """Remove spoiled stock and create a removal record"""
        stock = self.get_object()
        
        # Only allow removing spoiled stock
        if not stock.is_spoiled and not stock.is_actually_spoiled:
            return Response(
                {'error': 'Stock must be spoiled before removal'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'spoiled')
        notes = request.data.get('notes', '')
        
        # Create removal record
        removal = StockRemoval.objects.create(
            user=request.user,
            stock=stock,
            meat_cut=stock.meat_cut,
            weight_removed=stock.current_weight,
            reason=reason,
            notes=notes,
            original_receive_date=stock.receive_date,
            days_at_removal=stock.days_since_received
        )
        
        # Mark stock as inactive (removed)
        stock.is_active = False
        stock.current_weight = 0
        stock.save()
        
        serializer = StockRemovalSerializer(removal)
        return Response(serializer.data)

class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Sale.objects.all()
        date_from = self.request.query_params.get('from', None)
        date_to = self.request.query_params.get('to', None)
        
        if date_from:
            queryset = queryset.filter(sale_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(sale_date__date__lte=date_to)
        
        return queryset.order_by('-sale_date')[:50]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        stock_id = request.data.get('stock')
        weight_sold = float(request.data.get('weight_sold', 0))
        
        try:
            stock = Stock.objects.get(id=stock_id, is_active=True)
            if stock.current_weight < weight_sold:
                return Response(
                    {'error': 'Insufficient stock available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Don't allow selling spoiled stock
            if stock.is_spoiled:
                return Response(
                    {'error': 'Cannot sell spoiled stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Stock.DoesNotExist:
            return Response(
                {'error': 'Stock not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return super().create(request, *args, **kwargs)

# NEW: ViewSet for stock removal records
class StockRemovalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockRemovalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = StockRemoval.objects.all()
        meat_cut = self.request.query_params.get('meat_cut', None)
        reason = self.request.query_params.get('reason', None)
        date_from = self.request.query_params.get('from', None)
        date_to = self.request.query_params.get('to', None)
        
        if meat_cut:
            queryset = queryset.filter(meat_cut__id=meat_cut)
        if reason:
            queryset = queryset.filter(reason=reason)
        if date_from:
            queryset = queryset.filter(removal_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(removal_date__date__lte=date_to)
        
        return queryset.order_by('-removal_date')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    today = timezone.now().date()
    
    # Total active stock (only non-spoiled, non-zero stock)
    total_stock = Stock.objects.filter(
        is_active=True, 
        is_spoiled=False,
        current_weight__gt=0
    ).aggregate(
        total=Sum('current_weight')
    )['total'] or 0
    
    # Today's sales - total revenue and weight
    today_sales_data = Sale.objects.filter(sale_date__date=today).aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    today_revenue = today_sales_data['total_revenue'] or 0
    today_weight = today_sales_data['total_weight'] or 0
    
    # Low stock count - Check TOTAL weight per cut, not individual items
    low_stock_count = 0
    for cut in MeatCut.objects.all():
        total_cut_weight = Stock.objects.filter(
            meat_cut=cut,
            is_active=True,
            is_spoiled=False,
            current_weight__gt=0
        ).aggregate(total=Sum('current_weight'))['total'] or 0
        
        if total_cut_weight > 0 and total_cut_weight <= cut.min_stock_threshold:
            low_stock_count += 1
    
    # Spoilage warnings - Count cuts with items approaching spoilage
    spoilage_warnings = 0
    for cut in MeatCut.objects.all():
        warning_items = Stock.objects.filter(
            meat_cut=cut,
            is_active=True,
            is_spoiled=False,
            current_weight__gt=0,
            receive_date__lte=timezone.now() - timezone.timedelta(days=cut.spoilage_days - 1)
        ).exists()
        if warning_items:
            spoilage_warnings += 1
    
    # Recent sales
    recent_sales = Sale.objects.all().order_by('-sale_date')[:10]
    
    data = {
        'total_stock': total_stock,
        'total_sales_today': today_revenue,
        'total_weight_sold_today': today_weight,
        'low_stock_count': low_stock_count,
        'spoilage_warnings': spoilage_warnings,
        'recent_sales': recent_sales
    }
    
    serializer = DashboardStatsSerializer(data)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_alerts(request):
    """Get low stock alerts grouped by meat cut (checking total kgs per cut)"""
    alerts = []
    
    for cut in MeatCut.objects.all():
        # Calculate total weight for this cut across all active, unspoiled stock
        total_weight = Stock.objects.filter(
            meat_cut=cut,
            is_active=True,
            is_spoiled=False,
            current_weight__gt=0
        ).aggregate(total=Sum('current_weight'))['total'] or 0
        
        # Only alert if total weight is above 0 but below threshold
        if 0 < total_weight <= cut.min_stock_threshold:
            # Get all stock items for this cut
            stock_items = Stock.objects.filter(
                meat_cut=cut,
                is_active=True,
                is_spoiled=False,
                current_weight__gt=0
            ).order_by('receive_date')
            
            alerts.append({
                'meat_cut_id': cut.id,
                'meat_cut': cut.name,
                'meat_type': cut.meat_type.name,
                'total_weight': float(total_weight),
                'threshold': float(cut.min_stock_threshold),
                'stock_items': [{
                    'id': item.id,
                    'weight': float(item.current_weight),
                    'receive_date': item.receive_date,
                    'days_old': item.days_since_received
                } for item in stock_items]
            })
    
    return Response(alerts)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spoilage_alerts(request):
    """Get spoilage alerts with specific cut details and dates"""
    alerts = []
    
    for cut in MeatCut.objects.all():
        # Find all active, unspoiled stock items approaching or past spoilage
        warning_date = timezone.now() - timezone.timedelta(days=cut.spoilage_days - 1)
        spoiled_items = Stock.objects.filter(
            meat_cut=cut,
            is_active=True,
            is_spoiled=False,
            current_weight__gt=0,
            receive_date__lte=warning_date
        ).order_by('receive_date')
        
        for item in spoiled_items:
            days_old = item.days_since_received
            is_past_spoilage = days_old >= cut.spoilage_days
            
            alerts.append({
                'stock_id': item.id,
                'meat_cut_id': cut.id,
                'meat_cut': cut.name,
                'meat_type': cut.meat_type.name,
                'receive_date': item.receive_date,
                'days_old': days_old,
                'spoilage_days': cut.spoilage_days,
                'current_weight': float(item.current_weight),
                'is_past_spoilage': is_past_spoilage,
                'days_until_spoilage': max(0, cut.spoilage_days - days_old),
                'added_by': item.user.username
            })
    
    # Sort by most urgent (past spoilage first, then by days old descending)
    alerts.sort(key=lambda x: (not x['is_past_spoilage'], -x['days_old']))
    
    return Response(alerts)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_report(request):
    date_str = request.query_params.get('date', None)
    
    if not date_str:
        target_date = timezone.now().date()
    else:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    day_sales = Sale.objects.filter(sale_date__date=target_date).order_by('-sale_date')
    
    aggregates = day_sales.aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    
    sales_by_type = {}
    for sale in day_sales:
        meat_type = sale.stock.meat_cut.meat_type.name
        if meat_type not in sales_by_type:
            sales_by_type[meat_type] = {
                'total_weight': 0,
                'total_revenue': 0,
                'transactions': 0
            }
        sales_by_type[meat_type]['total_weight'] += float(sale.weight_sold)
        sales_by_type[meat_type]['total_revenue'] += float(sale.sale_price)
        sales_by_type[meat_type]['transactions'] += 1
    
    sales_by_user = {}
    for sale in day_sales:
        username = sale.user.username
        if username not in sales_by_user:
            sales_by_user[username] = {
                'total_weight': 0,
                'total_revenue': 0,
                'transactions': 0
            }
        sales_by_user[username]['total_weight'] += float(sale.weight_sold)
        sales_by_user[username]['total_revenue'] += float(sale.sale_price)
        sales_by_user[username]['transactions'] += 1
    
    data = {
        'date': target_date.isoformat(),
        'summary': {
            'total_revenue': aggregates['total_revenue'] or 0,
            'total_weight_sold': aggregates['total_weight'] or 0,
            'total_transactions': day_sales.count(),
        },
        'sales_by_type': sales_by_type,
        'sales_by_user': sales_by_user,
        'transactions': SaleSerializer(day_sales, many=True).data
    }
    
    return Response(data)