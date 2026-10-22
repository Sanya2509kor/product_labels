from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('labels.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='labels/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='labels/logged_out.html'), name='logout'),
]