from django.urls import path
from . import views

urlpatterns = [
    path('', views.wallet_view, name='wallet'),
    path('wallet/add-money/', views.add_money_view, name='add_money'),
    path('wallet/create-topup/', views.create_wallet_topup_view, name='create_wallet_topup'),
    path('wallet/verify-topup/', views.verify_wallet_topup_view, name='verify_wallet_topup'),
]