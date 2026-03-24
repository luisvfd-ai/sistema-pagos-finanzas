from django.urls import path
from . import views_auth

urlpatterns = [
    path('', views_auth.home_redirect, name='home_redirect'),
    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout_view'),

    path('usuarios/', views_auth.usuarios_lista, name='usuarios_lista'),
    path('usuarios/nuevo/', views_auth.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views_auth.usuario_editar, name='usuario_editar'),
]