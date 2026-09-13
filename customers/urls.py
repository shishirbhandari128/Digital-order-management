from django.urls import path

from . import views

app_name = 'customers'

urlpatterns = [
    path('qr/<uuid:qr_id>/', views.QRLocationLookupAPIView.as_view(), name='qr-lookup'),
    path('locations/', views.LocationListCreateAPIView.as_view(), name='location-list-create'),
    path('locations/<uuid:pk>/', views.LocationRetrieveUpdateDestroyAPIView.as_view(), name='location-detail'),
    path('qr-codes/', views.QRCodeListCreateAPIView.as_view(), name='qrcode-list-create'),
    path('qr-codes/<uuid:pk>/', views.QRCodeRetrieveUpdateDestroyAPIView.as_view(), name='qrcode-detail'),
    path('patients/', views.PatientListCreateAPIView.as_view(), name='patient-list-create'),
    path('patients/<uuid:pk>/', views.PatientRetrieveUpdateDestroyAPIView.as_view(), name='patient-detail'),
    path('visitors/', views.VisitorListCreateAPIView.as_view(), name='visitor-list-create'),
    path('visitors/<uuid:pk>/', views.VisitorRetrieveUpdateDestroyAPIView.as_view(), name='visitor-detail'),
]
