from django.db import models
from store.models import Product, ReviewRating
from django.contrib.auth import get_user_model


class ProductReport(Product):
    class Meta:
        proxy = True
        verbose_name = 'Product Report'
        verbose_name_plural = 'Product Reports'

class SalesSummary(models.Model):
    title = models.CharField(max_length=100, default="Sales Summary")
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        verbose_name = "Sales Summary"
        verbose_name_plural = "Sales Summary"

    def __str__(self):
        return self.title
    

# Proxy model for reporting
class ReviewRatingReport(ReviewRating):
    class Meta:
        proxy = True
        verbose_name = "Review Rating Report"
        verbose_name_plural = "Review Rating Reports"

User = get_user_model()

class TopCustomerReport(User):
    class Meta:
        proxy = True
        verbose_name = "Top Customer Report"
        verbose_name_plural = "Top Customers Report"

    def __str__(self):
        return self.email or self.username
    


class LowStockReport(Product):
    class Meta:
        proxy = True
        verbose_name = "Low Stock Report"
        verbose_name_plural = "Low Stock Reports"


