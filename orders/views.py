import datetime
import json
from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse

from carts.models import CartItem
from orders.models import Order, Payment, OrderProduct
from .forms import OrderForm
from store.models import Product

import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import JsonResponse

from django.contrib.auth import login
from django.contrib.auth.backends import ModelBackend


def payments(request):
    return render(request, 'orders/payments.html')


def place_order(request, total=0, quantity=0):
    current_user = request.user

    # If the cart count is less than or equal to 0, redirect back to store
    cart_items = CartItem.objects.filter(user=current_user)
    if cart_items.count() <= 0:
        return redirect('store')

    # Calculate totals
    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += cart_item.quantity
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
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
                order_note=form.cleaned_data['order_note'],
                order_total=grand_total,
                tax=tax,
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
                'grand_total': grand_total,
            }
            return render(request, 'orders/payments.html', context)
    return redirect('checkout')


def sslcommerz_payment(request, order_id):
    order = Order.objects.get(id=order_id, user=request.user, is_ordered=False)

    if settings.SSLCOMMERZ['sandbox']:
        url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
    else:
        url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"

    payload = {
        'store_id': settings.SSLCOMMERZ['store_id'],
        'store_passwd': settings.SSLCOMMERZ['store_password'],
        'total_amount': order.order_total,
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
    # Redirect user to SSLCommerz payment page
    return redirect(data['GatewayPageURL'])


@csrf_exempt
def ssl_success(request):
    """
    Handle successful SSLCommerz payment (supports both GET and POST)
    """
    # Get data from POST JSON or GET query
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

    # Ensure payment_id is never None
    payment_id = val_id or tran_id or f"PAY-{order_number}"

    # Create Payment
    payment = Payment.objects.create(
        user=order.user,
        payment_id=payment_id,
        payment_method='SSLCommerz',
        amount_paid=amount or order.order_total,
        status=status or "Success",
    )

    # Update order
    order.payment = payment
    order.is_ordered = True
    order.save()

    # Move cart items to OrderProduct
    cart_items = CartItem.objects.filter(user=order.user)
    for item in cart_items:
        order_product = OrderProduct.objects.create(
            order=order,
            payment=payment,
            user=item.user,
            product=item.product,
            quantity=item.quantity,
            product_price=item.product.price,
            ordered=True,
        )
        if hasattr(item, 'variations') and item.variations.exists():
            order_product.variations.set(item.variations.all())
        order_product.save()

        # Reduce stock
        product = item.product
        product.stock -= item.quantity
        product.save()

    # Clear cart
    CartItem.objects.filter(user=order.user).delete()

    # Send confirmation email
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_recieved_email.html', {
        'user': order.user,
        'order': order,
    })
    EmailMessage(mail_subject, message, to=[order.user.email]).send()

    # Subtotal
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
