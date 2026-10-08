from rest_framework import serializers
from .models import User, Company, Product, Customer, Sale, SaleItem, Loan, Payment, SupportMessage
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'company', 'company_name', 'is_approved', 'phone', 'is_superuser']
        extra_kwargs = {
            'username': {'allow_blank': False},
            'email': {'allow_blank': False},
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # Superadmins bypass approval requirement
        if not self.user.is_superuser:
            if not self.user.is_approved:
                raise serializers.ValidationError({"detail": "Your account is pending Super Admin approval. Please contact system administrator."})
            if self.user.company and not self.user.company.is_approved:
                raise serializers.ValidationError({"detail": "Your company workspace is pending Super Admin approval."})

        # Return only standard JWT authentication tokens without leaking sensitive company/user fields
        return {
            'access': data['access'],
            'refresh': data['refresh'],
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = getattr(user, 'role', '')
        token['is_superuser'] = user.is_superuser
        token['company_id'] = user.company.id if user.company else None
        return token

class CompanySerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()
    total_transactions_amount = serializers.SerializerMethodField()
    total_sales_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = '__all__'
        extra_kwargs = {
            'name': {'allow_blank': False},
        }

    def get_users_count(self, obj):
        return obj.users.count()

    def get_total_transactions_amount(self, obj):
        from decimal import Decimal
        from django.db.models import Sum
        val = obj.sales.filter(is_deleted=False).aggregate(total=Sum('total_amount'))['total']
        return str(val or Decimal('0.00'))

    def get_total_sales_count(self, obj):
        return obj.sales.filter(is_deleted=False).count()

class ProductSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'company', 'company_name', 'name', 'description', 'price', 'stock_quantity', 'created_at']
        extra_kwargs = {
            'name': {'allow_blank': False},
            'price': {'min_value': 0},
            'stock_quantity': {'min_value': 0},
        }

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
        extra_kwargs = {
            'name': {'allow_blank': False},
        }

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['subtotal']
        extra_kwargs = {
            'quantity': {'min_value': 1},
            'unit_price': {'min_value': 0},
        }

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    remaining_debt = serializers.DecimalField(source='customer.loan.total_debt', max_digits=12, decimal_places=2, read_only=True, required=False, allow_null=True)
    salesperson_name = serializers.CharField(source='user.username', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_address = serializers.CharField(source='company.address', read_only=True)
    company_phone = serializers.CharField(source='company.contact_phone', read_only=True)
    company_tin = serializers.CharField(source='company.tin_number', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'company', 'company_name', 'company_address', 'company_phone', 'company_tin',
            'customer', 'customer_name', 'user', 'salesperson_name',
            'total_amount', 'payment_amount', 'balance', 'created_at', 'items', 'remaining_debt'
        ]
        extra_kwargs = {
            'total_amount': {'min_value': 0},
            'payment_amount': {'min_value': 0},
        }

    def validate(self, data):
        # Cross-field validation example
        payment_amount = data.get('payment_amount', 0)
        total_amount = data.get('total_amount', 0)
        if payment_amount > total_amount:
            raise serializers.ValidationError({"payment_amount": "Payment amount cannot exceed the total sale amount."})
        return data

class LoanSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    remaining_debt = serializers.DecimalField(source='customer.loan.total_debt', max_digits=12, decimal_places=2, read_only=True, required=False, allow_null=True)

    class Meta:
        model = Loan
        fields = '__all__'
        extra_kwargs = {
            'total_debt': {'min_value': 0},
        }

class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    remaining_debt = serializers.DecimalField(source='customer.loan.total_debt', max_digits=12, decimal_places=2, read_only=True, required=False, allow_null=True)

    class Meta:
        model = Payment
        fields = '__all__'
        extra_kwargs = {
            'amount': {'min_value': 0.01},
        }


class SupportMessageSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_id = serializers.IntegerField(source='company.id', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = [
            'id', 'company', 'company_id', 'company_name', 'sender', 'sender_name',
            'sender_role', 'message', 'attachment', 'attachment_url',
            'is_admin', 'is_read', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company_id', 'created_at', 'updated_at', 'company_name', 'attachment_url']

    def get_attachment_url(self, obj):
        if obj.attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            url = obj.attachment.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            return f"https://194.164.72.181.nip.io{url}" if url.startswith('/') else f"https://194.164.72.181.nip.io/{url}"
        return None
