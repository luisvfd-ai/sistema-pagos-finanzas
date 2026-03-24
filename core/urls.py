from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth / usuarios
    path('', include('pagos.urls_auth')),

    # Módulo financiero
    path('pagos/', include('pagos.urls_dashboard')),
]