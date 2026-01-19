from django.contrib import admin
from django.db.models import Sum, F, Avg, Max, OuterRef, Subquery
from django.utils.timezone import now
from datetime import timedelta, datetime

from rangefilter.filters import DateRangeFilter

from .models import ProductReport, SalesSummary, ReviewRatingReport, TopCustomerReport, LowStockReport
from orders.models import OrderProduct
from django import forms




from django.contrib import admin
from django.db.models import Sum, F
from datetime import datetime
from orders.models import OrderProduct
from .models import SalesSummary

# -------------------------
# Custom Year Filter
# -------------------------
class YearListFilter(admin.SimpleListFilter):
    title = 'Year'
    parameter_name = 'year'

    def lookups(self, request, model_admin):
        # Last 5 years dynamically
        current_year = datetime.now().year
        return [(str(y), str(y)) for y in range(current_year, current_year - 5, -1)]

    def queryset(self, request, queryset):
        if self.value():
            request.selected_year = int(self.value())
        return queryset


# -------------------------
# Custom Month Filter
# -------------------------
class MonthListFilter(admin.SimpleListFilter):
    title = 'Month'
    parameter_name = 'month'

    MONTHS = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December')
    ]

    def lookups(self, request, model_admin):
        return self.MONTHS  # <--- fixed reference

    def queryset(self, request, queryset):
        if self.value():
            request.selected_month = int(self.value())
        return queryset


# -------------------------
# SalesSummary Admin
# -------------------------
@admin.register(SalesSummary)
class SalesSummaryAdmin(admin.ModelAdmin):
    list_display = ('title', 'total_items_sold', 'total_revenue')
    list_filter = (YearListFilter, MonthListFilter)  # sidebar filters

    # Capture request to access selected year/month
    def get_queryset(self, request):
        self.request = request
        return super().get_queryset(request)

    # Filter OrderProduct dynamically
    def _filtered_orders(self):
        qs = OrderProduct.objects.all()
        req = getattr(self, 'request', None)
        if not req:
            return qs

        # filter by selected year
        selected_year = getattr(req, 'selected_year', None)
        if selected_year:
            qs = qs.filter(created_at__year=selected_year)

        # filter by selected month
        selected_month = getattr(req, 'selected_month', None)
        if selected_month:
            qs = qs.filter(created_at__month=selected_month)

        return qs

    # Totals
    def total_items_sold(self, obj):
        return self._filtered_orders().aggregate(total=Sum('quantity'))['total'] or 0

    def total_revenue(self, obj):
        return self._filtered_orders().aggregate(
            total=Sum(F('product_price') * F('quantity'))
        )['total'] or 0

    # Read-only
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False








# =========================
# PRODUCT REPORT (Top sellers first)
# =========================
@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = (
        'product_name',
        'stock',
        'total_sold',
        'sold_this_month',
        'sold_last_month',
    )

    # Calendar popup filter
    list_filter = (
        ('orderproduct__created_at', DateRangeFilter),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_sold_annotated=Sum('orderproduct__quantity')
        ).order_by('-total_sold_annotated')

    def total_sold(self, obj):
        return obj.total_sold_annotated or 0
    total_sold.short_description = "Total Sold"

    def sold_this_month(self, obj):
        start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            OrderProduct.objects
            .filter(product=obj, created_at__gte=start)
            .aggregate(total=Sum('quantity'))['total']
            or 0
        )

    def sold_last_month(self, obj):
        start_this_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_last_month = start_this_month - timedelta(seconds=1)
        start_last_month = end_last_month.replace(day=1)

        return (
            OrderProduct.objects
            .filter(
                product=obj,
                created_at__gte=start_last_month,
                created_at__lte=end_last_month
            )
            .aggregate(total=Sum('quantity'))['total']
            or 0
        )


# =========================
# SALES SUMMARY (Overall business report)
# =========================
# @admin.register(SalesSummary)
# class SalesSummaryAdmin(admin.ModelAdmin):
#     list_display = (
#         'title',
#         'total_items_sold',
#         'total_revenue',
#         'sold_this_week',
#         'sold_this_month',
#         'sold_this_year',
#     )

