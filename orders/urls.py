from django.urls import path
from . import views


urlpatterns = [
    path('place_order/', views.place_order, name='place_order'),
    path('payments/', views.payments, name='payments'),
    path('ssl-pay/<int:order_id>/', views.sslcommerz_payment, name='ssl_pay'),
    path('ssl-success/', views.ssl_success, name='ssl_success'),
    path('ssl-fail/', views.ssl_fail, name='ssl_fail'),
    path('ssl-cancel/', views.ssl_cancel, name='ssl_cancel'),
    path('after-order-login/<str:order_number>/', views.after_order_login, name='after_order_login'),


]