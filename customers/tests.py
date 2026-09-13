from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Location, QRCode, Visitor


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
