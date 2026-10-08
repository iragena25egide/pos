from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from simple_history.models import HistoricalRecords


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class Company(SoftDeleteModel):
    name = models.CharField(max_length=255, db_index=True)
    ceo_founder = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True, null=True)
    tin_number = models.CharField(max_length=50, blank=True, null=True, help_text="Tax Identification Number")
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('company_admin', 'Company Admin'),
        ('cashier', 'Cashier'),
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='company_admin')
    company = models.ForeignKey(
        Company, related_name='users', on_delete=models.SET_NULL, null=True, blank=True)
    is_approved = models.BooleanField(default=False, db_index=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    owner_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tin_number = models.CharField(max_length=50, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.email} - {self.otp}"


class Product(SoftDeleteModel):
    company = models.ForeignKey(
        Company, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.name} - {self.company.name if self.company else 'Global'}"


class Customer(SoftDeleteModel):
    company = models.ForeignKey(
        Company, related_name='customers', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name


class Sale(SoftDeleteModel):
    company = models.ForeignKey(
        Company, related_name='sales', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    customer = models.ForeignKey(
        Customer, related_name='sales', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='sales',
                             on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    payment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    history = HistoricalRecords()

    @property
    def balance(self):
        return self.total_amount - self.payment_amount

    def __str__(self):
        return f"Sale {self.id} - {self.customer.name}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items',
                             on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Loan(SoftDeleteModel):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    ]
    company = models.ForeignKey(
        Company, related_name='loans', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    customer = models.OneToOneField(
        Customer, related_name='loan', on_delete=models.CASCADE)
    total_debt = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if self.total_debt is not None and self.total_debt > 0:
            self.status = 'Pending'
        else:
            self.status = 'Paid'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Loan - {self.customer.name} - ${self.total_debt}"


class Payment(SoftDeleteModel):
    PAYMENT_TYPE_CHOICES = (
        ('SALE', 'Sale'),
        ('LOAN_PAYMENT', 'Loan Payment'),
    )
    company = models.ForeignKey(
        Company, related_name='payments', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    customer = models.ForeignKey(Customer, related_name='payments', on_delete=models.CASCADE, null=True, blank=True)
    client_name = models.CharField(max_length=255, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='SALE')
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.client_name} - ${self.amount} on {self.date.strftime('%Y-%m-%d %H:%M')}"


class SupportMessage(models.Model):
    company = models.ForeignKey(
        Company, related_name='support_messages', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    sender = models.ForeignKey(
        User, related_name='sent_support_messages', on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=255)
    sender_role = models.CharField(max_length=50, default='company_admin')
    message = models.TextField(blank=True, default='')
    attachment = models.FileField(upload_to='support_attachments/', null=True, blank=True)
    is_admin = models.BooleanField(default=False, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        prefix = "ADMIN" if self.is_admin else f"COMPANY ({self.company.name if self.company else 'Global'})"
        return f"[{prefix}] {self.sender_name}: {self.message[:30]}"
