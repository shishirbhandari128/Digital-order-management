import uuid
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from billing.models import Transaction, TransactionStatus
from customers.models import Location, Patient, QRCode, Visitor
from menu.models import Item
from outlets.models import Outlet

from .models import Order, OrderStatus


class VisitorCheckoutTests(APITestCase):
    def setUp(self):
        self.url = reverse('orders:visitor-checkout')
        self.outlet = Outlet.objects.create(name='Bakery')
        self.item = Item.objects.create(outlet=self.outlet, name='Croissant', price=Decimal('150.00'))
        self.inactive_item = Item.objects.create(
            outlet=self.outlet, name='Stale Bun', price=Decimal('10.00'), is_active=False,
        )
        self.location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.qr = QRCode.objects.create(location=self.location)
        self.payload = {
            'visitor': {'name': 'Sarah Jenkins', 'mobile': '9841234567'},
            'qr_id': str(self.qr.id),
            'items': [{'item_id': str(self.item.id), 'quantity': 2}],
            'special_instructions': 'Deliver near bedside chair',
        }

    def test_checkout_creates_confirmed_orders_and_cod_transaction(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], OrderStatus.CONFIRMED)
        self.assertEqual(response.data['payment_method'], 'cash_on_delivery')
        self.assertEqual(response.data['payment_status'], TransactionStatus.PENDING)
        self.assertEqual(response.data['total_amount'], '300.00')
        self.assertEqual(response.data['items_count'], 2)

        order = Order.objects.get(batch_id=response.data['batch_id'])
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.unit_price, Decimal('150.00'))
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertEqual(order.visitor.mobile, '9841234567')

        txn = Transaction.objects.get(order=order)
        self.assertTrue(txn.is_cod)
        self.assertFalse(txn.is_midas_credit)
        self.assertEqual(txn.status, TransactionStatus.PENDING)

    def test_checkout_reuses_existing_visitor_by_mobile(self):
        existing = Visitor.objects.create(name='Sarah Jenkins', mobile='9841234567')
        self.client.post(self.url, self.payload, format='json')
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Order.objects.first().visitor_id, existing.id)

    def test_checkout_rejects_inactive_item(self):
        payload = {**self.payload, 'items': [{'item_id': str(self.inactive_item.id), 'quantity': 1}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_unknown_qr(self):
        payload = {**self.payload, 'qr_id': '00000000-0000-0000-0000-000000000000'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_does_not_partially_create_orders_on_invalid_item(self):
        payload = {
            **self.payload,
            'items': [
                {'item_id': str(self.item.id), 'quantity': 1},
                {'item_id': '00000000-0000-0000-0000-000000000000', 'quantity': 1},
            ],
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)


class OrderBatchTrackingTests(APITestCase):
    def setUp(self):
        self.outlet = Outlet.objects.create(name='Bakery')
        self.item = Item.objects.create(outlet=self.outlet, name='Croissant', price=Decimal('150.00'))
        self.location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.qr = QRCode.objects.create(location=self.location)
        self.visitor = Visitor.objects.create(name='Sarah Jenkins', mobile='9841234567')
        self.admin = User.objects.create_superuser(
            username='admin', password='AdminPass123!', name='Admin', role=UserRole.ADMINISTRATOR,
        )

        checkout_response = self.client.post(
            reverse('orders:visitor-checkout'),
            {
                'visitor': {'name': 'Sarah Jenkins', 'mobile': '9841234567'},
                'qr_id': str(self.qr.id),
                'items': [{'item_id': str(self.item.id), 'quantity': 1}],
            },
            format='json',
        )
        self.batch_id = checkout_response.data['batch_id']
        self.order = Order.objects.get(batch_id=self.batch_id)

    def _advance(self, order, status_value):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse('orders:order-detail', kwargs={'pk': order.id}), {'status': status_value}, format='json',
        )
        self.client.force_authenticate(None)
        return response

    def test_tracking_shows_confirmed_immediately_after_checkout(self):
        response = self.client.get(reverse('orders:batch-tracking', kwargs={'batch_id': self.batch_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_status'], OrderStatus.CONFIRMED)
        self.assertFalse(response.data['is_delivered'])
        confirmed_stage = response.data['status_progression'][0]
        self.assertEqual(confirmed_stage['status'], OrderStatus.CONFIRMED)
        self.assertTrue(confirmed_stage['completed'])
        self.assertIsNotNone(confirmed_stage['timestamp'])

    def test_tracking_progresses_through_stages_to_delivered(self):
        for stage in [OrderStatus.ROUTED, OrderStatus.PREPARING, OrderStatus.READY,
                      OrderStatus.ASSIGNED, OrderStatus.PICKED_UP, OrderStatus.DELIVERED]:
            self.assertEqual(self._advance(self.order, stage).status_code, status.HTTP_200_OK)

        response = self.client.get(reverse('orders:batch-tracking', kwargs={'batch_id': self.batch_id}))
        self.assertEqual(response.data['overall_status'], OrderStatus.DELIVERED)
        self.assertTrue(response.data['is_delivered'])
        for stage in response.data['status_progression']:
            self.assertTrue(stage['completed'])
            self.assertIsNotNone(stage['timestamp'])

    def test_tracking_rejects_illegal_transition(self):
        response = self._advance(self.order, OrderStatus.READY)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tracking_404_for_unknown_batch(self):
        response = self.client.get(
            reverse('orders:batch-tracking', kwargs={'batch_id': '00000000-0000-0000-0000-000000000000'})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VisitorOrderHistoryTests(APITestCase):
    def setUp(self):
        self.outlet = Outlet.objects.create(name='Bakery')
        self.item = Item.objects.create(outlet=self.outlet, name='Croissant', price=Decimal('150.00'))
        self.location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.qr = QRCode.objects.create(location=self.location)

    def test_history_requires_mobile(self):
        response = self.client.get(reverse('orders:visitor-history'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_lists_batches_for_mobile(self):
        self.client.post(
            reverse('orders:visitor-checkout'),
            {
                'visitor': {'name': 'Sarah Jenkins', 'mobile': '9841234567'},
                'qr_id': str(self.qr.id),
                'items': [{'item_id': str(self.item.id), 'quantity': 3}],
            },
            format='json',
        )
        response = self.client.get(reverse('orders:visitor-history'), {'mobile': '9841234567'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['items_count'], 3)
        self.assertEqual(response.data[0]['total_amount'], '450.00')

    def test_history_empty_for_unknown_mobile(self):
        response = self.client.get(reverse('orders:visitor-history'), {'mobile': '0000000000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])


class PatientCheckoutTests(APITestCase):
    def setUp(self):
        self.url = reverse('orders:patient-checkout')
        self.outlet = Outlet.objects.create(name='Bakery')
        self.item = Item.objects.create(outlet=self.outlet, name='Croissant', price=Decimal('150.00'))
        self.inactive_item = Item.objects.create(
            outlet=self.outlet, name='Stale Bun', price=Decimal('10.00'), is_active=False,
        )
        self.icu_location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.icu_qr = QRCode.objects.create(location=self.icu_location)
        self.patient = Patient.objects.create(
            midas_id='HAMS-101', name='Ram Bahadur Shrestha', location=self.icu_location,
        )
        self.payload = {
            'midas_id': 'HAMS-101',
            'qr_id': str(self.icu_qr.id),
            'items': [{'item_id': str(self.item.id), 'quantity': 2}],
            'special_instructions': 'Low sodium preparation',
        }

    def test_checkout_charges_midas_and_confirms_order(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], OrderStatus.CONFIRMED)
        self.assertEqual(response.data['payment_method'], 'midas_hospital_credit')
        self.assertEqual(response.data['payment_status'], TransactionStatus.SUCCESS)
        self.assertEqual(response.data['total_charged'], '300.00')
        self.assertTrue(response.data['midas_charge_reference'].startswith('MIDAS-CHG-'))
        self.assertEqual(response.data['patient_name'], 'Ram Bahadur Shrestha')
        self.assertEqual(response.data['delivery_location'], 'ICU Ward 3 - Bed 12')

        order = Order.objects.get(batch_id=response.data['batch_id'])
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertEqual(order.patient_id, self.patient.id)

        txn = Transaction.objects.get(order=order)
        self.assertTrue(txn.is_midas_credit)
        self.assertFalse(txn.is_cod)
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)
        self.assertEqual(txn.amount, Decimal('300.00'))
        self.assertEqual(txn.external_reference, response.data['midas_charge_reference'])

    def test_checkout_rejects_unverified_patient(self):
        self.patient.delete()
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_insufficient_credit_and_creates_no_orders(self):
        general_ward = Location.objects.create(ward_name='General Ward 1', bed_number='Bed 05')
        Patient.objects.create(midas_id='HAMS-102', name='Sita Devi Thapa', location=general_ward)
        qr = QRCode.objects.create(location=general_ward)
        payload = {**self.payload, 'midas_id': 'HAMS-102', 'qr_id': str(qr.id)}

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_checkout_rejects_inactive_item_without_charging(self):
        payload = {**self.payload, 'items': [{'item_id': str(self.inactive_item.id), 'quantity': 1}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)


class PatientActiveOrdersTests(APITestCase):
    def setUp(self):
        self.outlet = Outlet.objects.create(name='Bakery')
        self.item = Item.objects.create(outlet=self.outlet, name='Croissant', price=Decimal('150.00'))
        self.location = Location.objects.create(ward_name='ICU Ward 3', bed_number='Bed 12')
        self.qr = QRCode.objects.create(location=self.location)
        self.patient = Patient.objects.create(
            midas_id='HAMS-101', name='Ram Bahadur Shrestha', location=self.location,
        )

    def test_requires_midas_id(self):
        response = self.client.get(reverse('orders:patient-active'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lists_active_batch_after_checkout(self):
        self.client.post(
            reverse('orders:patient-checkout'),
            {
                'midas_id': 'HAMS-101',
                'qr_id': str(self.qr.id),
                'items': [{'item_id': str(self.item.id), 'quantity': 1}],
            },
            format='json',
        )
        response = self.client.get(reverse('orders:patient-active'), {'midas_id': 'HAMS-101'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], OrderStatus.CONFIRMED)
        self.assertEqual(response.data[0]['delivery_location'], 'ICU Ward 3 - Bed 12')

    def test_delivered_batch_is_excluded(self):
        Order.objects.create(
            qr=self.qr, batch_id=uuid.uuid4(), item=self.item, quantity=1, unit_price=self.item.price,
            status=OrderStatus.DELIVERED, patient=self.patient,
        )
        response = self.client.get(reverse('orders:patient-active'), {'midas_id': 'HAMS-101'})
        self.assertEqual(response.data, [])
