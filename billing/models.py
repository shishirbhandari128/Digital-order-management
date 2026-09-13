import uuid

from django.db import models

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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.id)
