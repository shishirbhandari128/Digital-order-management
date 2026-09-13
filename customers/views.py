from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Location, Patient, QRCode, Visitor
from .serializers import (
    LocationSerializer,
    PatientSerializer,
    QRCodeSerializer,
    QRLocationSerializer,
    VisitorRegistrationSerializer,
    VisitorSerializer,
)


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
