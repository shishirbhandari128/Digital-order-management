from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('visitor/checkout/', views.VisitorCheckoutAPIView.as_view(), name='visitor-checkout'),
    path('visitor/history/', views.VisitorOrderHistoryAPIView.as_view(), name='visitor-history'),
    path('patient/checkout/', views.PatientCheckoutAPIView.as_view(), name='patient-checkout'),
    path('patient/active/', views.PatientActiveOrdersAPIView.as_view(), name='patient-active'),
    path('batch/<uuid:batch_id>/', views.OrderBatchTrackingAPIView.as_view(), name='batch-tracking'),
    path('', views.OrderListCreateAPIView.as_view(), name='order-list-create'),
    path('<uuid:pk>/', views.OrderRetrieveUpdateDestroyAPIView.as_view(), name='order-detail'),
]
