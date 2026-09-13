"""Domain-facing MIDAS façade.

Wraps a raw ``MidasClientInterface`` backend with audit logging and
charge idempotency so that ``orders``/``customers`` code never talks to
``StubMidasClient``/``HttpMidasClient`` directly.
"""
import time
import uuid
from decimal import Decimal

from django.conf import settings

from .client import (
    ChargeFailedError,
    HttpMidasClient,
    MidasClientError,
    MidasClientInterface,
    PatientAdmission,
    StubMidasClient,
)
from .models import MidasAction, MidasAuditLog, MidasOutcome


class MidasService:
    def __init__(self, client: MidasClientInterface):
        self._client = client

    def verify_patient(self, midas_id: str, correlation_id: str | None = None) -> PatientAdmission:
        return self._call(MidasAction.VERIFY_PATIENT, midas_id, correlation_id, lambda: self._client.verify_patient(midas_id))

    def check_credit_eligibility(self, midas_id: str, amount: Decimal, correlation_id: str | None = None) -> bool:
        return self._call(
            MidasAction.CHECK_CREDIT, midas_id, correlation_id,
            lambda: self._client.check_credit_eligibility(midas_id, amount),
        )

    def post_charge(self, midas_id: str, amount: Decimal, idempotency_key: str, correlation_id: str | None = None) -> str:
        existing = MidasAuditLog.objects.filter(
            action=MidasAction.POST_CHARGE, idempotency_key=idempotency_key, outcome=MidasOutcome.SUCCESS,
        ).first()
        if existing is not None:
            return existing.external_reference

        return self._call(
            MidasAction.POST_CHARGE, midas_id, correlation_id,
            lambda: self._client.post_charge(midas_id, amount, idempotency_key),
            idempotency_key=idempotency_key,
        )

    def refund_charge(
        self, midas_id: str, external_reference: str, amount: Decimal, idempotency_key: str,
        correlation_id: str | None = None,
    ) -> str:
        existing = MidasAuditLog.objects.filter(
            action=MidasAction.REFUND_CHARGE, idempotency_key=idempotency_key, outcome=MidasOutcome.SUCCESS,
        ).first()
        if existing is not None:
            return existing.external_reference

        return self._call(
            MidasAction.REFUND_CHARGE, midas_id, correlation_id,
            lambda: self._client.refund_charge(external_reference, amount, idempotency_key),
            idempotency_key=idempotency_key,
        )

    def reverse_charge(
        self, midas_id: str, external_reference: str, idempotency_key: str, correlation_id: str | None = None,
    ) -> str:
        existing = MidasAuditLog.objects.filter(
            action=MidasAction.REVERSE_CHARGE, idempotency_key=idempotency_key, outcome=MidasOutcome.SUCCESS,
        ).first()
        if existing is not None:
            return existing.external_reference

        return self._call(
            MidasAction.REVERSE_CHARGE, midas_id, correlation_id,
            lambda: self._client.reverse_charge(external_reference, idempotency_key),
            idempotency_key=idempotency_key,
        )

    def _call(self, action, midas_id, correlation_id, fn, idempotency_key=''):
        correlation_id = correlation_id or uuid.uuid4().hex
        started = time.monotonic()
        try:
            result = fn()
        except MidasClientError as exc:
            MidasAuditLog.objects.create(
                correlation_id=correlation_id,
                action=action,
                midas_id=midas_id,
                idempotency_key=idempotency_key,
                outcome=MidasOutcome.FAILURE,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_code=type(exc).__name__,
            )
            raise

        external_reference = result if isinstance(result, str) else ''
        MidasAuditLog.objects.create(
            correlation_id=correlation_id,
            action=action,
            midas_id=midas_id,
            idempotency_key=idempotency_key,
            external_reference=external_reference,
            outcome=MidasOutcome.SUCCESS,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return result


def get_midas_client() -> MidasService:
    """Factory: builds the configured backend (stub or live HTTP) wrapped in the audited service façade."""
    backend = getattr(settings, 'MIDAS_BACKEND', 'stub')
    if backend == 'http':
        raw_client: MidasClientInterface = HttpMidasClient(
            base_url=settings.MIDAS_BASE_URL,
            api_key=settings.MIDAS_API_KEY,
            timeout=settings.MIDAS_TIMEOUT,
            max_retries=settings.MIDAS_MAX_RETRIES,
        )
    else:
        raw_client = StubMidasClient()
    return MidasService(raw_client)


__all__ = ['MidasService', 'get_midas_client', 'ChargeFailedError']
