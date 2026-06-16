from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.db.models import Sum, Count
from .models import User, Company, Product, Customer, Sale, SaleItem, Loan
from .serializers import (
    UserSerializer, CompanySerializer, ProductSerializer,
    CustomerSerializer, SaleSerializer, LoanSerializer
)
from decimal import Decimal

class SoftDeleteModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return self.queryset.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        try:
            instance = self.queryset.model.objects.get(pk=pk)
            instance.restore()
            return Response({'status': 'restored'})
        except self.queryset.model.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['delete'])
    def force_delete(self, request, pk=None):
        try:
            instance = self.queryset.model.objects.get(pk=pk)
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except self.queryset.model.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        role = request.data.get('role', 'cashier')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.set_password(password)
        user.save()

        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class CompanyViewSet(SoftDeleteModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class ProductViewSet(SoftDeleteModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class CustomerViewSet(SoftDeleteModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            customers = Customer.objects.filter(name__icontains=query, is_deleted=False)
        else:
            customers = Customer.objects.filter(is_deleted=False)
        serializer = self.get_serializer(customers, many=True)
        return Response(serializer.data)

class SaleViewSet(SoftDeleteModelViewSet):
    queryset = Sale.objects.all().order_by('-created_at')
    serializer_class = SaleSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        customer_id = request.data.get('customer_id')
        customer_name = request.data.get('customer_name')
        customer_address = request.data.get('customer_address')
        items_data = request.data.get('items', [])
        payment_amount = Decimal(request.data.get('payment_amount', '0.00'))
        confirm_loan = request.data.get('confirm_loan', False)

        if not items_data:
            return Response({'error': 'No items in sale.'}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = Decimal('0.00')
        for item in items_data:
            total_amount += Decimal(item['quantity']) * Decimal(item['unit_price'])

        balance = total_amount - payment_amount

        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, is_deleted=False)
                if customer_address and not customer.address:
                    customer.address = customer_address
                    customer.save()
            except Customer.DoesNotExist:
                return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        elif customer_name:
            customer = Customer.objects.filter(name=customer_name, is_deleted=False).first()
            if not customer:
                customer = Customer.objects.create(name=customer_name, address=customer_address)
            elif customer_address and not customer.address:
                customer.address = customer_address
                customer.save()
        else:
            return Response({'error': 'Customer name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        existing_loan = Loan.objects.filter(customer=customer, is_deleted=False).first()

        if balance > 0 and existing_loan and existing_loan.total_debt > 0 and not confirm_loan:
            return Response({
                'requires_confirmation': True,
                'message': f"This customer already has an outstanding debt of ${existing_loan.total_debt}. Do you want to add the new debt to the existing balance?",
                'existing_debt': existing_loan.total_debt,
                'new_debt': balance
            }, status=status.HTTP_409_CONFLICT)

        sale = Sale.objects.create(
            customer=customer,
            user=request.user if request.user.is_authenticated else None,
            total_amount=total_amount,
            payment_amount=payment_amount
        )

        for item in items_data:
            product = Product.objects.get(id=item['product_id'])
            qty = int(item['quantity'])
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=qty,
                unit_price=Decimal(item['unit_price'])
            )
            product.stock_quantity -= qty
            product.save()

        if balance > 0:
            if existing_loan:
                existing_loan.total_debt += balance
                existing_loan.save()
            else:
                Loan.objects.create(customer=customer, total_debt=balance)

        serializer = self.get_serializer(sale)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class LoanViewSet(SoftDeleteModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        loan = self.get_object()
        payment = Decimal(request.data.get('payment_amount', '0.00'))
        
        if payment <= 0:
            return Response({'error': 'Payment must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if payment >= loan.total_debt:
            loan.total_debt = Decimal('0.00')
            loan.status = 'Paid'
            loan.save()
            return Response({'message': 'Loan fully settled.', 'status': loan.status, 'remaining_debt': loan.total_debt})
        else:
            loan.total_debt -= payment
            loan.status = 'Pending'
            loan.save()
            return Response({'message': 'Partial payment received.', 'status': loan.status, 'remaining_debt': loan.total_debt})

class TrashView(views.APIView):
    def get(self, request):
        def format_item(item, type_name):
            return {
                'id': item.id,
                'type': type_name,
                'name': str(item),
                'deleted_at': item.deleted_at
            }
        
        trash = []
        trash.extend([format_item(i, 'company') for i in Company.objects.filter(is_deleted=True)])
        trash.extend([format_item(i, 'product') for i in Product.objects.filter(is_deleted=True)])
        trash.extend([format_item(i, 'customer') for i in Customer.objects.filter(is_deleted=True)])
        trash.extend([format_item(i, 'sale') for i in Sale.objects.filter(is_deleted=True)])
        trash.extend([format_item(i, 'loan') for i in Loan.objects.filter(is_deleted=True)])
        
        trash.sort(key=lambda x: x['deleted_at'] or timezone.now(), reverse=True)
        return Response(trash)

class DashboardStatsView(views.APIView):
    def get(self, request):
        total_companies = Company.objects.filter(is_deleted=False).count()
        total_products = Product.objects.filter(is_deleted=False).count()
        total_customers = Customer.objects.filter(is_deleted=False).count()
        total_sales = Sale.objects.filter(is_deleted=False).count()
        
        total_revenue = Sale.objects.filter(is_deleted=False).aggregate(total=Sum('payment_amount'))['total'] or Decimal('0.00')
        total_outstanding_loans = Loan.objects.filter(is_deleted=False).aggregate(total=Sum('total_debt'))['total'] or Decimal('0.00')

        recent_sales = SaleSerializer(Sale.objects.filter(is_deleted=False).order_by('-created_at')[:5], many=True).data
        recent_loans = LoanSerializer(Loan.objects.filter(is_deleted=False).order_by('-created_at')[:5], many=True).data

        return Response({
            'total_companies': total_companies,
            'total_products': total_products,
            'total_customers': total_customers,
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'total_outstanding_loans': total_outstanding_loans,
            'recent_sales': recent_sales,
            'recent_loans': recent_loans
        })

class RevenueReportView(views.APIView):
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        sales_query = SaleItem.objects.filter(sale__is_deleted=False, product__is_deleted=False)
        if start_date:
            sales_query = sales_query.filter(sale__created_at__gte=start_date)
        if end_date:
            sales_query = sales_query.filter(sale__created_at__lte=end_date)

        from django.db.models import F, Sum, DecimalField
        company_stats = sales_query.values(
            company_id=F('product__company__id'),
            company_name=F('product__company__name')
        ).annotate(
            total_sales_value=Sum(F('quantity') * F('unit_price'), output_field=DecimalField()),
            items_sold=Sum('quantity')
        )

        return Response(list(company_stats))
