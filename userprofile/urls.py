from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.profile_view, name='profile'),
    path('addresses/', views.address_list, name='address_list'),
    path('edit/', views.edit_profile_view, name='edit_profile'),
    path(
        'change-password/',
        auth_views.PasswordChangeView.as_view(
            template_name='userprofile/change_password.html'
        ),
        name='change_password'
    ),

    path(
        'change-password/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='userprofile/change_password_done.html'
        ),
        name='password_change_done'
    ),  
]