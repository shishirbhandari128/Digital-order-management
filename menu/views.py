from django.db.models import Q
from rest_framework import generics

from .models import Item
from .serializers import ItemSerializer


class ItemListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ItemSerializer

    def get_queryset(self):
        queryset = Item.objects.select_related('outlet').all()
        if not (self.request.user and self.request.user.is_authenticated):
            queryset = queryset.filter(is_active=True)

        outlet_id = self.request.query_params.get('outlet')
        if outlet_id:
            queryset = queryset.filter(outlet_id=outlet_id)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        return queryset


class ItemRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Item.objects.select_related('outlet').all()
    serializer_class = ItemSerializer
