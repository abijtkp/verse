from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .models import Category, Variant
from django.db.models import Q, Avg, Count, Prefetch
from cart.models import Wishlist
from django.contrib import messages
from accounts.decorators import user_required
from django.contrib.auth.decorators import login_required
from .models import Category, Variant, VariantImage


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
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).select_related(
        'product',
        'product__category'
    ).prefetch_related(
        Prefetch(
            'images',
            queryset=VariantImage.objects.order_by('-is_primary', 'id'),
            to_attr='ordered_images'
        )
    )

    if search_query:
        variants = variants.filter(
            Q(product__product_name__icontains=search_query) |
            Q(product__description__icontains=search_query) |
            Q(color__icontains=search_query) |
            Q(size__icontains=search_query)
        )

    if selected_category:
        if selected_category.isdigit():
            variants = variants.filter(product__category__id=selected_category)
        else:
            variants = variants.filter(product__category__category_name__iexact=selected_category)

    if min_price:
        variants = variants.filter(price__gte=min_price)

    if max_price:
        variants = variants.filter(price__lte=max_price)
        
    if selected_sizes:
        variants = variants.filter(size__in=selected_sizes)

    if selected_colors:
        variants = variants.filter(color__in=selected_colors)
    
    variants = variants.distinct()        

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
        
      
    unique_variants = []
    seen_product_ids = set()
    
    for variant in variants:
        if variant.product_id not in seen_product_ids:
            unique_variants.append(variant)
            seen_product_ids.add(variant.product_id)    

    paginator = Paginator(unique_variants, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('category_name')
    
    available_sizes = Variant.objects.filter(
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).values_list('size', flat=True).distinct().order_by('size')

    available_colors = Variant.objects.filter(
        is_active=True,
        is_deleted=False,
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
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )


    all_color_variants = Variant.objects.filter(
        product=variant.product,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).order_by('color', 'size')

    color_variants_dict = {}

    for item in all_color_variants:
        color_key = item.color.lower()

        if color_key not in color_variants_dict:
            color_variants_dict[color_key] = item

        if item.color.lower() == variant.color.lower():
            color_variants_dict[color_key] = variant

    same_product_variants = color_variants_dict.values()


    size_variants = Variant.objects.filter(
        product=variant.product,
        color=variant.color,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).order_by('size')


    related_variants = Variant.objects.filter(
        product__category=variant.product.category,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    ).exclude(
        product_id=variant.product_id
    ).select_related(
        'product',
        'product__category'
    ).prefetch_related(
        Prefetch(
        'images',
        queryset=VariantImage.objects.order_by('-is_primary', 'id'),
        to_attr='ordered_images'
        )
    ).order_by('?')
    
    related_products = []
    seen_product_ids = set()
    
    for item in related_variants:
        if item.product_id not in seen_product_ids:
            related_products.append(item)
            seen_product_ids.add(item.product_id)

        if len(related_products) == 4:
            break

    is_in_wishlist = False

    if request.user.is_authenticated:
        is_in_wishlist = Wishlist.objects.filter(
            user=request.user,
            variant=variant
        ).exists()
        
    # reviews = ProductReview.objects.filter(
    #     product=variant.product,
    #     is_active=True,
    # ).select_related('user')
    
    # review_summary = reviews.aggregate(
    #     average_rating=Avg('rating'),
    #     review_count=Count('id')
    # )
    
    # user_review = None
    
    # if request.user.is_authenticated:
    #     user_review = ProductReview.objects.filter(
    #         product=variant.product,
    #         user=request.user
    #     ).first()  
        
          
    

    context = {
        'variant': variant,
        'same_product_variants': same_product_variants,
        'size_variants': size_variants,
        'related_products': related_products,
        'is_in_wishlist': is_in_wishlist,
       
    }

    return render(
        request,
        'products/product_detail.html',
        context
    )
    
    
    
# @user_required
# def submit_review(request, variant_id):

#     variant = get_object_or_404(
#         Variant,
#         id=variant_id,
#         is_active=True,
#         product__is_active=True,
#         product__is_deleted=False
#     )

#     if request.method == 'POST':

#         rating = request.POST.get('rating')
#         review_text = request.POST.get('review_text', '').strip()

#         if not rating:
#             messages.error(request, "Please select a rating")
#             return redirect('product_detail', variant.id)

#         ProductReview.objects.update_or_create(
#             user=request.user,
#             variant=variant,
#             defaults={
#                 'rating': int(rating),
#                 'review_text': review_text
#             }
#         )

#         messages.success(request, "Review submitted successfully")

#     return redirect('product_detail', variant.id)