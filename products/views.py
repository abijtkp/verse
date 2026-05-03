from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Category, Variant
from django.shortcuts import get_object_or_404


def product_listing_view(request):
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '')
    selected_category = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    selected_sizes = request.GET.getlist('size')
    selected_colors = request.GET.getlist('color')

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
        
    if selected_sizes:
        variants = variants.filter(size__in=selected_sizes)

    if selected_colors:
        variants = variants.filter(color__in=selected_colors)    

    if sort_by == 'price_asc':
        variants = variants.order_by('price')
        
    elif sort_by == 'price_desc':
        variants = variants.order_by('-price')
        
    elif sort_by == 'name_asc':
        variants = variants.order_by('product__product_name', 'color', 'size')

    elif sort_by == 'name_desc':
        variants = variants.order_by('-product__product_name', 'color', 'size')   
        
    elif sort_by == 'stock_desc':
        variants = variants.order_by('-stock')
        
    else:
        variants = variants.order_by('-created_at')

    paginator = Paginator(variants, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('category_name')
    
    available_sizes = Variant.objects.filter(
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).values_list('size', flat=True).distinct().order_by('size')

    available_colors = Variant.objects.filter(
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).values_list('color', flat=True).distinct().order_by('color')
    
    

    return render(request, 'products/product_listing.html', {
        'variants':page_obj ,
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'sort_by': sort_by,
        'selected_category': selected_category,
        'min_price': min_price,
        'max_price': max_price,
        'available_sizes': available_sizes,
        'available_colors': available_colors,
        'selected_sizes': selected_sizes,
        'selected_colors': selected_colors,
    })


def product_detail_view(request, variant_id):

    variant = get_object_or_404(
        Variant.objects.select_related(
            'product',
            'product__category'
        ).prefetch_related(
            'images'
        ),
        id=variant_id,
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )

    same_product_variants = Variant.objects.filter(
        product=variant.product,
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).exclude(
        id=variant.id
    ).order_by('color', 'size')

    size_variants = Variant.objects.filter(
        product=variant.product,
        color=variant.color,
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).order_by('size')

    related_products = Variant.objects.filter(
        product__category=variant.product.category,
        is_active=True,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).exclude(
        product=variant.product
    )[:4]

    context = {
        'variant': variant,
        'same_product_variants': same_product_variants,
        'size_variants': size_variants,
        'related_products': related_products,
    }

    return render(
        request,
        'products/product_detail.html',
        context
    )
    