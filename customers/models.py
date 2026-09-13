import uuid

from django.db import models


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ward_name = models.CharField(max_length=255)
    bed_number = models.CharField(max_length=32, blank=True)
    is_public_space = models.BooleanField(default=False)
    is_patient_space_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.ward_name} {self.bed_number}'.strip()


class QRCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='qr_codes')
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.id)


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    midas_id = models.CharField(max_length=64, unique=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='patients')
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class Visitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=20, unique=True)

    def __str__(self) -> str:
        return f'{self.name} ({self.mobile})'
