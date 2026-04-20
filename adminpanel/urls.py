from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard'),
    path('login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.admin_logout_view, name='admin_logout'),
    
    path('users/', views.user_management_view, name='user_management'),
    path('users/block/<int:user_id>/', views.block_user_view, name='block_user'),
    path('users/unblock/<int:user_id>/', views.unblock_user_view, name='unblock_user'),
]