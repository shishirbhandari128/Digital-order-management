from rest_framework import generics, permissions

from .models import Transaction
from .serializers import TransactionSerializer


class TransactionListCreateAPIView(generics.ListCreateAPIView):
    queryset = Transaction.objects.select_related('order').all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]


class TransactionRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Transaction.objects.select_related('order').all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
