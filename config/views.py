from django.http import HttpResponse
from django.shortcuts import render
from store.models import Product, ReviewRating
from django.db.models import Avg


def home (request):
    # products = Product.objects.all().filter(is_available=True).order_by('created_date')
    products = Product.objects.all().filter(is_available=True)

    # Annotate each product with its average rating
    products = products.annotate(avg_rating=Avg('reviewrating__rating')).order_by('-avg_rating')[:8]  # top products

    # # Get the reviews
    reviews = None
    for product in products:
        reviews = ReviewRating.objects.filter(product_id=product.id, status=True)


    context = {
        'products': products,
        'reviews': reviews,
    }
    return render(request, 'home.html', context)