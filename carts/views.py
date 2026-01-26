from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from store.models import Product, Variation
from .models import Cart, CartItem
from django.contrib import messages

MAX_PER_PRODUCT = 10

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart

def add_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variations = []

    # ---------------- GET VARIATIONS ----------------
    if request.method == "POST":
        for key, value in request.POST.items():
            try:
                variations.append(
                    Variation.objects.get(
                        product=product,
                        variation_category__iexact=key,
                        variation_value__iexact=value,
                    )
                )
            except Variation.DoesNotExist:
                pass

    # ================= AUTH USER =================
    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(
            user=request.user, product=product, is_active=True
        )

        total_qty = cart_items.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        # ---- GLOBAL LIMITS ----
        if total_qty >= product.stock or total_qty >= MAX_PER_PRODUCT:
            return redirect("cart")

        # ---- SAME VARIATION ----
        for item in cart_items:
            if list(item.variations.all()) == variations:
                if item.quantity >= MAX_PER_PRODUCT:
                    return redirect("cart")

                if total_qty + 1 > product.stock:
                    return redirect("cart")

                item.quantity += 1
                item.save()
                return redirect("cart")

        # ---- CREATE NEW ----
        cart_item = CartItem.objects.create(
            user=request.user,
            product=product,
            quantity=1,
        )
        if variations:
            cart_item.variations.add(*variations)

        return redirect("cart")

    # ================= GUEST USER =================
    cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))

    cart_items = CartItem.objects.filter(
        cart=cart, product=product, is_active=True
    )

    total_qty = cart_items.aggregate(
        total=Sum("quantity")
    )["total"] or 0

    # ---- GLOBAL LIMITS ----
    if total_qty >= product.stock or total_qty >= MAX_PER_PRODUCT:
        return redirect("cart")

    # ---- SAME VARIATION ----
    for item in cart_items:
        if list(item.variations.all()) == variations:
            if item.quantity >= MAX_PER_PRODUCT:
                return redirect("cart")

            if total_qty + 1 > product.stock:
                return redirect("cart")

            item.quantity += 1
            item.save()
            return redirect("cart")

    # ---- CREATE NEW ----
    cart_item = CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=1,
    )
    if variations:
        cart_item.variations.add(*variations)

    return redirect("cart")


# ---------------- REMOVE ONE ----------------
def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)

    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(
                product=product, user=request.user, id=cart_item_id
            )
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(
                product=product, cart=cart, id=cart_item_id
            )

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except:
        pass

    return redirect("cart")


# ---------------- REMOVE ITEM ----------------
def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(
            product=product, user=request.user, id=cart_item_id
        )
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(
            product=product, cart=cart, id=cart_item_id
        )

    cart_item.delete()
    return redirect("cart")


# ---------------- CART VIEW ----------------
def cart(request):
    total = Decimal("0.00")
    discount_total = Decimal("0.00")
    quantity = 0
    tax = Decimal("0.00")
    grand_total = Decimal("0.00")

    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        for item in cart_items:
            original_price = item.product.price
            discounted_price = item.product.get_discounted_price()
            total += discounted_price * item.quantity
            discount_total += (original_price - discounted_price) * item.quantity
            quantity += item.quantity

        tax = total * Decimal("0.02")
        grand_total = total + tax

    except ObjectDoesNotExist:
        cart_items = []

    context = {
        "total": total,
        "discount_total": discount_total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,
    }

    return render(request, "store/cart.html", context)


# ---------------- CHECKOUT ----------------
@login_required(login_url="login")
def checkout(request):
    total = Decimal("0.00")
    discount_total = Decimal("0.00")
    quantity = 0
    tax = Decimal("0.00")
    grand_total = Decimal("0.00")

    try:
        cart_items = CartItem.objects.filter(user=request.user, is_active=True)

        for item in cart_items:
            original_price = item.product.price
            discounted_price = item.product.get_discounted_price()
            total += discounted_price * item.quantity
            discount_total += (original_price - discounted_price) * item.quantity
            quantity += item.quantity

        tax = total * Decimal("0.02")
        grand_total = total + tax

    except ObjectDoesNotExist:
        cart_items = []

    context = {
        "total": total,
        "discount_total": discount_total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,
    }

    return render(request, "store/checkout.html", context)
