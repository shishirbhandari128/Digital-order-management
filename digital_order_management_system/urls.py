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
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_simplejwt.views import TokenRefreshView

@extend_schema(exclude=True)
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
            'outlets': reverse('outlets:outlet-list-create', request=request, format=format),
            'items': reverse('menu:item-list-create', request=request, format=format),
            'locations': reverse('customers:location-list-create', request=request, format=format),
            'qr_codes': reverse('customers:qrcode-list-create', request=request, format=format),
            'patients': reverse('customers:patient-list-create', request=request, format=format),
            'patient_verify': reverse('customers:patient-verify', request=request, format=format),
            'visitors': reverse('customers:visitor-list-create', request=request, format=format),
            'orders': reverse('orders:order-list-create', request=request, format=format),
            'visitor_checkout': reverse('orders:visitor-checkout', request=request, format=format),
            'visitor_order_history': reverse('orders:visitor-history', request=request, format=format),
            'patient_checkout': reverse('orders:patient-checkout', request=request, format=format),
            'patient_active_orders': reverse('orders:patient-active', request=request, format=format),
            'transactions': reverse('billing:transaction-list-create', request=request, format=format),
            'feedback': reverse('feedback:feedback-list-create', request=request, format=format),
            'feedback_submit': reverse('feedback:feedback-submit', request=request, format=format),
            'browsable_api_login': reverse('rest_framework:login', request=request, format=format),
            'openapi_schema': reverse('schema', request=request, format=format),
            'swagger_docs': reverse('swagger-ui', request=request, format=format),
            'redoc_docs': reverse('redoc', request=request, format=format),
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

    # OpenAPI schema + interactive docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Versioned business endpoints
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/outlets/', include('outlets.urls')),
    path('api/v1/items/', include('menu.urls')),
    path('api/v1/customers/', include('customers.urls')),
    path('api/v1/orders/', include('orders.urls')),
    path('api/v1/transactions/', include('billing.urls')),
    path('api/v1/feedback/', include('feedback.urls')),
]



