from django.contrib import admin

from .models import MidasAuditLog


@admin.register(MidasAuditLog)
class MidasAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'midas_id', 'outcome', 'latency_ms', 'created_at')
    list_filter = ('action', 'outcome')
    search_fields = ('midas_id', 'correlation_id', 'external_reference', 'idempotency_key')
    readonly_fields = [field.name for field in MidasAuditLog._meta.fields]
