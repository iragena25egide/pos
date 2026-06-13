import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Company, Product, Customer, Sale, Loan

class Command(BaseCommand):
    help = 'Seeds the database with test data for POS'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Clearing existing non-auth data..."))
        Loan.objects.all().delete()
        Sale.objects.all().delete()
        Product.objects.all().delete()
        Company.objects.all().delete()
        Customer.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Seeding Companies..."))
        companies = []
        for name in ["Apple Inc", "Samsung Electronics", "Sony", "LG", "Microsoft"]:
            companies.append(Company.objects.create(name=name, contact_email=f"contact@{name.lower().replace(' ', '')}.com"))

        self.stdout.write(self.style.SUCCESS("Seeding Products..."))
        products = []
        product_names = [
            ("MacBook Pro 16", "Apple Inc", 2500),
            ("iPhone 15 Pro", "Apple Inc", 999),
            ("Galaxy S24 Ultra", "Samsung Electronics", 1200),
            ("PlayStation 5", "Sony", 450),
            ("LG OLED TV 65", "LG", 1500),
            ("Surface Pro 9", "Microsoft", 1000),
            ("AirPods Pro", "Apple Inc", 200),
        ]
        
        for p_name, c_name, price in product_names:
            company = next(c for c in companies if c.name == c_name)
            products.append(Product.objects.create(
                name=p_name,
                company=company,
                price=price,
                stock_quantity=random.randint(10, 50)
            ))

        self.stdout.write(self.style.SUCCESS("Seeding Customers..."))
        customers = []
        for name in ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Egide N"]:
            customers.append(Customer.objects.create(
                name=name,
                phone=f"+1-555-{random.randint(1000, 9999)}",
                email=f"{name.split()[0].lower()}@example.com"
            ))

        self.stdout.write(self.style.SUCCESS("Seeding Sales & Loans..."))
        now = timezone.now()
        for i in range(20):
            customer = random.choice(customers)
            product = random.choice(products)
            quantity = random.randint(1, 3)
            total_amount = product.price * quantity
            
            # Make some sales fully paid, some partial (loans)
            is_loan = random.choice([True, False, False]) # 33% chance of loan
            
            if is_loan:
                payment_amount = total_amount * random.uniform(0.1, 0.8) # 10% to 80% paid
            else:
                payment_amount = total_amount

            # Create sale
            # Create a date in the past 30 days
            past_date = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            sale = Sale.objects.create(
                customer=customer,
                total_amount=total_amount,
                payment_amount=payment_amount
            )
            # Update timestamps bypassing auto_now_add for realistic reporting data
            Sale.objects.filter(id=sale.id).update(created_at=past_date)
            
            sale.items.create(
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )
            
            # If it's a loan, update the cumulative customer loan record
            if payment_amount < total_amount:
                debt = total_amount - payment_amount
                loan, created = Loan.objects.get_or_create(customer=customer)
                loan.total_debt = float(loan.total_debt) + float(debt)
                loan.save()
                
            # Simulate stock reduction
            product.stock_quantity -= quantity
            product.save()

        self.stdout.write(self.style.SUCCESS("Successfully seeded database with test data!"))
