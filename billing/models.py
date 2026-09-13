import uuid

from django.db import models
from simple_history.models import HistoricalRecords

from orders.models import Order


class TransactionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'
    REVERSED = 'reversed', 'Reversed'


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='transactions')
    is_cod = models.BooleanField(default=False)
    is_midas_credit = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    external_reference = models.CharField(
        max_length=128, blank=True, help_text='MIDAS charge/refund/reversal token, when applicable.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self) -> str:
        return str(self.id)
