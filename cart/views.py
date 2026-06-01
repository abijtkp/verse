from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from accounts.decorators import user_required
from products.models import Variant
from .models import Cart, CartItem, Wishlist
from userprofile.models import Address
from offers.utils import calculate_best_offer
from django.core.paginator import Paginator
from products.utils import is_variant_available

import logging

logger = logging.getLogger(__name__)

MAX_CART_QUANTITY = 5

@never_cache
@user_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)

    cart_items = (
        cart.items
        .select_related('variant', 'variant__product', 'variant__product__category')
        .prefetch_related('variant__images')
        .order_by('-created_at')
    )
    
    cart_total = 0
    
    has_unavailable_items = False

    for item in cart_items:
        item.is_available = is_variant_available(item.variant)
        
        if not item.is_available:
            has_unavailable_items = True
        
        item.offer_data = calculate_best_offer(item.variant)
        item.discounted_price = item.offer_data['final_price']
        item.discount_amount = item.offer_data['discount_amount']
        item.discounted_subtotal = item.discounted_price * item.quantity

        cart_total += item.discounted_subtotal

    has_address = Address.objects.filter(user=request.user).exists() 
    
    
    logger.info(
        "User viewed cart | user_id=%s | email=%s | total_items=%s | cart_total=%s",
        request.user.id,
        request.user.email,
        cart.total_items,
        cart_total,
    )
    
    return render(request, 'cart/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'has_unavailable_items': has_unavailable_items,
        'has_address': has_address,
        'cart_total': cart_total,
    })


@user_required
def add_to_cart(request, variant_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid add to cart request method | user_id=%s | email=%s | variant_id=%s | method=%s",
            request.user.id,
            request.user.email,
            variant_id,
            request.method,
        )
        
        return redirect('home')

    variant = get_object_or_404(
        Variant,
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )

    if variant.stock <= 0:
        
        logger.warning(
            "User attempted to add out-of-stock item to cart | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )
        
        messages.error(request, "This item is currently out of stock.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    cart, created = Cart.objects.get_or_create(user=request.user)

    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={'quantity': 1}
    )

    if not item_created:
        if cart_item.quantity >= MAX_CART_QUANTITY:
            
            logger.warning(
                "User exceeded max cart quantity | user_id=%s | email=%s | variant_id=%s | current_quantity=%s | max_quantity=%s",
                request.user.id,
                request.user.email,
                variant.id,
                cart_item.quantity,
                MAX_CART_QUANTITY,
            )
            
            messages.error(request, f"You can add maximum {MAX_CART_QUANTITY} quantity only.")
            return redirect(request.META.get('HTTP_REFERER', 'cart_view'))

        if cart_item.quantity >= variant.stock:
            
            logger.warning(
                "User attempted to add more than available stock | user_id=%s | email=%s | variant_id=%s | current_quantity=%s | stock=%s",
                request.user.id,
                request.user.email,
                variant.id,
                cart_item.quantity,
                variant.stock,
            )
            
            messages.error(request, "Cannot add more than available stock.")
            return redirect(request.META.get('HTTP_REFERER', 'cart_view'))

        cart_item.quantity += 1
        cart_item.save(update_fields=['quantity', 'updated_at'])
        
    Wishlist.objects.filter(
        user=request.user,
        variant=variant
    ).delete()   
    
    logger.info(
        "User added item to cart | user_id=%s | email=%s | variant_id=%s | sku=%s | quantity=%s | created=%s",
        request.user.id,
        request.user.email,
        variant.id,
        variant.sku,
        cart_item.quantity,
        item_created,
    )

    cart_count = cart.total_items

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Product added to cart.',
            'cart_count': cart_count,
        })

    messages.success(request, "Product added to cart.")

    if request.POST.get('next') == 'checkout':
        return redirect('checkout')

    return redirect(request.META.get('HTTP_REFERER', 'cart_view'))


