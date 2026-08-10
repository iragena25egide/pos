from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import User, Company, Product, Customer, Sale, Loan

class SaleAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123', role='cashier')
        self.company = Company.objects.create(name='Test Company')
        self.product = Product.objects.create(company=self.company, name='Test Product', price=10.00, stock_quantity=100)
        self.customer = Customer.objects.create(name='Test Customer')
        self.client.force_authenticate(user=self.user)
        self.sale_url = reverse('sale-list')

    def test_create_sale_successful(self):
        data = {
            'customer_id': self.customer.id,
            'payment_amount': '15.00',
            'items': [
                {'product_id': self.product.id, 'quantity': 2, 'unit_price': '10.00'}
            ]
        }
        response = self.client.post(self.sale_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check stock deduction
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 98)
        
        # Check loan creation (Total amount 20, paid 15 => balance 5)
        loan = Loan.objects.get(customer=self.customer)
        self.assertEqual(loan.total_debt, 5.00)

    def test_create_sale_insufficient_stock(self):
        data = {
            'customer_id': self.customer.id,
            'payment_amount': '0.00',
            'items': [
                {'product_id': self.product.id, 'quantity': 200, 'unit_price': '10.00'}
            ]
        }
        response = self.client.post(self.sale_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(response.data))
        
        # Check stock unchanged
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 100)
