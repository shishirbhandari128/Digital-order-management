from django.urls import path

from . import views

app_name = 'menu'

urlpatterns = [
    path('', views.ItemListCreateAPIView.as_view(), name='item-list-create'),
    path('<uuid:pk>/', views.ItemRetrieveUpdateDestroyAPIView.as_view(), name='item-detail'),
]
