from rest_framework import serializers

from orders.models import Order

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())

    class Meta:
        model = Transaction
        fields = [
            'id', 'order', 'is_cod', 'is_midas_credit', 'status', 'amount', 'external_reference', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
