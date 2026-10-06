from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, CompanyViewSet, ProductViewSet,
    CustomerViewSet, SaleViewSet, LoanViewSet,
    PaymentViewSet, DashboardStatsView, RevenueReportView, TrashView,
    CustomTokenObtainPairView, GoogleAuthView,
    SupportMessageViewSet, AdminMetricsView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'companies', CompanyViewSet)
router.register(r'products', ProductViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'loans', LoanViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'support-messages', SupportMessageViewSet)

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/google/', GoogleAuthView.as_view(), name='google_auth'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('admin/metrics/', AdminMetricsView.as_view(), name='admin_metrics'),
    path('reports/revenue/', RevenueReportView.as_view(), name='revenue_report'),
    path('trash/', TrashView.as_view(), name='trash'),
    path('', include(router.urls)),
]
