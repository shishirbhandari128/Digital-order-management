from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Location, Patient, QRCode, Visitor


class QRLookupTests(APITestCase):
    def setUp(self):
        self.location = Location.objects.create(
            ward_name='ICU Ward 3', bed_number='Bed 12', is_public_space=True, is_patient_space_only=False,
        )
        self.qr = QRCode.objects.create(location=self.location)

    def test_qr_lookup_is_public_and_returns_location(self):
        url = reverse('customers:qr-lookup', kwargs={'qr_id': self.qr.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['qr_id']), str(self.qr.id))
        self.assertEqual(response.data['location']['ward_name'], 'ICU Ward 3')
        self.assertEqual(set(response.data['allowed_order_types']), {'visitor', 'patient'})

    def test_qr_lookup_restricts_patient_only_space(self):
        patient_location = Location.objects.create(
            ward_name='NICU', bed_number='Bed 1', is_public_space=False, is_patient_space_only=True,
        )
        qr = QRCode.objects.create(location=patient_location)
        url = reverse('customers:qr-lookup', kwargs={'qr_id': qr.id})
        response = self.client.get(url)
        self.assertEqual(response.data['allowed_order_types'], ['patient'])

    def test_qr_lookup_404_for_unknown_qr(self):
        url = reverse('customers:qr-lookup', kwargs={'qr_id': '00000000-0000-0000-0000-000000000000'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VisitorRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse('customers:visitor-list-create')

    def test_registration_creates_new_visitor(self):
        response = self.client.post(self.url, {'name': 'Sarah Jenkins', 'mobile': '9841234567'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Visitor.objects.count(), 1)

    def test_registration_returns_existing_visitor_for_known_mobile(self):
        visitor = Visitor.objects.create(name='Sarah Jenkins', mobile='9841234567')
        response = self.client.post(self.url, {'name': 'Different Name', 'mobile': '9841234567'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['id']), str(visitor.id))
        self.assertEqual(Visitor.objects.count(), 1)

    def test_visitor_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PatientVerifyTests(APITestCase):
    def setUp(self):
        self.url = reverse('customers:patient-verify')
        self.icu_location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.icu_qr = QRCode.objects.create(location=self.icu_location)

    def test_verify_happy_path_syncs_local_patient_and_returns_credit(self):
        response = self.client.post(
            self.url, {'midas_id': 'HAMS-101', 'qr_id': str(self.icu_qr.id)}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['patient']['name'], 'Ram Bahadur Shrestha')
        self.assertEqual(response.data['patient']['admission_status'], 'admitted')
        self.assertEqual(response.data['patient']['ward'], 'ICU Ward 3')
        self.assertEqual(response.data['patient']['bed'], 'Bed 12')
        self.assertTrue(response.data['billing_eligible'])
        self.assertEqual(response.data['credit_limit'], '5000.00')
        self.assertTrue(response.data['session_token'])

        patient = Patient.objects.get(midas_id='HAMS-101')
        self.assertEqual(patient.name, 'Ram Bahadur Shrestha')
        self.assertEqual(patient.location_id, self.icu_location.id)

    def test_verify_upserts_existing_local_patient(self):
        Patient.objects.create(midas_id='HAMS-101', name='Stale Name', location=self.icu_location)
        self.client.post(self.url, {'midas_id': 'HAMS-101', 'qr_id': str(self.icu_qr.id)}, format='json')
        self.assertEqual(Patient.objects.filter(midas_id='HAMS-101').count(), 1)
        self.assertEqual(Patient.objects.get(midas_id='HAMS-101').name, 'Ram Bahadur Shrestha')

    def test_verify_rejects_bed_mismatch(self):
        response = self.client.post(
            self.url, {'midas_id': 'HAMS-104', 'qr_id': str(self.icu_qr.id)}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Patient.objects.filter(midas_id='HAMS-104').exists())

    def test_verify_rejects_discharged_patient(self):
        response = self.client.post(
            self.url, {'midas_id': 'HAMS-103', 'qr_id': str(self.icu_qr.id)}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_rejects_unknown_midas_id(self):
        response = self.client.post(
            self.url, {'midas_id': 'HAMS-999', 'qr_id': str(self.icu_qr.id)}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_404_for_unknown_qr(self):
        response = self.client.post(
            self.url,
            {'midas_id': 'HAMS-101', 'qr_id': '00000000-0000-0000-0000-000000000000'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_reports_zero_credit_as_not_billing_eligible(self):
        general_ward = Location.objects.create(ward_name='General Ward 1', bed_number='Bed 05')
        qr = QRCode.objects.create(location=general_ward)
        response = self.client.post(self.url, {'midas_id': 'HAMS-102', 'qr_id': str(qr.id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['billing_eligible'])
        self.assertEqual(response.data['credit_limit'], '0.00')
