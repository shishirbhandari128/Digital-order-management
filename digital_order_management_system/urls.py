"""
URL configuration for digital_order_management_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_simplejwt.views import TokenRefreshView

@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'status': 'online',
        'message': 'Welcome to Digital Order Management System API',
        'endpoints': {
            'admin': reverse('admin:index', request=request, format=format),
            'register': reverse('accounts:register', request=request, format=format),
            'login': reverse('accounts:login', request=request, format=format),
            'logout': reverse('accounts:logout', request=request, format=format),
            'token_refresh': reverse('token_refresh', request=request, format=format),
            'browsable_api_login': reverse('rest_framework:login', request=request, format=format),
        }
    })

urlpatterns = [
    # Root API view
    path('', api_root, name='api-root'),

    # Admin
    path('admin/', admin.site.urls),

    # JWT token refresh
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Browsable API login/logout (session auth in browser)
    path('api-auth/', include('rest_framework.urls')),

    # Versioned business endpoints
    path('api/v1/accounts/', include('accounts.urls')),
]
