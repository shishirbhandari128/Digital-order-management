from decimal import Decimal

from django.test import TestCase

from .client import ChargeFailedError, PatientNotFoundError, StubMidasClient
from .models import MidasAuditLog
from .services import MidasService


class StubMidasClientTests(TestCase):
    def setUp(self):
        self.client = StubMidasClient()

    def test_verify_patient_happy_path(self):
        admission = self.client.verify_patient('HAMS-101')
        self.assertEqual(admission.name, 'Ram Bahadur Shrestha')
        self.assertEqual(admission.admission_status, 'admitted')
        self.assertEqual(admission.ward_name, 'ICU Ward 3')
        self.assertEqual(admission.bed_number, 'Bed 12')
        self.assertEqual(admission.credit_balance, Decimal('5000.00'))

    def test_verify_patient_discharged_raises_not_found(self):
        with self.assertRaises(PatientNotFoundError):
            self.client.verify_patient('HAMS-103')

    def test_verify_patient_unknown_id_raises_not_found(self):
        with self.assertRaises(PatientNotFoundError):
            self.client.verify_patient('HAMS-999')

    def test_check_credit_eligibility_rejects_zero_balance(self):
        self.assertFalse(self.client.check_credit_eligibility('HAMS-102', Decimal('50.00')))

    def test_check_credit_eligibility_accepts_within_balance(self):
        self.assertTrue(self.client.check_credit_eligibility('HAMS-101', Decimal('150.00')))

    def test_post_charge_deducts_balance_and_returns_reference(self):
        reference = self.client.post_charge('HAMS-101', Decimal('150.00'), 'idem-1')
        self.assertTrue(reference.startswith('MIDAS-CHG-'))
        self.assertFalse(self.client.check_credit_eligibility('HAMS-101', Decimal('5000.00')))

    def test_post_charge_insufficient_balance_raises(self):
        with self.assertRaises(ChargeFailedError):
            self.client.post_charge('HAMS-102', Decimal('50.00'), 'idem-2')

    def test_instances_do_not_share_mutated_state(self):
        self.client.post_charge('HAMS-101', Decimal('5000.00'), 'idem-3')
        fresh_client = StubMidasClient()
        self.assertTrue(fresh_client.check_credit_eligibility('HAMS-101', Decimal('5000.00')))


class MidasServiceTests(TestCase):
    def setUp(self):
        self.service = MidasService(StubMidasClient())

    def test_post_charge_is_idempotent(self):
        first_reference = self.service.post_charge('HAMS-101', Decimal('150.00'), 'shared-key')
        second_reference = self.service.post_charge('HAMS-101', Decimal('150.00'), 'shared-key')
        self.assertEqual(first_reference, second_reference)
        self.assertEqual(
            MidasAuditLog.objects.filter(idempotency_key='shared-key', outcome='success').count(), 1,
        )

    def test_failed_call_is_audited(self):
        with self.assertRaises(ChargeFailedError):
            self.service.post_charge('HAMS-102', Decimal('50.00'), 'failing-key')
        log = MidasAuditLog.objects.get(idempotency_key='failing-key')
        self.assertEqual(log.outcome, 'failure')
        self.assertEqual(log.error_code, 'ChargeFailedError')

    def test_successful_call_is_audited(self):
        self.service.verify_patient('HAMS-101')
        log = MidasAuditLog.objects.get(action='verify_patient', midas_id='HAMS-101')
        self.assertEqual(log.outcome, 'success')
