from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Category, Variant


def product_listing_view(request):
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '')
    selected_category = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    variants = Variant.objects.filter(
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).select_related(
        'product',
        'product__category'
    ).prefetch_related(
        'images'
    )

    if search_query:
        variants = variants.filter(
            product__product_name__icontains=search_query
        )

    if selected_category:
        variants = variants.filter(product__category__id=selected_category)

    if min_price:
        variants = variants.filter(price__gte=min_price)

    if max_price:
        variants = variants.filter(price__lte=max_price)

    if sort_by == 'price_asc':
        variants = variants.order_by('price')
        
    elif sort_by == 'price_desc':
        variants = variants.order_by('-price')
        
    elif sort_by == 'stock_desc':
        variants = variants.order_by('product__product_name')
        
    else:
        variants = variants.order_by('-created_at')

    paginator = Paginator(variants, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('category_name')

    return render(request, 'products/product_listing.html', {
        'variants':page_obj ,
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'sort_by': sort_by,
        'selected_category': selected_category,
        'min_price': min_price,
        'max_price': max_price,
    })