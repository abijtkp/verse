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

    for item in cart_items:
        item.offer_data = calculate_best_offer(item.variant)
        item.discounted_price = item.offer_data['final_price']
        item.discount_amount = item.offer_data['discount_amount']
        item.discounted_subtotal = item.discounted_price * item.quantity

        cart_total += item.discounted_subtotal

    has_address = Address.objects.filter(user=request.user).exists() 
    
    return render(request, 'cart/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'has_address': has_address,
        'cart_total': cart_total,
    })


@user_required
def add_to_cart(request, variant_id):
    if request.method != 'POST':
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
            messages.error(request, f"You can add maximum {MAX_CART_QUANTITY} quantity only.")
            return redirect(request.META.get('HTTP_REFERER', 'cart_view'))

        if cart_item.quantity >= variant.stock:
            messages.error(request, "Cannot add more than available stock.")
            return redirect(request.META.get('HTTP_REFERER', 'cart_view'))

        cart_item.quantity += 1
        cart_item.save(update_fields=['quantity', 'updated_at'])
        
    Wishlist.objects.filter(
        user=request.user,
        variant=variant
    ).delete()   

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
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    if cart_item.quantity >= MAX_CART_QUANTITY:
        messages.error(request, f"Maximum {MAX_CART_QUANTITY} quantity allowed.")
        return redirect('cart_view')

    if cart_item.quantity >= cart_item.variant.stock:
        messages.error(request, "Cannot increase beyond available stock.")
        return redirect('cart_view')

    cart_item.quantity += 1
    cart_item.save(update_fields=['quantity', 'updated_at'])

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
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    deleted = False
    if cart_item.quantity <= 1:
        cart_item.delete()
        messages.success(request, "Item removed from cart.")
        deleted = True
    else:
        cart_item.quantity -= 1
        cart_item.save(update_fields=['quantity', 'updated_at'])

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
        return redirect('cart_view')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    cart_item.delete()
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

    return render(request, 'cart/wishlist.html', {
        'wishlist_items': wishlist_items,
    })


@user_required
def add_to_wishlist(request, variant_id):
    if request.method != 'POST':
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
        messages.success(request, "Product added to wishlist.")
    else:
        messages.info(request, "Product is already in your wishlist.")

    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


@user_required
def remove_from_wishlist(request, variant_id):
    if request.method != 'POST':
        return redirect('wishlist_view')

    Wishlist.objects.filter(
        user=request.user,
        variant_id=variant_id
    ).delete()

    messages.success(request, "Product removed from wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


@user_required
def toggle_wishlist(request, variant_id):
    if request.method != 'POST':
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

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_wishlisted': True,
                'wishlist_count': Wishlist.objects.filter(user=request.user).count(),
                'message': 'Product added to wishlist.'
            })

        messages.success(request, "Product added to wishlist.")

    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


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
        messages.error(request, "Product is out of stock.")
        return redirect('product_detail', variant_id=variant.id)

    request.session['buy_now_variant_id'] = variant.id
    request.session['buy_now_quantity'] = 1

    return redirect('checkout')