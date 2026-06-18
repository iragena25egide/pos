from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.db.models import Sum, Count, F
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
    queryset = Sale.objects.select_related('customer', 'user').prefetch_related('items__product').all().order_by('-created_at')
    serializer_class = SaleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

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

        existing_loan = Loan.objects.select_for_update().filter(customer=customer, is_deleted=False).first()

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
            product = Product.objects.select_for_update().get(id=item['product_id'])
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

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        sale = self.get_object()
        
        # 1. Reverse old sale items impact on stock
        old_items = sale.items.all()
        for item in old_items:
            product = Product.objects.select_for_update().get(id=item.product_id)
            product.stock_quantity += item.quantity
            product.save()

        # 2. Reverse old sale impact on loan
        old_balance = sale.balance
        if old_balance > 0:
            loan = Loan.objects.select_for_update().filter(customer=sale.customer, is_deleted=False).first()
            if loan:
                loan.total_debt -= old_balance
                if loan.total_debt < 0:
                    loan.total_debt = Decimal('0.00')
                loan.save()

        # 3. Delete old items
        old_items.delete()

        # 4. Process new data
        customer_id = request.data.get('customer_id', sale.customer_id)
        items_data = request.data.get('items', [])
        payment_amount = Decimal(str(request.data.get('payment_amount', sale.payment_amount)))
        
        if not items_data:
            return Response({'error': 'No items in sale.'}, status=status.HTTP_400_BAD_REQUEST)

        if customer_id != sale.customer_id:
            try:
                sale.customer = Customer.objects.get(id=customer_id, is_deleted=False)
            except Customer.DoesNotExist:
                return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        total_amount = Decimal('0.00')
        for item in items_data:
            total_amount += Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))

        new_balance = total_amount - payment_amount

        sale.total_amount = total_amount
        sale.payment_amount = payment_amount
        sale.save()

        # 5. Apply new items and deduct stock
        for item in items_data:
            product_id = item.get('product_id')
            if not product_id and 'product' in item:
                product_id = item['product']
                
            product = Product.objects.select_for_update().get(id=product_id)
            qty = int(item['quantity'])
            unit_price = Decimal(str(item['unit_price']))
            
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=qty,
                unit_price=unit_price
            )
            product.stock_quantity -= qty
            product.save()

        # 6. Apply new loan balance
        if new_balance > 0:
            loan = Loan.objects.select_for_update().filter(customer=sale.customer, is_deleted=False).first()
            if loan:
                loan.total_debt += new_balance
                loan.save()
            else:
                Loan.objects.create(customer=sale.customer, total_debt=new_balance)

        serializer = self.get_serializer(sale)
        return Response(serializer.data)

class LoanViewSet(SoftDeleteModelViewSet):
    queryset = Loan.objects.select_related('customer').all().order_by('-created_at')
    serializer_class = LoanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def settle(self, request, pk=None):
        loan = self.get_object()
        payment = Decimal(request.data.get('payment_amount', '0.00'))
        
        if payment <= 0:
            return Response({'error': 'Payment must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)

        # Distribute the payment across unpaid sales (oldest first)
        unpaid_sales = Sale.objects.filter(
            customer=loan.customer,
            is_deleted=False
        ).exclude(
            payment_amount__gte=F('total_amount')
        ).order_by('created_at')

        remaining_payment = payment
        for sale in unpaid_sales:
            if remaining_payment <= 0:
                break
                
            sale_balance = sale.total_amount - sale.payment_amount
            if remaining_payment >= sale_balance:
                sale.payment_amount += sale_balance
                remaining_payment -= sale_balance
            else:
                sale.payment_amount += remaining_payment
                remaining_payment = Decimal('0.00')
            
            sale.save()
        
        # Update the loan itself
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
