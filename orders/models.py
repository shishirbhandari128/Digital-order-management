import uuid

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from customers.models import Patient, QRCode, Visitor
from menu.models import Item


class OrderStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
    CONFIRMED = 'confirmed', 'Confirmed'
    ROUTED = 'routed', 'Routed'
    PREPARING = 'preparing', 'Preparing'
    READY = 'ready', 'Ready'
    ASSIGNED = 'assigned', 'Assigned'
    PICKED_UP = 'picked_up', 'Picked Up'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qr = models.ForeignKey(QRCode, on_delete=models.PROTECT, related_name='orders', null=True, blank=True)
    batch_id = models.UUIDField(db_index=True, help_text='Shared identifier for all lines placed in one checkout batch')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='orders')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=32, choices=OrderStatus.choices, default=OrderStatus.DRAFT)
    assigned_delivery_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='deliveries', null=True, blank=True
    )
    is_settled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='orders', null=True, blank=True)
    visitor = models.ForeignKey(Visitor, on_delete=models.PROTECT, related_name='orders', null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self) -> str:
        return str(self.id)
