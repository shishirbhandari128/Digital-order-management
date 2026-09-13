import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    OUTLET_MANAGER = 'outlet_manager', 'Outlet Manager'
    KITCHEN_STAFF = 'kitchen_staff', 'Kitchen Staff'
    DELIVERY_STAFF = 'delivery_staff', 'Delivery Staff'
    ADMINISTRATOR = 'administrator', 'Administrator'


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=UserRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name or self.username
