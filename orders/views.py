import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Transaction as BillingTransaction
from billing.models import TransactionStatus
from customers.models import Patient, QRCode, Visitor
from menu.models import Item
from midas.client import MidasClientError, PatientNotFoundError
from midas.services import get_midas_client

from .models import Order, OrderStatus
from .serializers import (
    BatchTrackingResponseSerializer,
    OrderSerializer,
    PatientActiveBatchSummarySerializer,
    PatientCheckoutResponseSerializer,
    PatientCheckoutSerializer,
    VisitorBatchSummarySerializer,
    VisitorCheckoutResponseSerializer,
    VisitorCheckoutSerializer,
)
from .services import ACTIVE_STATUSES, batch_progression, bottleneck_status


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

    @extend_schema(
        request=VisitorCheckoutSerializer,
        responses={
            201: VisitorCheckoutResponseSerializer,
            400: OpenApiResponse(description='Invalid/inactive item id(s), or empty item list.'),
            404: OpenApiResponse(description='Unknown QR code.'),
        },
        summary='Checkout as a visitor (cash on delivery)',
    )
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


class PatientCheckoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PatientCheckoutSerializer,
        responses={
            201: PatientCheckoutResponseSerializer,
            400: OpenApiResponse(description='Invalid/inactive item id(s), or empty item list.'),
            402: OpenApiResponse(description='Insufficient MIDAS credit, or MIDAS declined the charge.'),
            404: OpenApiResponse(description='Unknown QR code, or the patient has not been MIDAS-verified yet.'),
        },
        summary='Checkout as a patient (charge to MIDAS hospital bill)',
    )
    def post(self, request):
        serializer = PatientCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr = get_object_or_404(QRCode.objects.select_related('location'), pk=data['qr_id'])
        patient = Patient.objects.select_related('location').filter(midas_id=data['midas_id']).first()
        if patient is None:
            return Response(
                {'detail': 'Patient must be verified via MIDAS before checkout.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        item_ids = [entry['item_id'] for entry in data['items']]
        items_by_id = {item.id: item for item in Item.objects.filter(id__in=item_ids, is_active=True)}
        missing = [str(item_id) for item_id in item_ids if item_id not in items_by_id]
        if missing:
            return Response(
                {'items': f'Invalid or inactive item id(s): {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_amount = sum(
            items_by_id[entry['item_id']].price * entry['quantity'] for entry in data['items']
        )

        midas_client = get_midas_client()
        try:
            eligible = midas_client.check_credit_eligibility(data['midas_id'], total_amount)
        except PatientNotFoundError:
            return Response({'detail': 'Patient not found in MIDAS.'}, status=status.HTTP_404_NOT_FOUND)

        if not eligible:
            return Response(
                {'detail': 'Insufficient MIDAS credit balance for this order.'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        idempotency_key = uuid.uuid4().hex
        try:
            charge_reference = midas_client.post_charge(data['midas_id'], total_amount, idempotency_key)
        except MidasClientError:
            return Response(
                {'detail': 'MIDAS was unable to post the charge to the hospital bill.'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        batch_id = uuid.uuid4()
        with transaction.atomic():
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
                    patient=patient,
                )
                BillingTransaction.objects.create(
                    order=order,
                    is_cod=False,
                    is_midas_credit=True,
                    status=TransactionStatus.SUCCESS,
                    amount=item.price * entry['quantity'],
                    external_reference=charge_reference,
                )
                created_orders.append(order)

        location = qr.location
        delivery_location = ' - '.join(part for part in [location.ward_name, location.bed_number] if part)

        return Response(
            {
                'batch_id': str(batch_id),
                'status': OrderStatus.CONFIRMED,
                'payment_method': 'midas_hospital_credit',
                'payment_status': TransactionStatus.SUCCESS,
                'midas_charge_reference': charge_reference,
                'total_charged': str(total_amount),
                'patient_name': patient.name,
                'delivery_location': delivery_location,
                'created_at': created_orders[0].created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class OrderBatchTrackingAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            200: BatchTrackingResponseSerializer,
            404: OpenApiResponse(description='Unknown order batch.'),
        },
        summary='Track a checkout batch through its delivery stages',
    )
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

    @extend_schema(
        parameters=[OpenApiParameter('mobile', str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: VisitorBatchSummarySerializer(many=True),
            400: OpenApiResponse(description='Missing mobile query parameter.'),
        },
        summary="List a visitor's past order batches by mobile number",
    )
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


class PatientActiveOrdersAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter('midas_id', str, OpenApiParameter.QUERY, required=True)],
        responses={
            200: PatientActiveBatchSummarySerializer(many=True),
            400: OpenApiResponse(description='Missing midas_id query parameter.'),
        },
        summary="List a patient's in-progress order batches by MIDAS id",
    )
    def get(self, request):
        midas_id = request.query_params.get('midas_id')
        if not midas_id:
            return Response({'detail': 'midas_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        orders = Order.objects.filter(
            patient__midas_id=midas_id, status__in=ACTIVE_STATUSES,
        ).select_related('item', 'qr__location').order_by('created_at')

        batches = {}
        for order in orders:
            batches.setdefault(order.batch_id, []).append(order)

        results = []
        for batch_id, batch_orders in batches.items():
            location = batch_orders[0].qr.location if batch_orders[0].qr else None
            delivery_location = (
                ' - '.join(part for part in [location.ward_name, location.bed_number] if part)
                if location else ''
            )
            results.append({
                'batch_id': str(batch_id),
                'status': bottleneck_status([order.status for order in batch_orders]),
                'items_count': sum(order.quantity for order in batch_orders),
                'total_amount': str(sum(order.unit_price * order.quantity for order in batch_orders)),
                'delivery_location': delivery_location,
                'created_at': min(order.created_at for order in batch_orders),
            })

        results.sort(key=lambda entry: entry['created_at'], reverse=True)
        return Response(results)
