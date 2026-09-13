import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Transaction as BillingTransaction
from billing.models import TransactionStatus
from customers.models import QRCode, Visitor
from menu.models import Item

from .models import Order, OrderStatus
from .serializers import OrderSerializer, VisitorCheckoutSerializer
from .services import batch_progression, bottleneck_status


class OrderListCreateAPIView(generics.ListCreateAPIView):
    queryset = Order.objects.select_related(
        'qr__location', 'item__outlet', 'assigned_delivery_user', 'patient', 'visitor'
    ).all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrderRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.select_related(
        'qr__location', 'item__outlet', 'assigned_delivery_user', 'patient', 'visitor'
    ).all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]


class VisitorCheckoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VisitorCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr = get_object_or_404(QRCode.objects.select_related('location'), pk=data['qr_id'])

        item_ids = [entry['item_id'] for entry in data['items']]
        items_by_id = {item.id: item for item in Item.objects.filter(id__in=item_ids, is_active=True)}
        missing = [str(item_id) for item_id in item_ids if item_id not in items_by_id]
        if missing:
            return Response(
                {'items': f'Invalid or inactive item id(s): {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            visitor, _ = Visitor.objects.get_or_create(
                mobile=data['visitor']['mobile'], defaults={'name': data['visitor']['name']}
            )
            batch_id = uuid.uuid4()
            created_orders = []
            for entry in data['items']:
                item = items_by_id[entry['item_id']]
                order = Order.objects.create(
                    qr=qr,
                    batch_id=batch_id,
                    item=item,
                    quantity=entry['quantity'],
                    unit_price=item.price,
                    status=OrderStatus.CONFIRMED,
                    visitor=visitor,
                )
                BillingTransaction.objects.create(
                    order=order,
                    is_cod=True,
                    is_midas_credit=False,
                    status=TransactionStatus.PENDING,
                )
                created_orders.append(order)

        total_amount = sum(order.unit_price * order.quantity for order in created_orders)
        items_count = sum(order.quantity for order in created_orders)
        location = qr.location
        delivery_location = ' - '.join(part for part in [location.ward_name, location.bed_number] if part)

        return Response(
            {
                'batch_id': str(batch_id),
                'status': OrderStatus.CONFIRMED,
                'payment_method': 'cash_on_delivery',
                'payment_status': TransactionStatus.PENDING,
                'total_amount': str(total_amount),
                'delivery_location': delivery_location,
                'items_count': items_count,
                'created_at': created_orders[0].created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class OrderBatchTrackingAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, batch_id):
        orders = list(
            Order.objects.filter(batch_id=batch_id).select_related('assigned_delivery_user')
        )
        if not orders:
            return Response({'detail': 'Order batch not found.'}, status=status.HTTP_404_NOT_FOUND)

        overall_status, progression = batch_progression(orders)
        delivery_user = next((order.assigned_delivery_user for order in orders if order.assigned_delivery_user), None)

        from feedback.models import Feedback

        feedback_submitted = Feedback.objects.filter(order__in=orders).exists()

        return Response({
            'batch_id': str(batch_id),
            'overall_status': overall_status,
            'status_progression': progression,
            'delivery_person': (
                {'name': delivery_user.name, 'assigned': True}
                if delivery_user
                else {'name': None, 'assigned': False}
            ),
            'is_delivered': overall_status == OrderStatus.DELIVERED,
            'feedback_submitted': feedback_submitted,
        })


class VisitorOrderHistoryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        mobile = request.query_params.get('mobile')
        if not mobile:
            return Response({'detail': 'mobile query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        orders = Order.objects.filter(visitor__mobile=mobile).select_related('item').order_by('created_at')
        batches = {}
        for order in orders:
            batches.setdefault(order.batch_id, []).append(order)

        results = []
        for batch_id, batch_orders in batches.items():
            results.append({
                'batch_id': str(batch_id),
                'status': bottleneck_status([order.status for order in batch_orders]),
                'items_count': sum(order.quantity for order in batch_orders),
                'total_amount': str(sum(order.unit_price * order.quantity for order in batch_orders)),
                'created_at': min(order.created_at for order in batch_orders),
            })

        results.sort(key=lambda entry: entry['created_at'], reverse=True)
        return Response(results)