@user_required
def increase_cart_item(request, item_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid increase cart item request method | user_id=%s | email=%s | item_id=%s | method=%s",
            request.user.id,
            request.user.email,
            item_id,
            request.method,
        )
        
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    if cart_item.quantity >= MAX_CART_QUANTITY:
        
        logger.warning(
            "User attempted to exceed max cart quantity | user_id=%s | email=%s | item_id=%s | variant_id=%s | current_quantity=%s",
            request.user.id,
            request.user.email,
            cart_item.id,
            cart_item.variant.id,
            cart_item.quantity,
        )
        
        messages.error(request, f"Maximum {MAX_CART_QUANTITY} quantity allowed.")
        return redirect('cart_view')

    if cart_item.quantity >= cart_item.variant.stock:
        
        logger.warning(
            "User attempted to increase cart beyond stock | user_id=%s | email=%s | item_id=%s | variant_id=%s | current_quantity=%s | stock=%s",
            request.user.id,
            request.user.email,
            cart_item.id,
            cart_item.variant.id,
            cart_item.quantity,
            cart_item.variant.stock,
        )
        
        messages.error(request, "Cannot increase beyond available stock.")
        return redirect('cart_view')

    cart_item.quantity += 1
    cart_item.save(update_fields=['quantity', 'updated_at'])
    
    logger.info(
        "User increased cart item quantity | user_id=%s | email=%s | item_id=%s | variant_id=%s | new_quantity=%s",
        request.user.id,
        request.user.email,
        cart_item.id,
        cart_item.variant.id,
        cart_item.quantity,
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        cart = cart_item.cart

        offer_data = calculate_best_offer(cart_item.variant)
        discounted_subtotal = offer_data['final_price'] * cart_item.quantity

        cart_total = sum(
            calculate_best_offer(item.variant)['final_price'] * item.quantity
            for item in cart.items.all()
        )

        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity,
            'item_subtotal': discounted_subtotal,
            'cart_total': cart_total,
            'cart_count': cart.total_items,
            'max_reached': cart_item.quantity >= min(MAX_CART_QUANTITY, cart_item.variant.stock),
            'min_reached': cart_item.quantity <= 1,
        })

    return redirect('cart_view')


@user_required
def decrease_cart_item(request, item_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid decrease cart item request method | user_id=%s | email=%s | item_id=%s | method=%s",
            request.user.id,
            request.user.email,
            item_id,
            request.method,
        )
        
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )
    
    variant_id = cart_item.variant.id
    old_quantity = cart_item.quantity
    deleted = False
    
    if cart_item.quantity <= 1:
        cart_item.delete()
        messages.success(request, "Item removed from cart.")
        deleted = True
        
        logger.info(
            "User decreased cart item and removed it | user_id=%s | email=%s | item_id=%s | variant_id=%s | old_quantity=%s",
            request.user.id,
            request.user.email,
            item_id,
            variant_id,
            old_quantity,
        )
        
    else:
        cart_item.quantity -= 1
        cart_item.save(update_fields=['quantity', 'updated_at'])
        
        logger.info(
            "User decreased cart item quantity | user_id=%s | email=%s | item_id=%s | variant_id=%s | old_quantity=%s | new_quantity=%s",
            request.user.id,
            request.user.email,
            cart_item.id,
            variant_id,
            old_quantity,
            cart_item.quantity,
        )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        cart = Cart.objects.get(user=request.user)

        if deleted:
            item_subtotal = 0
        else:
            offer_data = calculate_best_offer(cart_item.variant)
            item_subtotal = offer_data['final_price'] * cart_item.quantity

        cart_total = sum(
            calculate_best_offer(item.variant)['final_price'] * item.quantity
            for item in cart.items.all()
        )

        return JsonResponse({
            'success': True,
            'deleted': deleted,
            'quantity': 0 if deleted else cart_item.quantity,
            'item_subtotal': item_subtotal,
            'cart_total': cart_total,
            'cart_count': cart.total_items,
            'max_reached': False if deleted else (cart_item.quantity >= min(MAX_CART_QUANTITY, cart_item.variant.stock)),
            'min_reached': True if deleted else (cart_item.quantity <= 1),
        })

    return redirect('cart_view')


@user_required
def remove_cart_item(request, item_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid remove cart item request method | user_id=%s | email=%s | item_id=%s | method=%s",
            request.user.id,
            request.user.email,
            item_id,
            request.method,
        )
        
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )
    
    variant_id = cart_item.variant.id
    quantity = cart_item.quantity
    cart_item.delete()
    
    logger.info(
        "User removed item from cart | user_id=%s | email=%s | item_id=%s | variant_id=%s | quantity=%s",
        request.user.id,
        request.user.email,
        item_id,
        variant_id,
        quantity,
    )
    
    messages.success(request, "Item removed from cart.")

    return redirect('cart_view')


