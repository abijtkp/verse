from datetime import timedelta
from decimal import Decimal
import json
import io

from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from xhtml2pdf import pisa
from openpyxl import Workbook

from adminpanel.views.core_views import admin_required
from orders.models import Order, OrderItem


def _get_filtered_orders(request):
    filter_type = request.GET.get('filter', 'daily')
    today = timezone.now()

    base_orders = Order.objects.exclude(payment_status='failed')

    orders = base_orders.exclude(
        status__in=['cancelled', 'returned']
    )

    if filter_type == 'daily':
        orders = orders.filter(created_at__date=today.date())

    elif filter_type == 'weekly':
        start_week = today - timedelta(days=7)
        orders = orders.filter(created_at__gte=start_week)

    elif filter_type == 'monthly':
        orders = orders.filter(
            created_at__month=today.month,
            created_at__year=today.year
        )

    elif filter_type == 'yearly':
        orders = orders.filter(created_at__year=today.year)

    elif filter_type == 'custom':
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date and end_date:
            orders = orders.filter(
                created_at__date__range=[start_date, end_date]
            )

    return base_orders, orders, filter_type


def _get_report_metrics(base_orders, orders):
    total_orders = orders.count()

    total_revenue = orders.aggregate(
        total=Sum('final_total')
    )['total'] or Decimal('0.00')

    total_discount = orders.aggregate(
        total=Sum('discount')
    )['total'] or Decimal('0.00')

    total_offer_discount = OrderItem.objects.filter(
        order__in=orders
    ).aggregate(
        total=Sum('offer_discount')
    )['total'] or Decimal('0.00')

    total_coupon_discount = OrderItem.objects.filter(
        order__in=orders
    ).aggregate(
        total=Sum('coupon_discount_share')
    )['total'] or Decimal('0.00')

    cancelled_amount = OrderItem.objects.filter(
        order__in=base_orders,
        status='cancelled'
    ).aggregate(
        total=Sum('final_item_total')
    )['total'] or Decimal('0.00')

    returned_amount = OrderItem.objects.filter(
        order__in=base_orders,
        status='returned'
    ).aggregate(
        total=Sum('final_item_total')
    )['total'] or Decimal('0.00')

    net_revenue = max(
        total_revenue - cancelled_amount - returned_amount,
        Decimal('0.00')
    )

    products_sold = OrderItem.objects.filter(
        order__in=orders
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    average_order_value = Decimal('0.00')

    if total_orders > 0:
        average_order_value = total_revenue / total_orders

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_discount': total_discount,
        'total_offer_discount': total_offer_discount,
        'total_coupon_discount': total_coupon_discount,
        'cancelled_amount': cancelled_amount,
        'returned_amount': returned_amount,
        'net_revenue': net_revenue,
        'products_sold': products_sold,
        'average_order_value': average_order_value,
    }


def _get_chart_data(orders, filter_type):
    if filter_type == 'daily':
        chart_queryset = (
            orders
            .annotate(period=TruncHour('created_at'))
            .values('period')
            .annotate(total=Sum('final_total'))
            .order_by('period')
        )

        labels = [
            item['period'].strftime('%I %p')
            for item in chart_queryset
        ]

    elif filter_type == 'yearly':
        chart_queryset = (
            orders
            .annotate(period=TruncMonth('created_at'))
            .values('period')
            .annotate(total=Sum('final_total'))
            .order_by('period')
        )

        labels = [
            item['period'].strftime('%b')
            for item in chart_queryset
        ]

    else:
        chart_queryset = (
            orders
            .annotate(period=TruncDate('created_at'))
            .values('period')
            .annotate(total=Sum('final_total'))
            .order_by('period')
        )

        labels = [
            item['period'].strftime('%d %b')
            for item in chart_queryset
        ]

    values = [
        float(item['total'] or 0)
        for item in chart_queryset
    ]

    return labels, values


@admin_required
def sales_report_view(request):
    base_orders, orders, filter_type = _get_filtered_orders(request)
    metrics = _get_report_metrics(base_orders, orders)
    chart_labels, chart_values = _get_chart_data(orders, filter_type)

    orders = orders.order_by('-created_at')

    paginator = Paginator(orders, 5)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'orders': page_obj,
        'page_obj': page_obj,
        'filter_type': filter_type,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
        **metrics,
    }

    return render(
        request,
        'adminpanel/sales_report.html',
        context
    )


@admin_required
def export_sales_report_excel(request):
    base_orders, orders, filter_type = _get_filtered_orders(request)
    metrics = _get_report_metrics(base_orders, orders)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Sales Report'

    sheet.append(['VERSE Sales Report'])
    sheet.append(['Filter', filter_type.title()])
    sheet.append([])

    sheet.append(['Metric', 'Value'])
    sheet.append(['Total Orders', metrics['total_orders']])
    sheet.append(['Total Revenue', metrics['total_revenue']])
    sheet.append(['Net Revenue', metrics['net_revenue']])
    sheet.append(['Total Discount', metrics['total_discount']])
    sheet.append(['Offer Discount', metrics['total_offer_discount']])
    sheet.append(['Coupon Discount', metrics['total_coupon_discount']])
    sheet.append(['Cancelled Amount', metrics['cancelled_amount']])
    sheet.append(['Returned Amount', metrics['returned_amount']])
    sheet.append(['Products Sold', metrics['products_sold']])
    sheet.append(['Average Order Value', metrics['average_order_value']])
    sheet.append([])

    sheet.append([
        'Order ID',
        'Customer',
        'Date',
        'Payment Method',
        'Payment Status',
        'Order Status',
        'Subtotal',
        'Discount',
        'Final Total',
    ])

    for order in orders.order_by('-created_at'):
        sheet.append([
            order.order_id,
            order.user.email,
            order.created_at.strftime('%d %b %Y %I:%M %p'),
            order.payment_method,
            order.payment_status,
            order.status,
            order.subtotal,
            order.discount,
            order.final_total,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="VERSE_Sales_Report_{filter_type}.xlsx"'
    )

    workbook.save(response)

    return response


@admin_required
def export_sales_report_pdf(request):
    base_orders, orders, filter_type = _get_filtered_orders(request)
    metrics = _get_report_metrics(base_orders, orders)

    html_string = render_to_string(
        'adminpanel/sales_report_pdf.html',
        {
            'orders': orders.order_by('-created_at'),
            'filter_type': filter_type,
            **metrics,
        }
    )

    buffer = io.BytesIO()

    pisa_status = pisa.CreatePDF(
        io.BytesIO(html_string.encode('UTF-8')),
        dest=buffer
    )

    if pisa_status.err:
        return HttpResponse('PDF generation failed.')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="VERSE_Sales_Report_{filter_type}.pdf"'
    )
    response.write(buffer.getvalue())
    buffer.close()

    return response