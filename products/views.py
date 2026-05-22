from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, Prefetch
from cart.models import Wishlist
from django.contrib import messages
from accounts.decorators import user_required
from django.contrib.auth.decorators import login_required
from .models import Category, Product, Variant, VariantImage
from offers.utils import calculate_best_offer


def product_listing_view(request):
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '')
    selected_category = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    selected_sizes = request.GET.getlist('size')
    selected_colors = request.GET.getlist('color')

    products = Product.objects.filter(
        is_active=True,
        is_deleted=False,
        category__is_active=True,
        category__is_deleted=False,
        variants__is_active=True,
        variants__is_deleted=False,
    ).select_related(
        'category'
    ).prefetch_related(
        Prefetch(
            'variants',
            queryset=Variant.objects.filter(
                is_active=True,
                is_deleted=False
            ).prefetch_related(
                Prefetch(
                    'images',
                    queryset=VariantImage.objects.order_by('-is_primary', 'id'),
                    to_attr='ordered_images'
                )
            ).order_by('-stock', 'price'),
            to_attr='active_variants'
        )
    ).distinct()

    
    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(variants__color__icontains=search_query) |
            Q(variants__size__icontains=search_query)
        )


    if selected_category:
        if selected_category.isdigit():
            products = products.filter(category__id=selected_category)
        else:
            products = products.filter(
                category__category_name__iexact=selected_category
            )


    if min_price:
        products = products.filter(
            variants__price__gte=min_price
        )

    if max_price:
        products = products.filter(
            variants__price__lte=max_price
        )

    
    if selected_sizes:
        products = products.filter(
            variants__size__in=selected_sizes
        )

    if selected_colors:
        products = products.filter(
            variants__color__in=selected_colors
        )

    products = products.distinct()

    if sort_by == 'price_asc':
        products = products.order_by('variants__price')

    elif sort_by == 'price_desc':
        products = products.order_by('-variants__price')

    elif sort_by == 'name_asc':
        products = products.order_by('product_name')

    elif sort_by == 'name_desc':
        products = products.order_by('-product_name')

    else:
        products = products.order_by(
            '-variants__stock',
            '-created_at'
        )

    product_cards = []
    seen_product_ids = set()

    for product in products:
        if product.id in seen_product_ids:
            continue

        representative_variant = None

        in_stock_variants = [
            v for v in product.active_variants
            if v.stock > 0
        ]

        if in_stock_variants:
            representative_variant = in_stock_variants[0]
        elif product.active_variants:
            representative_variant = product.active_variants[0]

        if representative_variant:
            offer_data = calculate_best_offer(representative_variant)
            product.representative_variant = representative_variant
            product.offer_data = offer_data
            product.total_colors = len(set(v.color for v in product.active_variants))
            product.is_out_of_stock = all(v.stock <= 0 for v in product.active_variants)

            product_cards.append(product)
            seen_product_ids.add(product.id)

    paginator = Paginator(product_cards, 8)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('category_name')

    available_sizes = Variant.objects.filter(
        is_active=True,
        is_deleted=False
    ).values_list(
        'size',
        flat=True
    ).distinct().order_by('size')

    available_colors = Variant.objects.filter(
        is_active=True,
        is_deleted=False
    ).values_list(
        'color',
        flat=True
    ).distinct().order_by('color')
    
    wishlisted_variant_ids = []
    
    if request.user.is_authenticated:
        wishlisted_variant_ids = list(
            Wishlist.objects.filter(user=request.user)
            .values_list('variant_id', flat=True)
    )

    return render(request, 'products/product_listing.html', {
        'products': page_obj,
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
        'wishlisted_variant_ids': wishlisted_variant_ids,
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
    
    offer_data = calculate_best_offer(variant)


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
        'offer_data': offer_data,
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