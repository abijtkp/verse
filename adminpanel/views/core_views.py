from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.cache import never_cache
from functools import wraps

from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import User
from products.models import Product, Variant, Category
from orders.models import Order, OrderItem

import json
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncDay

import logging

logger = logging.getLogger(__name__)

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            
            logger.warning(
                "Unauthorized admin access attempt - unauthenticated | ip=%s | path=%s",
                request.META.get("REMOTE_ADDR"),
                request.path,
            )
            
            messages.error(request, "Please login to continue")
            return redirect('admin_login')

        if not request.user.is_staff:
            
            logger.warning(
                "Unauthorized admin access attempt - non staff | user_id=%s | email=%s | ip=%s | path=%s",
                request.user.id,
                request.user.email,
                request.META.get("REMOTE_ADDR"),
                request.path,
            )
            
            messages.error(request, "You are not authorized to access admin panel")
            return redirect('home')
        
        if request.user.is_blocked:
            
            logger.warning(
                "Blocked admin attempted access | user_id=%s | email=%s | ip=%s",
                request.user.id,
                request.user.email,
                request.META.get("REMOTE_ADDR"),
            )
            
            logout(request)
            
            messages.error(request, "Your account has been blocked")
            return redirect('admin_login')
            
        return view_func(request, *args, **kwargs)
    return wrapper


@never_cache
def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            
            logger.info(
                "Admin already authenticated redirected to dashboard | user_id=%s | email=%s",
                request.user.id,
                request.user.email,
            )
            
            return redirect('admin_dashboard')
        else:
            logout(request)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, email=email, password=password)

        if user is None:
            
            logger.warning(
                "Failed admin login attempt | email=%s | ip=%s",
                email,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "Invalid email or password")
            return redirect('admin_login')

        if not user.is_staff:
            
            logger.warning(
                "Non-admin attempted admin login | user_id=%s | email=%s | ip=%s",
                user.id,
                user.email,
                request.META.get("REMOTE_ADDR"),
            )
            
            messages.error(request, "You are not authorized to access admin panel")
            return redirect('admin_login')

        if user.is_blocked:
            
            logger.warning(
                "Blocked admin login attempt | user_id=%s | email=%s | ip=%s",
                user.id,
                user.email,
                request.META.get("REMOTE_ADDR"),
            )
   
            messages.error(request, "Your account has been blocked")
            return redirect('admin_login')

        login(request, user)
        
        logger.info(
            "Admin logged in successfully | user_id=%s | email=%s",
            user.id,
            user.email,
        )
        
        messages.success(request, "Welcome to admin panel")
        return redirect('admin_dashboard')

    return render(request, 'adminpanel/login.html')


@never_cache
@admin_required
def admin_dashboard_view(request):
    today = timezone.now()
    
    logger.info(
        "Admin dashboard accessed | user_id=%s | email=%s",
        request.user.id,
        request.user.email,
    )
    
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    successful_orders = Order.objects.exclude(
        payment_status='failed'
    ).exclude(
        status__in=['cancelled', 'returned', 'payment_failed']
    )

    total_revenue = successful_orders.aggregate(
        total=Sum('final_total')
    )['total'] or Decimal('0.00')

    monthly_revenue = successful_orders.filter(
        created_at__gte=month_start
    ).aggregate(
        total=Sum('final_total')
    )['total'] or Decimal('0.00')

    active_orders = Order.objects.filter(
        status__in=['pending', 'shipped', 'out_for_delivery']
    ).count()

    total_customers = User.objects.filter(
        is_staff=False
    ).count()

    total_products = Product.objects.filter(
        is_deleted=False
    ).count()

    low_stock_variants = Variant.objects.filter(
        is_deleted=False,
        stock__lte=5
    ).select_related('product')[:5]

    low_stock_count = Variant.objects.filter(
        is_deleted=False,
        stock__lte=5
    ).count()

    pending_returns = OrderItem.objects.filter(
        status='return_requested'
    ).count()

    recent_orders = Order.objects.exclude(
        status__in=['cancelled', 'payment_failed']
    ).select_related('user').order_by('-created_at')[:5]

    top_products = []

    top_products_queryset = (
        OrderItem.objects
        .values('product_name')
        .annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('item_total')
        )
        .order_by('-total_sold')[:5]
    )

    for item in top_products_queryset:
        variant = Variant.objects.filter(
            product__product_name=item['product_name']
        ).prefetch_related('images').first()

        primary_image = None

        if variant:
            primary = variant.images.filter(is_primary=True).first()

            if primary:
                primary_image = primary.image_url.url

        top_products.append({
            'product_name': item['product_name'],
            'total_sold': item['total_sold'],
            'total_revenue': item['total_revenue'],
            'primary_image': primary_image,
        })
    
    # monthly_chart = (
    #     successful_orders
    #     .annotate(month=TruncMonth('created_at'))
    #     .values('month')
    #     .annotate(
    #         revenue=Sum('final_total'),
    #         orders=Count('id')
    #     )
    #     .order_by('month')
    # )
    
    daily_chart = (
        successful_orders
        .annotate(day=TruncDay('created_at'))
        .values('day')
        .annotate(
            revenue=Sum('final_total'),
            orders=Count('id')
        )
        .order_by('day')
    )

    chart_labels = []
    chart_revenue = []
    chart_orders = []

    # for item in monthly_chart:
    #     chart_labels.append(item['month'].strftime('%b'))
    #     chart_revenue.append(float(item['revenue'] or 0))
    #     chart_orders.append(item['orders'] or 0)
        
    
    for item in daily_chart:
        chart_labels.append(item['day'].strftime('%d %b'))
        chart_revenue.append(float(item['revenue'] or 0))
        chart_orders.append(item['orders'] or 0)    
            
    
    category_data = (
        Category.objects.filter(
            is_active=True,
            is_deleted=False
        )
        .annotate(
            total_products=Count('products')
        )
        .order_by('-total_products')[:10]
    )

    category_labels = []
    category_counts = []

    for category in category_data:
        category_labels.append(category.category_name)
        category_counts.append(category.total_products)
        
    
    top_categories = (
        OrderItem.objects
        .values('category_name')
        .annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('item_total')
        )
        .order_by('-total_sold')[:10]
    )    
    
        

    context = {
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'active_orders': active_orders,
        'total_customers': total_customers,
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'low_stock_variants': low_stock_variants,
        'pending_returns': pending_returns,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'chart_labels': json.dumps(chart_labels),
        'chart_revenue': json.dumps(chart_revenue),
        'chart_orders': json.dumps(chart_orders),
        'category_labels': json.dumps(category_labels),
        'category_counts': json.dumps(category_counts),
        'top_categories': top_categories,
    }

    return render(request, 'adminpanel/dashboard.html', context)


@never_cache
@admin_required
def admin_logout_view(request):
    
    logger.info(
        "Admin logged out | user_id=%s | email=%s",
        request.user.id,
        request.user.email,
    )
    
    logout(request)
    
    messages.success(request, "Logged out successfully")
    return redirect('admin_login')
