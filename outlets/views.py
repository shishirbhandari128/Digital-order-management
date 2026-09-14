from rest_framework import generics

from .models import Outlet
from .serializers import OutletSerializer


class OutletListCreateAPIView(generics.ListCreateAPIView):
    queryset = Outlet.objects.all()
    serializer_class = OutletSerializer


class OutletRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Outlet.objects.all()
    serializer_class = OutletSerializer
