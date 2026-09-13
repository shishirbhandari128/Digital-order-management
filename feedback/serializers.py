from rest_framework import serializers

from orders.models import Order, OrderStatus

from .models import Feedback


def _validate_deliverable_order(order):
    if order.status != OrderStatus.DELIVERED:
        raise serializers.ValidationError('Feedback can only be submitted for delivered orders.')
    if Feedback.objects.filter(order=order).exists():
        raise serializers.ValidationError('Feedback has already been submitted for this order.')


class FeedbackSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())

    class Meta:
        model = Feedback
        fields = ['id', 'order', 'feedback_type', 'rating', 'feedback_and_others', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_order(self, order):
        if self.instance is None:
            _validate_deliverable_order(order)
        return order


class FeedbackSubmitSerializer(serializers.ModelSerializer):
    order_id = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), source='order')

    class Meta:
        model = Feedback
        fields = ['id', 'order_id', 'feedback_type', 'rating', 'feedback_and_others', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_order_id(self, order):
        _validate_deliverable_order(order)
        return order
