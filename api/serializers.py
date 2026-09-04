from rest_framework import serializers
from .models import User, Company, Product, Customer, Sale, SaleItem, Loan, Payment
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name']
        extra_kwargs = {
            'username': {'allow_blank': False},
            'email': {'allow_blank': False},
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = getattr(user, 'role', '')
        return token

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        extra_kwargs = {
            'name': {'allow_blank': False},
        }

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

    class Meta:
        model = Sale
        fields = ['id', 'customer', 'customer_name', 'user', 'salesperson_name', 'total_amount', 'payment_amount', 'balance', 'created_at', 'items', 'remaining_debt']
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
