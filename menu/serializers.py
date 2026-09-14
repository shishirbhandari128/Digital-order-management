from rest_framework import serializers

from outlets.models import Outlet
from outlets.serializers import OutletSerializer

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    outlet = serializers.PrimaryKeyRelatedField(queryset=Outlet.objects.all())

    class Meta:
        model = Item
        fields = [
            'id',
            'outlet',
            'name',
            'price',
            'description',
            'image_url',
            'is_kot',
            'is_bot',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['outlet'] = OutletSerializer(instance.outlet).data
        return data
