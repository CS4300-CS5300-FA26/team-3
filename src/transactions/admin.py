from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "kind", "category", "amount", "is_fixed", "owner")
    list_filter = ("kind", "category", "is_fixed")
    search_fields = ("description",)