@never_cache
@user_required
def wishlist_view(request):
    wishlist_items = (
        Wishlist.objects
        .filter(user=request.user)
        .select_related('variant', 'variant__product', 'variant__product__category')
        .prefetch_related('variant__images')
        .order_by('-created_at')
    )

    paginator = Paginator(wishlist_items, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for item in page_obj:
        item.offer_data = calculate_best_offer(item.variant)
        item.is_available = is_variant_available(item.variant)
        
    logger.info(
        "User viewed wishlist | user_id=%s | email=%s | total_items=%s | page=%s",
        request.user.id,
        request.user.email,
        wishlist_items.count(),
        page_number or 1,
    )    

    return render(request, 'cart/wishlist.html', {
        'wishlist_items': page_obj,
        'page_obj': page_obj,
        'total_wishlist_items': wishlist_items.count(),
    })


@user_required
def add_to_wishlist(request, variant_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid add to wishlist request method | user_id=%s | email=%s | variant_id=%s | method=%s",
            request.user.id,
            request.user.email,
            variant_id,
            request.method,
        )
        
        return redirect('home')

    variant = get_object_or_404(
        Variant,
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )

    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        variant=variant
    )

    if created:
        
        logger.info(
            "User added item to wishlist | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )
        
        messages.success(request, "Product added to wishlist.")
    else:
        
        logger.info(
            "User attempted to add existing wishlist item | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )

        
        messages.info(request, "Product is already in your wishlist.")

    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


@user_required
def remove_from_wishlist(request, variant_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid remove from wishlist request method | user_id=%s | email=%s | variant_id=%s | method=%s",
            request.user.id,
            request.user.email,
            variant_id,
            request.method,
        )
        
        return redirect('wishlist_view')

    deleted_count, _ = Wishlist.objects.filter(
        user=request.user,
        variant_id=variant_id
    ).delete()
    
    logger.info(
        "User removed item from wishlist | user_id=%s | email=%s | variant_id=%s | deleted_count=%s",
        request.user.id,
        request.user.email,
        variant_id,
        deleted_count,
    )

    messages.success(request, "Product removed from wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


@user_required
def toggle_wishlist(request, variant_id):
    if request.method != 'POST':
        
        logger.warning(
            "Invalid toggle wishlist request method | user_id=%s | email=%s | variant_id=%s | method=%s",
            request.user.id,
            request.user.email,
            variant_id,
            request.method,
        )
        
        return redirect('home')

    variant = get_object_or_404(
        Variant,
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )

    wishlist_item = Wishlist.objects.filter(
        user=request.user,
        variant=variant
    ).first()

    if wishlist_item:
        wishlist_item.delete()
        
        logger.info(
            "User toggled wishlist off | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_wishlisted': False,
                'wishlist_count': Wishlist.objects.filter(user=request.user).count(),
                'message': 'Product removed from wishlist.'
            })

        messages.success(request, "Product removed from wishlist.")

    else:
        Wishlist.objects.create(user=request.user, variant=variant)
        
        logger.info(
            "User toggled wishlist on | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_wishlisted': True,
                'wishlist_count': Wishlist.objects.filter(user=request.user).count(),
                'message': 'Product added to wishlist.'
            })

        messages.success(request, "Product added to wishlist.")

    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))

@user_required
@login_required
def buy_now(request, variant_id):
    variant = get_object_or_404(
        Variant,
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
        product__category__is_active=True,
        product__category__is_deleted=False,
    )

    if variant.stock <= 0:
        
        logger.warning(
            "User attempted buy now for out-of-stock item | user_id=%s | email=%s | variant_id=%s | sku=%s",
            request.user.id,
            request.user.email,
            variant.id,
            variant.sku,
        )
        
        messages.error(request, "Product is out of stock.")
        return redirect('product_detail', variant_id=variant.id)

    request.session['buy_now_variant_id'] = variant.id
    request.session['buy_now_quantity'] = 1
    
    logger.info(
        "User started buy now checkout | user_id=%s | email=%s | variant_id=%s | sku=%s",
        request.user.id,
        request.user.email,
        variant.id,
        variant.sku,
    )

    return redirect('checkout')