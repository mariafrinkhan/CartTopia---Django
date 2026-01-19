from django.db import models
from accounts.models import Account
from store.models import Product, Variation

class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_paid = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id
    
class Order(models.Model):
    STATUS = (
        ('Accepted', 'Accepted'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )

    DELIVERY_CHOICES = [
        ("inside", "Inside Dhaka"),
        ("outside", "Outside Dhaka"),
    ]

    delivery_area = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default="inside"
    )
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=80
    )

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    order_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    email = models.EmailField(max_length=50)
    address_line_1 = models.CharField(max_length=100)
    address_line_2 = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    order_note = models.TextField(blank=True)
    order_total = models.FloatField()
    tax = models.FloatField()
    status = models.CharField(max_length=10, choices=STATUS, default='Accepted')
    ip = models.CharField(blank=True, max_length=20)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_delivery = models.DateField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.estimated_delivery and self.status == 'Accepted':
            # Example: delivery 5 days for inside Dhaka, 7 for outside
            from datetime import timedelta, date
            days = 5 if self.delivery_area == 'inside' else 7
            self.estimated_delivery = date.today() + timedelta(days=days)
        super().save(*args, **kwargs)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'

    def __str__(self):
        return self.first_name
    
class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variations = models.ManyToManyField(Variation, blank=True)
    # color = models.CharField(max_length=50)
    # size = models.CharField(max_length=50)
    quantity = models.IntegerField()
    product_price = models.FloatField()
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # discounted price
    discount_percent = models.IntegerField(default=0)


    def __str__(self):
        return self.product.product_name