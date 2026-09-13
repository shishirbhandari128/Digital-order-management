from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.TransactionListCreateAPIView.as_view(), name='transaction-list-create'),
    path('<uuid:pk>/', views.TransactionRetrieveUpdateDestroyAPIView.as_view(), name='transaction-detail'),
]
