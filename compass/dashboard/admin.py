from django.contrib import admin

from .models import GitDiffContext, GitDiffRepositoryGroupInsight


@admin.register(GitDiffContext)
class GitDiffContextAdmin(admin.ModelAdmin):
    list_display = (
        "repository",
        "organization",
        "time",
        "sha",
        "file_path",
        "git_diff_hash",
        "category",
        "summary",
    )
    readonly_fields = ["repository", "organization", "time"]
    list_filter = ["repository__organization", "repository"]
    search_fields = ["repository__name", "file_path", "sha"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("repository")

    def organization(self, obj):
        return obj.repository.organization if obj.repository else None


@admin.register(GitDiffRepositoryGroupInsight)
class GitDiffRepositoryGroupInsightAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "repository_group",
        "start_date",
        "end_date",
        "category",
        "percentage",
    )
    readonly_fields = ["organization", "repository_group"]
    list_filter = ["organization", "repository_group"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("organization", "repository_group")
