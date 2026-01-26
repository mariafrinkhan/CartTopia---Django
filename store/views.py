from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from orders.models import OrderProduct
from store.forms import ReviewForm
from .models import Product, ReviewRating, ProductGallery
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import Paginator
from django.db.models import Q


def store(request, category_slug=None):
    categories = None
    products = None

    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories).order_by("-is_available")
        paginator = Paginator(products, 3)
        page = request.GET.get("page")
        paged_products = paginator.get_page(page)

    else:
        products = Product.objects.all().order_by("-is_available")
        paginator = Paginator(products, 3)
        page = request.GET.get("page")
        paged_products = paginator.get_page(page)

    product_count = products.count()

    context = {
        "products": paged_products,
        "product_count": product_count,
    }
    return render(request, "store/store.html", context)


def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(
            category__slug=category_slug, slug=product_slug
        )
        in_cart = CartItem.objects.filter(
            cart__cart_id=_cart_id(request), product=single_product
        ).exists()
    except Exception as e:
        raise e

    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(
                user=request.user, product_id=single_product.id
            ).exists()
        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None

    # Get the reviews
    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)

    # Get the product gallery
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)

    context = {
        "single_product": single_product,
        "in_cart": in_cart,
        "orderproduct": orderproduct,
        "reviews": reviews,
        "product_gallery": product_gallery,
    }

    return render(request, "store/product_detail.html", context)



def search(request):
    keyword = request.GET.get("keyword", "").strip()

    # If keyword is empty, redirect to previous page or homepage
    if not keyword:
        return redirect(request.META.get('HTTP_REFERER', '/'))

    products = Product.objects.none()
    product_count = 0

    if len(keyword) >= 3:
        queries = Q()

        # Split the keyword into words
        for word in keyword.split():
            # Handle singular/plural form for simple 's' ending
            if word.endswith('s') and len(word) > 1:
                singular = word[:-1]
                queries |= Q(product_name__icontains=word)
                queries |= Q(product_name__icontains=singular)
                queries |= Q(description__icontains=word)
                queries |= Q(description__icontains=singular)
            else:
                plural = word + 's'
                queries |= Q(product_name__icontains=word)
                queries |= Q(product_name__icontains=plural)
                queries |= Q(description__icontains=word)
                queries |= Q(description__icontains=plural)

        products = Product.objects.filter(queries).distinct().order_by("-is_available")
        product_count = products.count()

    # ===== Pagination =====
    paginator = Paginator(products, 3)  # 3 products per page
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    context = {
        "products": paged_products,
        "product_count": product_count,
        "keyword": keyword,
    }

    return render(request, "store/store.html", context)




def submit_review(request, product_id):
    url = request.META.get("HTTP_REFERER")
    if request.method == "POST":
        try:
            reviews = ReviewRating.objects.get(
                user__id=request.user.id, product__id=product_id
            )
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, "Thank you! Your review has been updated.")
            return redirect(url)
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data["subject"]
                data.rating = form.cleaned_data["rating"]
                data.review = form.cleaned_data["review"]
                data.ip = request.META.get("REMOTE_ADDR")
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, "Thank you! Your review has been submitted.")
                return redirect(url)
