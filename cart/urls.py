from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_view, name='cart_view'),
    path('add/<int:variant_id>/', views.add_to_cart, name='add_to_cart'),
    path('buy-now/<int:variant_id>/', views.buy_now, name='buy_now'),
    path('increase/<int:item_id>/', views.increase_cart_item, name='increase_cart_item'),
    path('decrease/<int:item_id>/', views.decrease_cart_item, name='decrease_cart_item'),
    path('remove/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),
    
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/add/<int:variant_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:variant_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/toggle/<int:variant_id>/', views.toggle_wishlist, name='toggle_wishlist'),
]