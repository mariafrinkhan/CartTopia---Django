from itertools import product
from django.contrib import messages, auth
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from accounts.models import Account, UserProfile
from carts.models import Cart, CartItem
from carts.views import _cart_id
from orders.models import Order, OrderProduct
from .forms import RegistrationForm, UserForm, UserProfileForm
from django.contrib.auth.decorators import login_required

# Verification email imports
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
import requests
from django.db.models import Sum


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            phone_number = form.cleaned_data["phone_number"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            username = email.split("@")[0]
            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                password=password,
            )
            user.phone_number = phone_number
            user.save()

            # Create a user profile
            profile = UserProfile()
            profile.user_id = user.id
            profile.profile_picture = 'default/default-user.png'
            profile.save()

            # User Activation
            current_site = get_current_site(request)
            mail_subject = "Please activate your account"
            message = render_to_string(
                "accounts/account_verification_email.html",
                {
                    "user": user,
                    "domain": current_site,
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": default_token_generator.make_token(user),
                },
            )
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()
            # messages.success(request, "Thank you for registering with us. We have sent you a verification email to your email address [<EMAIL>]. Please verify to activate your account.")
            return redirect("/accounts/login/?command=verification&email=" + email)
    else:
        form = RegistrationForm()
    context = {
        "form": form,
    }
    return render(request, "accounts/register.html", context)


MAX_PER_PRODUCT = 10  # Max items per product allowed in cart

def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = auth.authenticate(email=email, password=password)
        if user is None:
            messages.error(request, "Invalid login credentials")
            return redirect("login")

        # ---------- MERGE GUEST CART ----------
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            guest_items = CartItem.objects.filter(cart=cart, is_active=True)

            for item in guest_items:
                product = item.product
                variations = list(item.variations.all())

                # total quantity already in user's cart (all variations)
                user_total_qty = (
                    CartItem.objects
                    .filter(user=user, product=product, is_active=True)
                    .aggregate(total=Sum("quantity"))["total"] or 0
                )

                # compute how many we can add
                remaining_stock = product.stock - user_total_qty
                remaining_limit = MAX_PER_PRODUCT - user_total_qty
                allowed_qty = min(remaining_stock, remaining_limit)

                if allowed_qty <= 0:
                    # cannot add any → delete guest item
                    item.delete()
                    continue

                # check if same variation already exists
                existing_items = CartItem.objects.filter(
                    user=user, product=product, is_active=True
                )

                merged = False
                for ex_item in existing_items:
                    if list(ex_item.variations.all()) == variations:
                        qty_to_add = min(item.quantity, allowed_qty)
                        ex_item.quantity += qty_to_add
                        ex_item.save()
                        item.delete()
                        merged = True
                        break

                if not merged:
                    # assign item to user
                    qty_to_add = min(item.quantity, allowed_qty)
                    item.quantity = qty_to_add
                    item.user = user
                    item.cart = None
                    item.save()

        except Cart.DoesNotExist:
            pass

        # ---------- LOGIN ----------
        auth.login(request, user)
        messages.success(request, "You are now logged in.")

        # redirect logic
        url = request.META.get("HTTP_REFERER")
        try:
            query = requests.utils.urlparse(url).query
            params = dict(x.split("=") for x in query.split("&"))
            if "next" in params:
                return redirect(params["next"])
        except:
            pass

        return redirect("dashboard")

    return render(request, "accounts/login.html")



@login_required(login_url="login")
def logout(request):
    auth.logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your account has been activated successfully!")
        return redirect("login")
    else:
        messages.error(request, "Invalid activation link.")
        return redirect("register")

@login_required(login_url="login")
def dashboard(request):
    orders = Order.objects.order_by('-created_at').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()

    userprofile = UserProfile.objects.get(user_id=request.user.id)
    context = {
        'orders_count': orders_count,
        'userprofile': userprofile,
    }
    return render(request, "accounts/dashboard.html", context)

def forgotPassword(request):
    if request.method == "POST":
        email = request.POST["email"]

        if Account.objects.filter(email=email).exists():
            user=Account.objects.get(email__exact=email)

            # Reset Password Email
            current_site = get_current_site(request)
            mail_subject = "Reset Your Password"
            message = render_to_string(
                "accounts/reset_password_email.html",
                {
                    "user": user,
                    "domain": current_site,
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": default_token_generator.make_token(user),
                },
            )
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(
                request,
                "Password reset email has been sent to your email address.",
            )
            return redirect("login")
        else:
            messages.error(request, "Account does not exist!")
            return redirect("forgotPassword")    
    return render(request, "accounts/forgotPassword.html")

def resetpassword_validate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session["uid"] = uid
        messages.success(request, "Please reset your password")
        return redirect("resetPassword")
    else:
        messages.error(request, "This link has been expired!")
        return redirect("login")
    
def resetPassword(request):
    if request.method == "POST":
        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if password == confirm_password:
            uid = request.session.get("uid")
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, "Password reset successful.")
            return redirect("login")
        else:
            messages.error(request, "Passwords do not match!")
            return redirect("resetPassword")
    else:
        return render(request, "accounts/resetPassword.html")

@login_required(login_url='login')    
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)

@login_required(login_url='login')
def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        user = Account.objects.get(username__exact=request.user.username)

        if new_password == confirm_password:
            success = user.check_password(current_password)
            if success:
                user.set_password(new_password)
                user.save()
                # auth.logout(request)
                messages.success(request, 'Password updated successfully.')
                return redirect('change_password')
            else:
                messages.error(request, 'Please enter valid current password')
                return redirect('change_password')
        else:
            messages.error(request, 'Password does not match!')
            return redirect('change_password')
    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def order_detail(request, order_id):
    order_detail = OrderProduct.objects.filter(order__order_number=order_id)
    order = Order.objects.get(order_number=order_id)
    subtotal = 0
    for i in order_detail:
        subtotal += i.product_price * i.quantity

    context = {
        'order_detail': order_detail,
        'order': order,
        'subtotal': subtotal,
    }
    return render(request, 'accounts/order_detail.html', context)