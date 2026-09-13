import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DefaultUserManager
from django.db import models


class UserRole(models.TextChoices):
    OUTLET_MANAGER = 'outlet_manager', 'Outlet Manager'
    KITCHEN_STAFF = 'kitchen_staff', 'Kitchen Staff'
    DELIVERY_STAFF = 'delivery_staff', 'Delivery Staff'
    ADMINISTRATOR = 'administrator', 'Administrator'

class CustomUserManager(DefaultUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Enforce administrative privileges
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # Automatically assign your custom role
        extra_fields.setdefault('role', UserRole.ADMINISTRATOR)

        return super().create_superuser(username, email, password, **extra_fields)
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    role = models.CharField(
        max_length=32, 
        choices=UserRole.choices, 
        default=UserRole.OUTLET_MANAGER,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    def __str__(self) -> str:
        return self.name or self.username
