from django.urls import path

from . import views

app_name = 'outlets'

urlpatterns = [
    path('', views.OutletListCreateAPIView.as_view(), name='outlet-list-create'),
    path('<uuid:pk>/', views.OutletRetrieveUpdateDestroyAPIView.as_view(), name='outlet-detail'),
]
