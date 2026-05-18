from django.urls import path
from . import views

urlpatterns = [
    path('', views.coupon_list_view, name='coupon_list'),
    path('add/', views.add_coupon_view, name='add_coupon'),
    path('edit/<int:coupon_id>/', views.edit_coupon_view, name='edit_coupon'),
    path('toggle-status/<int:coupon_id>/', views.toggle_coupon_status_view, name='toggle_coupon_status'),
]