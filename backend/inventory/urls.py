from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'meat-types', views.MeatTypeViewSet)
router.register(r'meat-cuts', views.MeatCutViewSet)
router.register(r'stock', views.StockViewSet, basename='stock')
router.register(r'sales', views.SaleViewSet, basename='sale')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.dashboard_stats, name='dashboard'),
    path('alerts/low-stock/', views.low_stock_alerts, name='low-stock-alerts'),
    path('alerts/spoilage/', views.spoilage_alerts, name='spoilage-alerts'),
    path('reports/daily/', views.daily_report, name='daily-report'),
]