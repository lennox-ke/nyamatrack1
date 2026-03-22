from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Sum, Q, F, Min, Max, Count
from django.utils import timezone
from datetime import timedelta, datetime
import logging
import traceback

from .models import MeatType, MeatCut, Stock, Sale, UserProfile, RemovalHistory
from .serializers import (
    UserSerializer, MeatTypeSerializer, MeatCutSerializer,
    StockSerializer, SaleSerializer, DashboardStatsSerializer,
    RemovalHistorySerializer
)

logger = logging.getLogger(__name__)


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
        queryset = Stock.objects.filter(is_active=True).select_related('meat_cut', 'meat_cut__meat_type')
        
        meat_type = self.request.query_params.get('meat_type', None)
        if meat_type:
            queryset = queryset.filter(meat_cut__meat_type__id=meat_type)
        
        return queryset.order_by('meat_cut__id', 'receive_date')
    
    def list(self, request, *args, **kwargs):
        all_stock = Stock.objects.filter(
            is_active=True,
            current_weight__gt=0
        ).select_related('meat_cut', 'meat_cut__meat_type').order_by('meat_cut__id', 'receive_date')
        
        aggregated_data = {}
        for stock in all_stock:
            cut_id = stock.meat_cut.id
            if cut_id not in aggregated_data:
                aggregated_data[cut_id] = {
                    'id': stock.id,
                    'meat_cut': stock.meat_cut.id,
                    'meat_cut_details': {
                        'id': stock.meat_cut.id,
                        'name': stock.meat_cut.name,
                        'meat_type': stock.meat_cut.meat_type.id,
                        'meat_type_name': stock.meat_cut.meat_type.name,
                        'spoilage_days': stock.meat_cut.spoilage_days,
                        'min_stock_threshold': float(stock.meat_cut.min_stock_threshold)
                    },
                    'total_weight': 0,
                    'oldest_receive_date': stock.receive_date,
                    'newest_receive_date': stock.receive_date,
                    'stock_entries': [],
                    'is_spoilage_warning': False,
                    'is_low_stock': False,
                    'days_since_received': 0
                }
            
            aggregated_data[cut_id]['total_weight'] += float(stock.current_weight)
            aggregated_data[cut_id]['stock_entries'].append({
                'id': stock.id,
                'current_weight': float(stock.current_weight),
                'receive_date': stock.receive_date,
                'user': stock.user.username
            })
            
            if stock.receive_date < aggregated_data[cut_id]['oldest_receive_date']:
                aggregated_data[cut_id]['oldest_receive_date'] = stock.receive_date
                aggregated_data[cut_id]['id'] = stock.id
            
            if stock.receive_date > aggregated_data[cut_id]['newest_receive_date']:
                aggregated_data[cut_id]['newest_receive_date'] = stock.receive_date
        
        result = []
        now = timezone.now()
        for data in aggregated_data.values():
            days_old = (now - data['oldest_receive_date']).days
            data['current_weight'] = data['total_weight']
            data['receive_date'] = data['oldest_receive_date']
            data['days_since_received'] = days_old
            data['is_spoilage_warning'] = days_old >= data['meat_cut_details']['spoilage_days'] - 1
            data['is_low_stock'] = data['total_weight'] <= data['meat_cut_details']['min_stock_threshold']
            data['username'] = data['stock_entries'][0]['user'] if data['stock_entries'] else 'Unknown'
            result.append(data)
        
        meat_type_filter = request.query_params.get('meat_type', None)
        if meat_type_filter:
            result = [r for r in result if str(r['meat_cut_details']['meat_type']) == str(meat_type_filter)]
        
        return Response(result)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
    
    @action(detail=False, methods=['post'], url_path='remove-spoiled')
    def remove_spoiled(self, request):
        stock_id = request.data.get('stock_id')
        reason = request.data.get('reason', 'spoilage')
        custom_reason = request.data.get('custom_reason', '')
        notes = request.data.get('notes', '')
        
        if not stock_id:
            return Response(
                {'error': 'stock_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stock = Stock.objects.get(id=stock_id, is_active=True)
            
            days_old = (timezone.now() - stock.receive_date).days
            if days_old < stock.meat_cut.spoilage_days - 1:
                return Response(
                    {'error': 'This stock is not marked for spoilage. Use regular delete instead.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            removal_record = RemovalHistory.objects.create(
                user=request.user,
                meat_cut=stock.meat_cut,
                stock_id=stock.id,
                weight_removed=stock.current_weight,
                reason=reason,
                custom_reason=custom_reason,
                days_old_at_removal=days_old,
                receive_date=stock.receive_date,
                notes=notes or f'Removed due to {reason}'
            )
            
            removed_weight = float(stock.current_weight)
            stock_name = stock.meat_cut.name
            stock.is_active = False
            stock.current_weight = 0
            stock.save()
            
            return Response({
                'message': f'Successfully removed {stock_name} ({removed_weight}kg) due to {reason}',
                'removed_weight': removed_weight,
                'days_old': days_old,
                'meat_cut': stock_name,
                'removal_id': removal_record.id,
                'removed_at': removal_record.removed_at
            })
            
        except Stock.DoesNotExist:
            return Response(
                {'error': 'Stock not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'], url_path='remove-all-spoiled')
    def remove_all_spoiled(self, request):
        meat_cut_id = request.data.get('meat_cut_id')
        reason = request.data.get('reason', 'spoilage')
        custom_reason = request.data.get('custom_reason', '')
        notes = request.data.get('notes', '')
        
        if not meat_cut_id:
            return Response(
                {'error': 'meat_cut_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            spoiled_stock = Stock.objects.filter(
                meat_cut__id=meat_cut_id,
                is_active=True,
                current_weight__gt=0
            ).select_related('meat_cut')
            
            removed_entries = []
            total_removed = 0
            removal_records = []
            
            for stock in spoiled_stock:
                days_old = (timezone.now() - stock.receive_date).days
                if days_old >= stock.meat_cut.spoilage_days - 1:
                    removed_weight = float(stock.current_weight)
                    
                    removal_record = RemovalHistory.objects.create(
                        user=request.user,
                        meat_cut=stock.meat_cut,
                        stock_id=stock.id,
                        weight_removed=stock.current_weight,
                        reason=reason,
                        custom_reason=custom_reason,
                        days_old_at_removal=days_old,
                        receive_date=stock.receive_date,
                        notes=notes or f'Batch removal due to {reason}'
                    )
                    removal_records.append(removal_record.id)
                    
                    stock.is_active = False
                    stock.current_weight = 0
                    stock.save()
                    
                    removed_entries.append({
                        'id': stock.id,
                        'weight': removed_weight,
                        'days_old': days_old,
                        'removal_id': removal_record.id
                    })
                    total_removed += removed_weight
            
            if not removed_entries:
                return Response(
                    {'message': 'No spoiled stock found for this meat cut'},
                    status=status.HTTP_200_OK
                )
            
            return Response({
                'message': f'Successfully removed {len(removed_entries)} entries ({total_removed}kg)',
                'removed_entries': removed_entries,
                'total_weight': total_removed,
                'meat_cut': spoiled_stock.first().meat_cut.name,
                'removal_ids': removal_records
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RemovalHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RemovalHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = RemovalHistory.objects.select_related('meat_cut', 'meat_cut__meat_type', 'user')
        
        date_from = self.request.query_params.get('from', None)
        date_to = self.request.query_params.get('to', None)
        reason = self.request.query_params.get('reason', None)
        meat_cut = self.request.query_params.get('meat_cut', None)
        
        if date_from:
            queryset = queryset.filter(removed_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(removed_at__date__lte=date_to)
        if reason:
            queryset = queryset.filter(reason=reason)
        if meat_cut:
            queryset = queryset.filter(meat_cut__id=meat_cut)
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        today = timezone.now().date()
        
        today_removals = RemovalHistory.objects.filter(removed_at__date=today).aggregate(
            total_weight=Sum('weight_removed'),
            count=Count('id')
        )
        
        month_start = today.replace(day=1)
        month_removals = RemovalHistory.objects.filter(removed_at__date__gte=month_start).aggregate(
            total_weight=Sum('weight_removed'),
            count=Count('id')
        )
        
        by_reason = RemovalHistory.objects.values('reason').annotate(
            total_weight=Sum('weight_removed'),
            count=Count('id')
        ).order_by('-total_weight')
        
        top_items = RemovalHistory.objects.values('meat_cut__name').annotate(
            total_weight=Sum('weight_removed'),
            count=Count('id')
        ).order_by('-total_weight')[:5]
        
        return Response({
            'today': {
                'total_weight': today_removals['total_weight'] or 0,
                'count': today_removals['count'] or 0
            },
            'this_month': {
                'total_weight': month_removals['total_weight'] or 0,
                'count': month_removals['count'] or 0
            },
            'by_reason': list(by_reason),
            'top_items': list(top_items)
        })


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Sale.objects.all().select_related('stock', 'stock__meat_cut', 'user')
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
        try:
            stock_id = request.data.get('stock')
            weight_sold = float(request.data.get('weight_sold', 0))
            sale_price = float(request.data.get('sale_price', 0))
        except (TypeError, ValueError) as e:
            return Response(
                {'error': f'Invalid numeric value: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not stock_id:
            return Response({'error': 'stock is required'}, status=status.HTTP_400_BAD_REQUEST)

        if weight_sold <= 0:
            return Response({'error': 'weight_sold must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)

        if sale_price <= 0:
            return Response({'error': 'sale_price must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve meat_cut from the provided stock_id.
        # Accept the stock even if it's the aggregated "display" id from the frontend.
        try:
            initial_stock = Stock.objects.select_related('meat_cut').get(id=stock_id)
        except Stock.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

        meat_cut = initial_stock.meat_cut

        # Check total available weight across ALL active batches for this meat cut
        total_available = Stock.objects.filter(
            meat_cut=meat_cut,
            is_active=True,
            current_weight__gt=0
        ).aggregate(total=Sum('current_weight'))['total'] or 0

        if float(total_available) < weight_sold:
            return Response(
                {'error': f'Insufficient stock. Available: {float(total_available):.2f}kg, Requested: {weight_sold}kg'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # FIFO deduction — oldest batches first
        remaining_to_sell = weight_sold
        stock_entries_used = []
        reference_stock = None  # will hold the first batch touched (for Sale FK)

        fifo_stock = Stock.objects.filter(
            meat_cut=meat_cut,
            is_active=True,
            current_weight__gt=0
        ).order_by('receive_date')

        for entry in fifo_stock:
            if remaining_to_sell <= 0:
                break

            available = float(entry.current_weight)
            deduct = min(available, remaining_to_sell)

            entry.current_weight = round(available - deduct, 2)
            if entry.current_weight <= 0:
                entry.is_active = False
            entry.save()

            stock_entries_used.append({
                'stock_id': entry.id,
                'deducted': deduct,
                'remaining': float(entry.current_weight)
            })

            if reference_stock is None:
                reference_stock = entry  # remember first batch used for Sale FK

            remaining_to_sell = round(remaining_to_sell - deduct, 10)

        # reference_stock is guaranteed non-None because we checked total_available > 0
        # Create the Sale record directly — bypasses serializer stock-weight re-validation
        # (stock weights were already deducted above; re-validating would always fail)
        try:
            sale = Sale.objects.create(
                user=request.user,
                stock=reference_stock,
                weight_sold=weight_sold,
                sale_price=sale_price,
            )
        except Exception as e:
            logger.error(f"Sale creation failed: {e}\n{traceback.format_exc()}")
            return Response(
                {'error': f'Failed to record sale: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer = self.get_serializer(sale)
        response_data = dict(serializer.data)
        response_data['fifo_details'] = {
            'message': 'Sold using FIFO (oldest stock first)',
            'entries_used': stock_entries_used,
            'total_deducted': weight_sold,
        }

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    today = timezone.now().date()
    
    total_stock = Stock.objects.filter(is_active=True).aggregate(
        total=Sum('current_weight')
    )['total'] or 0
    
    today_sales_data = Sale.objects.filter(sale_date__date=today).aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    today_revenue = today_sales_data['total_revenue'] or 0
    today_weight = today_sales_data['total_weight'] or 0
    
    low_stock = 0
    stock_by_cut = {}
    for stock in Stock.objects.filter(is_active=True, current_weight__gt=0).select_related('meat_cut'):
        cut_id = stock.meat_cut.id
        if cut_id not in stock_by_cut:
            stock_by_cut[cut_id] = {'total': 0, 'threshold': stock.meat_cut.min_stock_threshold}
        stock_by_cut[cut_id]['total'] += float(stock.current_weight)
    
    for cut_data in stock_by_cut.values():
        if 0 < cut_data['total'] <= cut_data['threshold']:
            low_stock += 1
    
    spoilage_warnings = 0
    for cut_id, data in stock_by_cut.items():
        oldest = Stock.objects.filter(
            meat_cut__id=cut_id,
            is_active=True,
            current_weight__gt=0
        ).order_by('receive_date').first()
        
        if oldest:
            days_old = (timezone.now() - oldest.receive_date).days
            if days_old >= oldest.meat_cut.spoilage_days - 1:
                spoilage_warnings += 1
    
    today_removals = RemovalHistory.objects.filter(removed_at__date=today).aggregate(
        total_weight=Sum('weight_removed'),
        count=Count('id')
    )
    
    recent_sales = Sale.objects.all().order_by('-sale_date')[:10]
    
    data = {
        'total_stock': float(total_stock) if total_stock else 0,
        'total_sales_today': float(today_revenue),
        'total_weight_sold_today': float(today_weight),
        'low_stock_count': low_stock,
        'spoilage_warnings': spoilage_warnings,
        'removals_today': {
            'count': today_removals['count'] or 0,
            'weight': float(today_removals['total_weight']) if today_removals['total_weight'] else 0
        },
        'recent_sales': SaleSerializer(recent_sales, many=True).data
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_alerts(request):
    alerts = []
    stock_by_cut = {}
    
    for stock in Stock.objects.filter(
        is_active=True,
        current_weight__gt=0
    ).select_related('meat_cut'):
        cut_id = stock.meat_cut.id
        if cut_id not in stock_by_cut:
            stock_by_cut[cut_id] = {
                'meat_cut': stock.meat_cut,
                'total_weight': 0,
                'threshold': stock.meat_cut.min_stock_threshold,
                'oldest_date': stock.receive_date,
                'entries': []
            }
        stock_by_cut[cut_id]['total_weight'] += float(stock.current_weight)
        stock_by_cut[cut_id]['entries'].append(stock.id)
        if stock.receive_date < stock_by_cut[cut_id]['oldest_date']:
            stock_by_cut[cut_id]['oldest_date'] = stock.receive_date
    
    for cut_id, data in stock_by_cut.items():
        if 0 < data['total_weight'] <= data['threshold']:
            alerts.append({
                'id': min(data['entries']),
                'meat_cut': data['meat_cut'].name,
                'current_weight': data['total_weight'],
                'threshold': float(data['threshold'])
            })
    
    return Response(alerts)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spoilage_alerts(request):
    alerts = []
    stock_by_cut = {}
    
    for stock in Stock.objects.filter(
        is_active=True,
        current_weight__gt=0
    ).select_related('meat_cut'):
        cut_id = stock.meat_cut.id
        if cut_id not in stock_by_cut:
            stock_by_cut[cut_id] = {
                'meat_cut': stock.meat_cut,
                'oldest_date': stock.receive_date,
                'newest_date': stock.receive_date,
                'total_weight': 0,
                'entries': []
            }
        stock_by_cut[cut_id]['total_weight'] += float(stock.current_weight)
        stock_by_cut[cut_id]['entries'].append(stock)
        if stock.receive_date < stock_by_cut[cut_id]['oldest_date']:
            stock_by_cut[cut_id]['oldest_date'] = stock.receive_date
        if stock.receive_date > stock_by_cut[cut_id]['newest_date']:
            stock_by_cut[cut_id]['newest_date'] = stock.receive_date
    
    for cut_id, data in stock_by_cut.items():
        days_old = (timezone.now() - data['oldest_date']).days
        spoilage_days = data['meat_cut'].spoilage_days
        
        if days_old >= spoilage_days - 1:
            alerts.append({
                'id': min([s.id for s in data['entries']]),
                'meat_cut': data['meat_cut'].name,
                'receive_date': data['oldest_date'],
                'days_old': days_old,
                'spoilage_days': spoilage_days,
                'is_expired': days_old >= spoilage_days,
                'total_weight': data['total_weight']
            })
    
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
    
    day_sales = Sale.objects.filter(
        sale_date__date=target_date
    ).select_related(
        'stock', 
        'stock__meat_cut', 
        'stock__meat_cut__meat_type',
        'user'
    ).order_by('-sale_date')
    
    aggregates = day_sales.aggregate(
        total_revenue=Sum('sale_price'),
        total_weight=Sum('weight_sold')
    )
    
    day_removals = RemovalHistory.objects.filter(removed_at__date=target_date)
    removal_stats = day_removals.aggregate(
        total_weight=Sum('weight_removed'),
        count=Count('id')
    )
    
    sales_by_type = {}
    for sale in day_sales:
        try:
            if sale.stock and sale.stock.meat_cut and sale.stock.meat_cut.meat_type:
                meat_type = sale.stock.meat_cut.meat_type.name
            else:
                meat_type = 'Unknown'
                logger.warning(f"Sale {sale.id} has missing stock relation")
        except Exception as e:
            meat_type = 'Unknown'
            logger.error(f"Error accessing meat_type for sale {sale.id}: {e}")
        
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
        try:
            username = sale.user.username if sale.user else 'Unknown'
        except:
            username = 'Unknown'
        
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
            'total_revenue': float(aggregates['total_revenue']) if aggregates['total_revenue'] else 0,
            'total_weight_sold': float(aggregates['total_weight']) if aggregates['total_weight'] else 0,
            'total_transactions': day_sales.count(),
        },
        'removals': {
            'total_weight': float(removal_stats['total_weight']) if removal_stats['total_weight'] else 0,
            'count': removal_stats['count'] or 0,
            'details': RemovalHistorySerializer(day_removals, many=True).data
        },
        'sales_by_type': sales_by_type,
        'sales_by_user': sales_by_user,
        'transactions': SaleSerializer(day_sales, many=True).data
    }
    
    return Response(data)