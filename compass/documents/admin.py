from django.contrib import admin
from django.utils.html import format_html

from compass.documents.models import Document
from mvp.utils import get_file_url


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "file_name",
        "uploaded_by",
    )
    list_filter = ("organization__name",)
    search_fields = ("file", "uploaded_by__email")
    fields = ("name", "organization", "uploaded_by", "download_file")
    readonly_fields = fields

    def has_add_permission(self, request):
        # Hide the Add documents button
        return False

    def file_name(self, obj):
        return obj.file.name.split("/")[-1]

    def download_file(self, obj):
        url = get_file_url(obj.file)
        return format_html('<a href="{}" target="_blank">{}</a>', url, self.file_name(obj))

    download_file.short_description = "Download File"

    def get_queryset(self, request):
        # Use select_related to avoid N+1 queries
        queryset = super().get_queryset(request)
        return queryset.select_related("organization", "uploaded_by")
