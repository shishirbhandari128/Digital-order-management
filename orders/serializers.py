from rest_framework import serializers

from accounts.models import User
from customers.models import Patient, QRCode, Visitor
from menu.models import Item

from .models import Order, OrderStatus

ALLOWED_TRANSITIONS = {
    OrderStatus.DRAFT: {OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED},
    OrderStatus.PENDING_PAYMENT: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.ROUTED, OrderStatus.CANCELLED},
    OrderStatus.ROUTED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.ASSIGNED, OrderStatus.CANCELLED},
    OrderStatus.ASSIGNED: {OrderStatus.PICKED_UP, OrderStatus.CANCELLED},
    OrderStatus.PICKED_UP: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


class OrderSerializer(serializers.ModelSerializer):
    qr = serializers.PrimaryKeyRelatedField(queryset=QRCode.objects.all(), required=False, allow_null=True)
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    assigned_delivery_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all(), required=False, allow_null=True)
    visitor = serializers.PrimaryKeyRelatedField(queryset=Visitor.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'qr',
            'batch_id',
            'item',
            'quantity',
            'unit_price',
            'status',
            'assigned_delivery_user',
            'is_settled',
            'created_at',
            'updated_at',
            'patient',
            'visitor',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        patient = attrs.get('patient', getattr(self.instance, 'patient', None))
        visitor = attrs.get('visitor', getattr(self.instance, 'visitor', None))
        if not patient and not visitor:
            raise serializers.ValidationError('An order must be linked to a patient or a visitor.')
        if patient and visitor:
            raise serializers.ValidationError('An order cannot be linked to both a patient and a visitor.')

        new_status = attrs.get('status')
        if self.instance is not None and new_status is not None and new_status != self.instance.status:
            allowed = ALLOWED_TRANSITIONS.get(self.instance.status, set())
            if new_status not in allowed:
                raise serializers.ValidationError(
                    {'status': f'Cannot transition from {self.instance.status} to {new_status}.'}
                )
        return attrs


class VisitorInputSerializer(serializers.Serializer):
    """Visitor identification for checkout: no uniqueness check, since an existing mobile
    number is resolved to the existing visitor rather than rejected."""
    name = serializers.CharField(max_length=255)
    mobile = serializers.CharField(max_length=20)


class CheckoutItemSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class VisitorCheckoutSerializer(serializers.Serializer):
    visitor = VisitorInputSerializer()
    qr_id = serializers.UUIDField()
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    special_instructions = serializers.CharField(required=False, allow_blank=True)


class PatientCheckoutSerializer(serializers.Serializer):
    midas_id = serializers.CharField(max_length=64)
    qr_id = serializers.UUIDField()
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    special_instructions = serializers.CharField(required=False, allow_blank=True)


class VisitorCheckoutResponseSerializer(serializers.Serializer):
    """Documents the response shape of VisitorCheckoutAPIView (built by hand, not via .data)."""
    batch_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    payment_method = serializers.CharField()
    payment_status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_location = serializers.CharField()
    items_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class PatientCheckoutResponseSerializer(serializers.Serializer):
    """Documents the response shape of PatientCheckoutAPIView (built by hand, not via .data)."""
    batch_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    payment_method = serializers.CharField()
    payment_status = serializers.CharField()
    midas_charge_reference = serializers.CharField()
    total_charged = serializers.DecimalField(max_digits=10, decimal_places=2)
    patient_name = serializers.CharField()
    delivery_location = serializers.CharField()
    created_at = serializers.DateTimeField()


class BatchTrackingStageSerializer(serializers.Serializer):
    status = serializers.CharField()
    timestamp = serializers.DateTimeField(allow_null=True)
    completed = serializers.BooleanField()


class DeliveryPersonSerializer(serializers.Serializer):
    name = serializers.CharField(allow_null=True)
    assigned = serializers.BooleanField()


class BatchTrackingResponseSerializer(serializers.Serializer):
    """Documents the response shape of OrderBatchTrackingAPIView (built by hand, not via .data)."""
    batch_id = serializers.UUIDField()
    overall_status = serializers.CharField()
    status_progression = BatchTrackingStageSerializer(many=True)
    delivery_person = DeliveryPersonSerializer()
    is_delivered = serializers.BooleanField()
    feedback_submitted = serializers.BooleanField()


class VisitorBatchSummarySerializer(serializers.Serializer):
    """Documents one entry of VisitorOrderHistoryAPIView's response list."""
    batch_id = serializers.UUIDField()
    status = serializers.CharField()
    items_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    created_at = serializers.DateTimeField()


class PatientActiveBatchSummarySerializer(serializers.Serializer):
    """Documents one entry of PatientActiveOrdersAPIView's response list."""
    batch_id = serializers.UUIDField()
    status = serializers.CharField()
    items_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_location = serializers.CharField()
    created_at = serializers.DateTimeField()
