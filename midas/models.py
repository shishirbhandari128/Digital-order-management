import uuid

from django.db import models


class MidasAction(models.TextChoices):
    VERIFY_PATIENT = 'verify_patient', 'Verify Patient'
    CHECK_CREDIT = 'check_credit', 'Check Credit Eligibility'
    POST_CHARGE = 'post_charge', 'Post Charge'
    REFUND_CHARGE = 'refund_charge', 'Refund Charge'
    REVERSE_CHARGE = 'reverse_charge', 'Reverse Charge'


class MidasOutcome(models.TextChoices):
    SUCCESS = 'success', 'Success'
    FAILURE = 'failure', 'Failure'


class MidasAuditLog(models.Model):
    """Integration audit trail for every MIDAS call.

    Stores only the correlation id, the MIDAS id (an administrative reference,
    not clinical data), latency, and outcome/error metadata -- never
    credentials or raw MIDAS response bodies.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    correlation_id = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=32, choices=MidasAction.choices)
    midas_id = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    external_reference = models.CharField(max_length=128, blank=True)
    outcome = models.CharField(max_length=16, choices=MidasOutcome.choices)
    latency_ms = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'idempotency_key']),
        ]

    def __str__(self) -> str:
        return f'{self.action} [{self.outcome}] {self.correlation_id}'
