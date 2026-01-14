from django.db import models
from decimal import Decimal
from accounts.models import Account
from store.models import Product, Variation


class Cart(models.Model):
    cart_id = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cart_id

class CartItem(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variations = models.ManyToManyField(Variation, blank=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def discounted_price(self):
        """
        Returns per-item price AFTER discount
        """
        price = self.product.price
        discount = self.product.discount_percent

        if discount > 0:
            return price - (price * Decimal(discount) / Decimal(100))
        return price

    def sub_total(self):
        """
        Returns total price for this cart item (price * quantity)
        """
        return self.discounted_price() * self.quantity

    def __unicode__(self):
        return self.product