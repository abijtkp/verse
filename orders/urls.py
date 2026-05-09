from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('place-order/', views.place_order_view, name='place_order'),
    path('success/<str:order_id>/', views.order_success_view, name='order_success'),
    path('my-orders/', views.order_list_view, name='order_list'),
    path('details/<str:order_id>/', views.order_detail_view, name='order_detail'),
]