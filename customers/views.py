from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from midas.client import CreditFrozenError, PatientNotFoundError
from midas.services import get_midas_client

from .models import Location, Patient, QRCode, Visitor
from .serializers import (
    LocationSerializer,
    PatientSerializer,
    PatientVerifyResponseSerializer,
    PatientVerifySerializer,
    QRCodeSerializer,
    QRLocationSerializer,
    VisitorRegistrationSerializer,
    VisitorSerializer,
)
from .services import generate_patient_session_token, location_matches_admission


class LocationListCreateAPIView(generics.ListCreateAPIView):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated]


class LocationRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated]


class QRCodeListCreateAPIView(generics.ListCreateAPIView):
    queryset = QRCode.objects.select_related('location').all()
    serializer_class = QRCodeSerializer
    permission_classes = [permissions.IsAuthenticated]


class QRCodeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = QRCode.objects.select_related('location').all()
    serializer_class = QRCodeSerializer
    permission_classes = [permissions.IsAuthenticated]


class PatientListCreateAPIView(generics.ListCreateAPIView):
    queryset = Patient.objects.select_related('location').all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]


class PatientRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Patient.objects.select_related('location').all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]


class VisitorListCreateAPIView(generics.ListCreateAPIView):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = VisitorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visitor, created = Visitor.objects.get_or_create(
            mobile=serializer.validated_data['mobile'],
            defaults={'name': serializer.validated_data['name']},
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(VisitorSerializer(visitor).data, status=response_status)


class VisitorRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer
    permission_classes = [permissions.IsAuthenticated]


class QRLocationLookupAPIView(generics.RetrieveAPIView):
    queryset = QRCode.objects.select_related('location').all()
    serializer_class = QRLocationSerializer
    permission_classes = [permissions.AllowAny]
    lookup_url_kwarg = 'qr_id'


class PatientVerifyAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PatientVerifySerializer,
        responses={
            200: PatientVerifyResponseSerializer,
            400: OpenApiResponse(description='Scanned location does not match the patient\'s MIDAS admission.'),
            402: OpenApiResponse(description='Patient has an active credit freeze in MIDAS.'),
            404: OpenApiResponse(description='MIDAS id not found, or the QR code is unknown.'),
        },
        summary='Verify a patient via MIDAS and sync the local Patient record',
    )
    def post(self, request):
        serializer = PatientVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        midas_id = serializer.validated_data['midas_id']
        qr = get_object_or_404(QRCode.objects.select_related('location'), pk=serializer.validated_data['qr_id'])

        midas_client = get_midas_client()
        try:
            admission = midas_client.verify_patient(midas_id)
        except PatientNotFoundError:
            return Response(
                {'detail': 'MIDAS id not found or patient is no longer admitted.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CreditFrozenError:
            return Response(
                {'detail': 'Patient has an active credit freeze in MIDAS.'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        location = qr.location
        if not location_matches_admission(location, admission):
            return Response(
                {
                    'detail': (
                        f'Patient is admitted to {admission.ward_name} / {admission.bed_number}, '
                        'which does not match the scanned location.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        patient, _ = Patient.objects.update_or_create(
            midas_id=midas_id,
            defaults={'name': admission.name, 'location': location},
        )

        billing_eligible = admission.credit_balance > 0 and not admission.credit_frozen
        session_token = generate_patient_session_token(patient, qr)

        return Response(
            {
                'patient': {
                    'id': str(patient.id),
                    'midas_id': patient.midas_id,
                    'name': patient.name,
                    'admission_status': admission.admission_status,
                    'ward': admission.ward_name,
                    'bed': admission.bed_number,
                },
                'billing_eligible': billing_eligible,
                'credit_limit': str(admission.credit_balance),
                'session_token': session_token,
            },
            status=status.HTTP_200_OK,
        )
