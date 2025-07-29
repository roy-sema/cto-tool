from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View

from mvp.mixins import DecodePublicIdMixin
from mvp.models import Repository
from mvp.services import PullRequestService


class RepositoryDetailView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_pull_request_scans"

    def get(self, request, pk_encoded):
        if not pk_encoded:
            return self.redirect_to_view()

        return self.render_page(request, pk_encoded)

    def render_page(self, request, pk_encoded):
        pk = self.decode_id(pk_encoded)
        current_org = request.current_organization
        repo = get_object_or_404(Repository, pk=pk, organization=current_org)
        commit_sha = repo.last_commit_sha
        return render(
            request,
            "mvp/ai_code_monitor/repository-detail.html",
            {
                "repository_full_name": repo.full_name(),
                "repository_pk_encoded": pk_encoded,
                "commit_sha": commit_sha,
                "code_generation_labels": PullRequestService().get_code_generation_labels(),
            },
        )

    def redirect_to_view(self):
        path_name = "home"
        return redirect(reverse_lazy(path_name))
