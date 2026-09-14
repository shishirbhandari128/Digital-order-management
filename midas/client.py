"""MIDAS adapter clients.

Domain code must never construct MIDAS payloads directly. It calls the typed
methods on ``MidasClientInterface`` (obtained via ``midas.services.get_midas_client``)
and only ever sees the ``PatientAdmission`` dataclass and the exceptions below.
"""
import copy
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone


class MidasClientError(Exception):
    """Base class for all MIDAS adapter errors."""


class PatientNotFoundError(MidasClientError):
    """Raised when a MIDAS id is unknown or the patient is no longer admitted."""


class CreditFrozenError(MidasClientError):
    """Raised when the patient has an active credit freeze in MIDAS."""


class ChargeFailedError(MidasClientError):
    """Raised when MIDAS rejects a charge, refund, or reversal request."""


@dataclass(frozen=True)
class PatientAdmission:
    midas_id: str
    name: str
    admission_status: str
    ward_name: str
    bed_number: str
    credit_balance: Decimal
    credit_frozen: bool = False


class MidasClientInterface(ABC):
    """Contract every MIDAS backend (stub or live HTTP) must satisfy."""

    @abstractmethod
    def verify_patient(self, midas_id: str) -> PatientAdmission:
        ...

    @abstractmethod
    def check_credit_eligibility(self, midas_id: str, amount: Decimal) -> bool:
        ...

    @abstractmethod
    def post_charge(self, midas_id: str, amount: Decimal, idempotency_key: str) -> str:
        """Posts a charge to the patient's hospital bill and returns MIDAS's external reference."""

    @abstractmethod
    def refund_charge(self, external_reference: str, amount: Decimal, idempotency_key: str) -> str:
        ...

    @abstractmethod
    def reverse_charge(self, external_reference: str, idempotency_key: str) -> str:
        ...


def _charge_reference(prefix: str = 'MIDAS-CHG') -> str:
    return f'{prefix}-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}'


class StubMidasClient(MidasClientInterface):
    """In-memory MIDAS simulator for local development and contract testing.

    Each instance starts from a fresh copy of the built-in test registry so
    that balance mutations from one request never leak into another.
    """

    _BASE_REGISTRY = {
        'HAMS-101': {
            'name': 'Ram Bahadur Shrestha',
            'admission_status': 'admitted',
            'ward_name': 'ICU Ward 3',
            'bed_number': 'Bed 12',
            'credit_balance': Decimal('5000.00'),
            'credit_frozen': False,
        },
        'HAMS-102': {
            'name': 'Sita Devi Thapa',
            'admission_status': 'admitted',
            'ward_name': 'General Ward 1',
            'bed_number': 'Bed 05',
            'credit_balance': Decimal('0.00'),
            'credit_frozen': False,
        },
        'HAMS-103': {
            'name': 'Hari Prasad Sharma',
            'admission_status': 'discharged',
            'ward_name': '',
            'bed_number': '',
            'credit_balance': Decimal('0.00'),
            'credit_frozen': False,
        },
        'HAMS-104': {
            'name': 'Gita Karki',
            'admission_status': 'admitted',
            'ward_name': 'Maternity Ward',
            'bed_number': 'Bed 02',
            'credit_balance': Decimal('3000.00'),
            'credit_frozen': False,
        },
    }

    def __init__(self):
        self._registry = copy.deepcopy(self._BASE_REGISTRY)

    def _record(self, midas_id: str) -> dict:
        record = self._registry.get(midas_id)
        if record is None or record['admission_status'] != 'admitted':
            raise PatientNotFoundError(f'MIDAS id {midas_id!r} is unknown or not currently admitted.')
        return record

    def verify_patient(self, midas_id: str) -> PatientAdmission:
        record = self._record(midas_id)
        if record['credit_frozen']:
            raise CreditFrozenError(f'Patient {midas_id!r} has an active credit freeze.')
        return PatientAdmission(midas_id=midas_id, **record)

    def check_credit_eligibility(self, midas_id: str, amount: Decimal) -> bool:
        record = self._record(midas_id)
        if record['credit_frozen']:
            return False
        return record['credit_balance'] >= amount

    def post_charge(self, midas_id: str, amount: Decimal, idempotency_key: str) -> str:
        record = self._record(midas_id)
        if record['credit_frozen'] or record['credit_balance'] < amount:
            raise ChargeFailedError(f'Insufficient MIDAS credit balance for patient {midas_id!r}.')
        record['credit_balance'] -= amount
        return _charge_reference()

    def refund_charge(self, external_reference: str, amount: Decimal, idempotency_key: str) -> str:
        return _charge_reference(prefix='MIDAS-RFD')

    def reverse_charge(self, external_reference: str, idempotency_key: str) -> str:
        return _charge_reference(prefix='MIDAS-REV')


class HttpMidasClient(MidasClientInterface):
    """Live MIDAS backend. Talks to the hospital's REST/JSON service."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0, max_retries: int = 2):
        self.base_url = base_url.rstrip('/') + '/'
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict:
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def _request(self, method: str, path: str, *, json: dict | None = None, safe: bool = True) -> dict:
        import requests

        url = self.base_url + path.lstrip('/')
        attempts = self.max_retries + 1 if safe else 1
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                response = requests.request(method, url, json=json, headers=self._headers(), timeout=self.timeout)
                if response.status_code == 404:
                    raise PatientNotFoundError(f'MIDAS returned 404 for {path}.')
                if response.status_code == 402:
                    raise CreditFrozenError(f'MIDAS returned 402 for {path}.')
                response.raise_for_status()
                return response.json()
            except (PatientNotFoundError, CreditFrozenError):
                raise
            except requests.RequestException as exc:
                last_exc = exc
                continue
        raise ChargeFailedError(f'MIDAS request to {path} failed after {attempts} attempt(s): {last_exc}')

    def verify_patient(self, midas_id: str) -> PatientAdmission:
        payload = self._request('GET', f'patients/{midas_id}/')
        return PatientAdmission(
            midas_id=midas_id,
            name=payload['name'],
            admission_status=payload['admission_status'],
            ward_name=payload.get('ward_name', ''),
            bed_number=payload.get('bed_number', ''),
            credit_balance=Decimal(str(payload.get('credit_balance', '0'))),
            credit_frozen=bool(payload.get('credit_frozen', False)),
        )

    def check_credit_eligibility(self, midas_id: str, amount: Decimal) -> bool:
        payload = self._request(
            'POST', f'patients/{midas_id}/credit-check/', json={'amount': str(amount)},
        )
        return bool(payload.get('eligible', False))

    def post_charge(self, midas_id: str, amount: Decimal, idempotency_key: str) -> str:
        # Charge posting must never be silently retried: a lost response could double-bill the patient.
        payload = self._request(
            'POST', f'patients/{midas_id}/charges/',
            json={'amount': str(amount), 'idempotency_key': idempotency_key},
            safe=False,
        )
        return payload['external_reference']

    def refund_charge(self, external_reference: str, amount: Decimal, idempotency_key: str) -> str:
        payload = self._request(
            'POST', f'charges/{external_reference}/refund/',
            json={'amount': str(amount), 'idempotency_key': idempotency_key},
            safe=False,
        )
        return payload['external_reference']

    def reverse_charge(self, external_reference: str, idempotency_key: str) -> str:
        payload = self._request(
            'POST', f'charges/{external_reference}/reverse/',
            json={'idempotency_key': idempotency_key},
            safe=False,
        )
        return payload['external_reference']
