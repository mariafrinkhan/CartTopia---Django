import datetime
from decimal import Decimal
from django.contrib import messages
import json
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from carts.models import CartItem
from orders.models import Order, Payment, OrderProduct
from .forms import OrderForm
from store.models import Product

import requests
from django.conf import settings
from django.contrib.auth import login


def payments(request):
    return render(request, 'orders/payments.html')


def place_order(request):
    current_user = request.user

    # Get cart items
    cart_items = CartItem.objects.filter(user=current_user, is_active=True)
    if not cart_items.exists():
        messages.error(request, "Your cart is empty!")
        return redirect('store')

    # Calculate total and quantity using discounted price
    total = sum(
        (item.product.get_discounted_price() if item.product.discount_percent > 0 else item.product.price) 
        * item.quantity
        for item in cart_items
    )
    quantity = sum(item.quantity for item in cart_items)
    tax = total * Decimal('0.02')  # 2% tax

    # Default delivery
    delivery_area = "inside"
    DELIVERY_CHARGES = {
        "inside": Decimal('80'),
        "outside": Decimal('140')
    }
    delivery_charge = DELIVERY_CHARGES[delivery_area]
    grand_total = total + tax + delivery_charge

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Get delivery area from form
            delivery_area = form.cleaned_data.get('delivery_area', 'inside')
            if delivery_area not in DELIVERY_CHARGES:
                delivery_area = 'inside'
            delivery_charge = DELIVERY_CHARGES[delivery_area]
            grand_total = total + tax + delivery_charge

            # Create order
            order = Order.objects.create(
                user=current_user,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                phone=form.cleaned_data['phone'],
                email=form.cleaned_data['email'],
                address_line_1=form.cleaned_data['address_line_1'],
                address_line_2=form.cleaned_data['address_line_2'],
                country=form.cleaned_data['country'],
                state=form.cleaned_data['state'],
                city=form.cleaned_data['city'],
                order_note=form.cleaned_data.get('order_note', ''),
                order_total=grand_total,
                tax=tax,
                delivery_area=delivery_area,
                delivery_charge=delivery_charge,
                ip=request.META.get('REMOTE_ADDR'),
            )

            # Generate order number
            current_date = datetime.date.today().strftime("%Y%m%d")
            order.order_number = f"{current_date}{order.id}"
            order.save()

            context = {
                'order': order,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'delivery_charge': delivery_charge,
                'grand_total': grand_total,
                'delivery_area': delivery_area,
            }

            return render(request, 'orders/payments.html', context)
    else:
        messages.error(request, "Invalid request!")
        return redirect('checkout')


def sslcommerz_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user, is_ordered=False)

    url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php" if settings.SSLCOMMERZ['sandbox'] else "https://securepay.sslcommerz.com/gwprocess/v4/api.php"

    payload = {
        'store_id': settings.SSLCOMMERZ['store_id'],
        'store_passwd': settings.SSLCOMMERZ['store_password'],
        'total_amount': float(order.order_total),
        'currency': 'BDT',
        'tran_id': order.order_number,
        'success_url': f'http://127.0.0.1:8000/orders/ssl-success/?order_number={order.order_number}',
        'fail_url': 'http://127.0.0.1:8000/orders/ssl-fail/',
        'cancel_url': 'http://127.0.0.1:8000/orders/ssl-cancel/',
        'cus_name': order.full_name(),
        'cus_email': order.email,
        'cus_phone': order.phone,
        'cus_add1': order.address_line_1,
        'cus_city': order.city,
        'cus_country': order.country,
        'shipping_method': 'NO',
        'product_name': 'CartTopia Order',
        'product_category': 'Ecommerce',
        'product_profile': 'general',
    }

    response = requests.post(url, data=payload)
    data = response.json()
    return redirect(data.get('GatewayPageURL', '/store/'))


@csrf_exempt
def ssl_success(request):
    data = {}
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
    else:
        data = request.GET

    order_number = data.get('order_number') or data.get('tran_id')
    tran_id = data.get('tran_id')
    val_id = data.get('val_id')
    status = data.get('status')
    amount = data.get('amount')

    if not order_number:
        return HttpResponse("Order number missing!", status=400)

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=False)
    except Order.DoesNotExist:
        return HttpResponse("Order not found!", status=404)

    payment_id = val_id or tran_id or f"PAY-{order_number}"

    payment = Payment.objects.create(
        user=order.user,
        payment_id=payment_id,
        payment_method='SSLCommerz',
        amount_paid=Decimal(amount) if amount else order.order_total,
        status=status or "Success",
    )

    order.payment = payment
    order.is_ordered = True
    order.save()

    cart_items = CartItem.objects.filter(user=order.user)
    for item in cart_items:
        product_price = item.product.get_discounted_price() if item.product.discount_percent > 0 else item.product.price
        discounted_price = item.product.price * (Decimal(100 - item.product.discount_percent) / Decimal(100))
        order_product = OrderProduct.objects.create(
            order=order,
            payment=payment,
            user=item.user,
            product=item.product,
            quantity=item.quantity,
            product_price=discounted_price,
            original_price=item.product.price,
            discount_percent=item.product.discount_percent,
            ordered=True,
        )
        if item.variations.exists():
            order_product.variations.set(item.variations.all())
        order_product.save()

        # Reduce stock
        item.product.stock -= item.quantity
        item.product.save()

    cart_items.delete()

    # Send confirmation email
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_recieved_email.html', {'user': order.user, 'order': order})
    EmailMessage(mail_subject, message, to=[order.user.email]).send()

    subtotal = sum([p.product_price * p.quantity for p in OrderProduct.objects.filter(order=order)])

    return render(request, 'orders/order_complete.html', {
        'order': order,
        'ordered_products': OrderProduct.objects.filter(order=order),
        'order_number': order.order_number,
        'transID': payment.payment_id,
        'payment': payment,
        'subtotal': subtotal,
    })


@csrf_exempt
def ssl_fail(request):
    return HttpResponse(
        "<h2>Payment Failed!</h2>"
        "<p>Your payment could not be processed. Please try again.</p>"
        '<a href="/store/">Go Back to Store</a>',
        content_type="text/html"
    )


@csrf_exempt
def ssl_cancel(request):
    return HttpResponse(
        "<h2>Payment Canceled!</h2>"
        "<p>You canceled the payment. Your order has not been completed.</p>"
        '<a href="/store/">Go Back to Store</a>',
        content_type="text/html"
    )


def after_order_login(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        return redirect('store')

    user = order.user
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    return redirect('store')
