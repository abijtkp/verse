from .models import Cart, Wishlist


def cart_count(request):
    cart_total = 0
    wishlist_total = 0

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()

        if cart:
            cart_total = cart.total_items

        wishlist_total = Wishlist.objects.filter(user=request.user).count()

    return {
        'cart_count': cart_total,
        'wishlist_count': wishlist_total,
    }