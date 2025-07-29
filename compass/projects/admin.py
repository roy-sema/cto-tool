from django.contrib import admin

from compass.projects.models import ChatHistory


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "prompt",
        "organization",
        "created_by",
        "status",
        "is_rollback",
        "is_reset",
        "is_active",
    )
    list_filter = ("organization",)
    readonly_fields = ["created_by", "organization", "rollback_chat", "created_at", "updated_at"]

    def get_queryset(self, request):
        # Use select_related to avoid N+1 queries
        return super().get_queryset(request).select_related("organization", "created_by")