#     # -----------------------
#     # Totals
#     # -----------------------
#     def total_items_sold(self, obj):
#         return OrderProduct.objects.aggregate(
#             total=Sum('quantity')
#         )['total'] or 0

#     def total_revenue(self, obj):
#         # Multiply price * quantity for revenue
#         return OrderProduct.objects.aggregate(
#             total=Sum(F('product_price') * F('quantity'))
#         )['total'] or 0

#     # -----------------------
#     # Sold in specific periods
#     # -----------------------
#     def sold_this_week(self, obj):
#         start = now() - timedelta(days=7)
#         return OrderProduct.objects.filter(
#             created_at__gte=start
#         ).aggregate(total=Sum('quantity'))['total'] or 0

#     def sold_this_month(self, obj):
#         start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
#         return OrderProduct.objects.filter(
#             created_at__gte=start
#         ).aggregate(total=Sum('quantity'))['total'] or 0

#     def sold_this_year(self, obj):
#         start = now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
#         return OrderProduct.objects.filter(
#             created_at__gte=start
#         ).aggregate(total=Sum('quantity'))['total'] or 0

#     # -----------------------
#     # Make admin clean (read-only)
#     # -----------------------
#     def has_add_permission(self, request):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False




@admin.register(ReviewRatingReport)
class ReviewRatingReportAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'avg_rating',
        'total_reviews',
        'five_star_count',
        'four_star_count',
        'three_star_count',
        'two_star_count',
        'one_star_count',
    )

    list_filter = (
        ('created_at', DateRangeFilter),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # annotate average rating for each product to order by
        qs = qs.annotate(avg_rating_annotated=Avg('rating'))
        return qs.order_by('-avg_rating_annotated')

    def avg_rating(self, obj):
        return obj.avg_rating_annotated or 0
    avg_rating.short_description = "Average Rating"

    def total_reviews(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product).count()
    total_reviews.short_description = "Total Reviews"

    def five_star_count(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product, rating=5).count()
    five_star_count.short_description = "5★"

    def four_star_count(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product, rating=4).count()
    four_star_count.short_description = "4★"

    def three_star_count(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product, rating=3).count()
    three_star_count.short_description = "3★"

    def two_star_count(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product, rating=2).count()
    two_star_count.short_description = "2★"

    def one_star_count(self, obj):
        return ReviewRatingReport.objects.filter(product=obj.product, rating=1).count()
    one_star_count.short_description = "1★"


@admin.register(TopCustomerReport)
class TopCustomerReportAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'total_orders',
        'total_spent',
        'last_order_date',
    )

    list_filter = (
        ('orderproduct__created_at', DateRangeFilter),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Subquery: sum of all completed orders for each user
        total_spent_subquery = OrderProduct.objects.filter(
            order__user=OuterRef('pk'),
            order__is_ordered=True
        ).values('order__user').annotate(
            total=Sum(F('product_price') * F('quantity'))
        ).values('total')

        # annotate total_spent so we can order by it
        qs = qs.annotate(total_spent=Subquery(total_spent_subquery))
        return qs.order_by('-total_spent')

    # Calculate totals dynamically
    def total_orders(self, obj):
        return obj.order_set.filter(is_ordered=True).count()

    def total_spent(self, obj):
        return obj.order_set.filter(is_ordered=True).aggregate(
            total=Sum(F('orderproduct__product_price') * F('orderproduct__quantity'))
        )['total'] or 0

    def last_order_date(self, obj):
        return obj.order_set.filter(is_ordered=True).aggregate(
            last=Max('created_at')
        )['last']


@admin.register(LowStockReport)
class LowStockReportAdmin(admin.ModelAdmin):
    list_display = (
        'product_name',
        'stock',
        'avg_daily_sold',
        'days_left',
    )

    list_filter = (
        ('orderproduct__created_at', DateRangeFilter),
    )

    def avg_daily_sold(self, obj):
        start = now() - timedelta(days=30)
        sold_last_30 = OrderProduct.objects.filter(
            product=obj,
            order__is_ordered=True,
            created_at__gte=start
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return round(sold_last_30 / 30, 2)

    def days_left(self, obj):
        avg_sold = self.avg_daily_sold(obj)
        if avg_sold == 0:
            return "∞"
        return round(obj.stock / avg_sold, 2)

