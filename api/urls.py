from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    UserViewSet, CompanyViewSet, ProductViewSet, 
    CustomerViewSet, SaleViewSet, LoanViewSet,
    DashboardStatsView, RevenueReportView, TrashView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'companies', CompanyViewSet)
router.register(r'products', ProductViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'loans', LoanViewSet)

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('reports/revenue/', RevenueReportView.as_view(), name='revenue_report'),
    path('trash/', TrashView.as_view(), name='trash'),
    path('', include(router.urls)),
]
