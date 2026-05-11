from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('place-order/', views.place_order_view, name='place_order'),
    path('success/<str:order_id>/', views.order_success_view, name='order_success'),
    path('my-orders/', views.order_list_view, name='order_list'),
    path('details/<str:order_id>/', views.order_detail_view, name='order_detail'),
    path('cancel/<str:order_id>/', views.cancel_order, name='cancel_order'),
    path('cancel-item/<int:item_id>/', views.cancel_order_item, name='cancel_order_item'),
    path('invoice/<str:order_id>/', views.download_invoice, name='download_invoice'),
    path('return/<str:order_id>/', views.return_order, name='return_order'),
    path('return-item/<int:item_id>/', views.return_order_item, name='return_order_item'),
]