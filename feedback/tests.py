from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from customers.models import Visitor
from menu.models import Item
from orders.models import Order, OrderStatus
from outlets.models import Outlet

from .models import Feedback


class FeedbackSubmitTests(APITestCase):
    def setUp(self):
        self.url = reverse('feedback:feedback-submit')
        outlet = Outlet.objects.create(name='Bakery')
        item = Item.objects.create(outlet=outlet, name='Croissant', price=Decimal('150.00'))
        visitor = Visitor.objects.create(name='Sarah Jenkins', mobile='9841234567')
        self.confirmed_order = Order.objects.create(
            batch_id='11111111-1111-1111-1111-111111111111',
            item=item, quantity=1, unit_price=item.price, status=OrderStatus.CONFIRMED, visitor=visitor,
        )
        self.delivered_order = Order.objects.create(
            batch_id='22222222-2222-2222-2222-222222222222',
            item=item, quantity=1, unit_price=item.price, status=OrderStatus.DELIVERED, visitor=visitor,
        )

    def test_rejects_feedback_for_undelivered_order(self):
        response = self.client.post(self.url, {
            'order_id': str(self.confirmed_order.id), 'feedback_type': 'food_feedback',
            'rating': 5, 'feedback_and_others': 'too early',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accepts_feedback_for_delivered_order(self):
        response = self.client.post(self.url, {
            'order_id': str(self.delivered_order.id), 'feedback_type': 'food_feedback',
            'rating': 5, 'feedback_and_others': 'Food was warm, fresh, and delivered promptly.',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(Feedback.objects.get(order=self.delivered_order).rating, 5)

    def test_rejects_duplicate_feedback(self):
        Feedback.objects.create(order=self.delivered_order, rating=5, feedback_and_others='first')
        response = self.client.post(self.url, {
            'order_id': str(self.delivered_order.id), 'feedback_type': 'delivery_feedback',
            'rating': 3, 'feedback_and_others': 'second',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_rating_out_of_range(self):
        response = self.client.post(self.url, {
            'order_id': str(self.delivered_order.id), 'feedback_type': 'food_feedback',
            'rating': 7, 'feedback_and_others': 'invalid rating',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_endpoint_is_public(self):
        response = self.client.post(self.url, {
            'order_id': str(self.delivered_order.id), 'feedback_type': 'food_feedback',
            'rating': 4, 'feedback_and_others': 'no auth needed',
        })
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
