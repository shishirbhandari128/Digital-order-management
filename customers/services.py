from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

from midas.client import PatientAdmission

from .models import Location, Patient, QRCode

PATIENT_SESSION_TOKEN_LIFETIME_MINUTES = 60


def location_matches_admission(location: Location, admission: PatientAdmission) -> bool:
    def _norm(value: str) -> str:
        return value.strip().casefold()

    return (
        _norm(location.ward_name) == _norm(admission.ward_name)
        and _norm(location.bed_number) == _norm(admission.bed_number)
    )


def generate_patient_session_token(patient: Patient, qr: QRCode) -> str:
    """Short-lived, stateless proof that this patient was just verified at this bedside.

    Not a Django auth token (patients are not Django users) -- a plain signed
    JWT carrying only non-clinical identifiers, for the frontend to attach to
    the subsequent checkout request.
    """
    now = timezone.now()
    payload = {
        'patient_id': str(patient.id),
        'midas_id': patient.midas_id,
        'qr_id': str(qr.id),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=PATIENT_SESSION_TOKEN_LIFETIME_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
