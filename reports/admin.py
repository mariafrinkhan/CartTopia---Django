from django.contrib import admin
from django.db.models import Sum, F, Avg, Max, OuterRef, Subquery
from django.utils.timezone import now
from datetime import timedelta, datetime
from django.http import HttpResponse
import csv
from orders.models import OrderProduct

from rangefilter.filters import DateRangeFilter

from .models import (
    ProductReport,
    SalesSummary,
    ReviewRatingReport,
    TopCustomerReport,
    LowStockReport,
)


# =====================================================
# CSV EXPORT (Reusable)
# =====================================================
def export_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{modeladmin.model.__name__}.csv"'
    writer = csv.writer(response)

    headers = modeladmin.list_display
    writer.writerow(headers)

    for obj in queryset:
        row = []
        for field in headers:
            value = getattr(modeladmin, field, None)
            row.append(value(obj) if callable(value) else getattr(obj, field))
        writer.writerow(row)

    return response


# =====================================================
# YEAR FILTER
# =====================================================
class YearListFilter(admin.SimpleListFilter):
    title = "Year"
    parameter_name = "year"

    def lookups(self, request, model_admin):
        current_year = datetime.now().year
        return [(str(y), str(y)) for y in range(current_year, current_year - 10, -1)]

    def queryset(self, request, queryset):
        if self.value():
            request.selected_year = int(self.value())
        return queryset


# =====================================================
# MONTH FILTER
# =====================================================
class MonthListFilter(admin.SimpleListFilter):
    title = "Month"
    parameter_name = "month"

    MONTHS = [
        (1, "January"), (2, "February"), (3, "March"),
        (4, "April"), (5, "May"), (6, "June"),
        (7, "July"), (8, "August"), (9, "September"),
        (10, "October"), (11, "November"), (12, "December"),
    ]

    def lookups(self, request, model_admin):
        return self.MONTHS

    def queryset(self, request, queryset):
        if self.value():
            request.selected_month = int(self.value())
        return queryset


# =====================================================
# SALES SUMMARY
# =====================================================
@admin.register(SalesSummary)
class SalesSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "total_items_sold",
        "total_revenue_bdt",
        "total_cancellations",
        "total_refund_bdt",
    )
    list_filter = (YearListFilter, MonthListFilter)
    actions = [export_as_csv]

    def get_queryset(self, request):
        self.request = request
        return super().get_queryset(request)

    def _filtered_orders(self):
        qs = OrderProduct.objects.all()
        req = getattr(self, "request", None)

        if req:
            if hasattr(req, "selected_year"):
                qs = qs.filter(created_at__year=req.selected_year)
            if hasattr(req, "selected_month"):
                qs = qs.filter(created_at__month=req.selected_month)

        return qs

    def total_items_sold(self, obj):
        return self._filtered_orders().aggregate(t=Sum("quantity"))["t"] or 0

    def total_revenue_bdt(self, obj):
        total = self._filtered_orders().aggregate(
            t=Sum(F("product_price") * F("quantity"))
        )["t"] or 0
        return f"BDT {total}"

    def total_cancellations(self, obj):
        return self._filtered_orders().filter(order__status="Cancelled").count()

    def total_refund_bdt(self, obj):
        total = self._filtered_orders().filter(
            order__status="Cancelled"
        ).aggregate(t=Sum(F("product_price") * F("quantity")))["t"] or 0
        return f"BDT {total}"

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


# =====================================================
# PRODUCT REPORT
# =====================================================
@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = (
        "product_name",
        "stock",
        "total_sold",
        "sold_this_month",
        "sold_last_month",
    )
    list_filter = (("orderproduct__created_at", DateRangeFilter),)
    actions = [export_as_csv]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_sold_annotated=Sum("orderproduct__quantity")
        ).order_by("-total_sold_annotated")

    def total_sold(self, obj):
        return obj.total_sold_annotated or 0

    def sold_this_month(self, obj):
        start = now().replace(day=1)
        return OrderProduct.objects.filter(
            product=obj, created_at__gte=start
        ).aggregate(t=Sum("quantity"))["t"] or 0

    def sold_last_month(self, obj):
        start = (now().replace(day=1) - timedelta(days=1)).replace(day=1)
        end = now().replace(day=1) - timedelta(seconds=1)
        return OrderProduct.objects.filter(
            product=obj, created_at__range=(start, end)
        ).aggregate(t=Sum("quantity"))["t"] or 0


# =====================================================
# REVIEW RATING REPORT
# =====================================================
@admin.register(ReviewRatingReport)
class ReviewRatingReportAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "avg_rating",
        "total_reviews",
        "five_star_count",
        "four_star_count",
        "three_star_count",
        "two_star_count",
        "one_star_count",
    )
    list_filter = (("created_at", DateRangeFilter),)
    actions = [export_as_csv]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            avg_rating_annotated=Avg("rating")
        ).order_by("-avg_rating_annotated")

    def avg_rating(self, obj): return obj.avg_rating_annotated or 0
    def total_reviews(self, obj): return ReviewRatingReport.objects.filter(product=obj.product).count()
    def five_star_count(self, obj): return ReviewRatingReport.objects.filter(product=obj.product, rating=5).count()
    def four_star_count(self, obj): return ReviewRatingReport.objects.filter(product=obj.product, rating=4).count()
    def three_star_count(self, obj): return ReviewRatingReport.objects.filter(product=obj.product, rating=3).count()
    def two_star_count(self, obj): return ReviewRatingReport.objects.filter(product=obj.product, rating=2).count()
    def one_star_count(self, obj): return ReviewRatingReport.objects.filter(product=obj.product, rating=1).count()


# =====================================================
# TOP CUSTOMER REPORT
# =====================================================
@admin.register(TopCustomerReport)
class TopCustomerReportAdmin(admin.ModelAdmin):
    list_display = ("email", "total_orders", "total_spent", "last_order_date")
    list_filter = (("orderproduct__created_at", DateRangeFilter),)
    actions = [export_as_csv]

    def get_queryset(self, request):
        total_spent_sq = OrderProduct.objects.filter(
            order__user=OuterRef("pk"),
            order__is_ordered=True
        ).values("order__user").annotate(
            t=Sum(F("product_price") * F("quantity"))
        ).values("t")

        return super().get_queryset(request).annotate(
            total_spent=Subquery(total_spent_sq)
        ).order_by("-total_spent")

    def total_orders(self, obj): return obj.order_set.filter(is_ordered=True).count()
    def total_spent(self, obj): return obj.total_spent or 0
    def last_order_date(self, obj):
        return obj.order_set.filter(is_ordered=True).aggregate(
            d=Max("created_at")
        )["d"]


# =====================================================
# LOW STOCK REPORT
# =====================================================
@admin.register(LowStockReport)
class LowStockReportAdmin(admin.ModelAdmin):
    list_display = ("product_name", "stock", "avg_daily_sold", "days_left")
    list_filter = (("orderproduct__created_at", DateRangeFilter),)
    actions = [export_as_csv]

    def avg_daily_sold(self, obj):
        sold = OrderProduct.objects.filter(
            product=obj,
            order__is_ordered=True,
            created_at__gte=now() - timedelta(days=30)
        ).aggregate(t=Sum("quantity"))["t"] or 0
        return round(sold / 30, 2)

    def days_left(self, obj):
        avg = self.avg_daily_sold(obj)
        return "∞" if avg == 0 else round(obj.stock / avg, 2)
