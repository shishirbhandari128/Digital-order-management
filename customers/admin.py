from django.contrib import admin

from .models import Location, Patient, QRCode, Visitor

admin.site.register(Location)
admin.site.register(QRCode)
admin.site.register(Patient)
admin.site.register(Visitor)
