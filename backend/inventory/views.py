from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta, datetime

from .models import MeatType, MeatCut, Stock, Sale, UserProfile
from .serializers import (
    UserSerializer, MeatTypeSerializer, MeatCutSerializer,
    StockSerializer, SaleSerializer, DashboardStatsSerializer
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
        queryset = Stock.objects.filter(is_active=True)
        meat_type = self.request.query_params.get('meat_type', None)
        if meat_type:
            queryset = queryset.filter(meat_cut__meat_type__id=meat_type)
        return queryset.order_by('-receive_date')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
        except Stock.DoesNotExist:
            return Response(
                {'error': 'Stock not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return super().create(request, *args, **kwargs)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    today = timezone.now().date()
    
    # Total active stock
    total_stock = Stock.objects.filter(is_active=True).aggregate(
        total=Sum('current_weight')
    )['total'] or 0
    
    # Today's sales - total revenue and weight
    today_sales_data = Sale.objects.filter(sale_date__date=today).aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    today_revenue = today_sales_data['total_revenue'] or 0
    today_weight = today_sales_data['total_weight'] or 0
    
    # Low stock count
    low_stock = Stock.objects.filter(is_active=True).filter(
        current_weight__lte=5
    ).count()
    
    # Spoilage warnings (meat older than 2 days)
    spoilage_date = timezone.now() - timedelta(days=2)
    spoilage_warnings = Stock.objects.filter(
        is_active=True,
        receive_date__lte=spoilage_date
    ).count()
    
    # Recent sales
    recent_sales = Sale.objects.all().order_by('-sale_date')[:10]
    
    data = {
        'total_stock': total_stock,
        'total_sales_today': today_revenue,
        'total_weight_sold_today': today_weight,
        'low_stock_count': low_stock,
        'spoilage_warnings': spoilage_warnings,
        'recent_sales': recent_sales
    }
    
    serializer = DashboardStatsSerializer(data)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_alerts(request):
    alerts = Stock.objects.filter(is_active=True).filter(
        current_weight__lte=5
    ).select_related('meat_cut')
    
    data = [{
        'id': stock.id,
        'meat_cut': stock.meat_cut.name,
        'current_weight': float(stock.current_weight),
        'threshold': float(stock.meat_cut.min_stock_threshold)
    } for stock in alerts]
    
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spoilage_alerts(request):
    spoilage_date = timezone.now() - timedelta(days=2)
    alerts = Stock.objects.filter(
        is_active=True,
        receive_date__lte=spoilage_date
    ).select_related('meat_cut')
    
    data = [{
        'id': stock.id,
        'meat_cut': stock.meat_cut.name,
        'receive_date': stock.receive_date,
        'days_old': (timezone.now() - stock.receive_date).days
    } for stock in alerts]
    
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_report(request):
    """
    Get detailed report for a specific day
    Query params: date (YYYY-MM-DD)
    """
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
    
    # Sales for that day
    day_sales = Sale.objects.filter(sale_date__date=target_date).order_by('-sale_date')
    
    # Aggregates
    aggregates = day_sales.aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    
    # Sales by meat type
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
    
    # Sales by user
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