from rest_framework import serializers

from .models import Location, Patient, QRCode, Visitor


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            'id',
            'ward_name',
            'bed_number',
            'is_public_space',
            'is_patient_space_only',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QRCodeSerializer(serializers.ModelSerializer):
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())

    class Meta:
        model = QRCode
        fields = ['id', 'location', 'image_url', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PatientSerializer(serializers.ModelSerializer):
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())

    class Meta:
        model = Patient
        fields = ['id', 'midas_id', 'location', 'name']
        read_only_fields = ['id']


class VisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = ['id', 'name', 'mobile']
        read_only_fields = ['id']


class VisitorRegistrationSerializer(serializers.Serializer):
    """Validates visitor self-identification input without the model's unique-mobile
    validator, since an existing mobile number is resolved via get_or_create, not rejected."""
    name = serializers.CharField(max_length=255)
    mobile = serializers.CharField(max_length=20)


class QRLocationSerializer(serializers.Serializer):
    qr_id = serializers.UUIDField(source='id')
    location = LocationSerializer()
    allowed_order_types = serializers.SerializerMethodField()

    def get_allowed_order_types(self, obj):
        return ['patient'] if obj.location.is_patient_space_only else ['visitor', 'patient']
