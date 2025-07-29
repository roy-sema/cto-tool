from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from mvp.middlewares import CurrentOrganizationMiddleware
from mvp.mixins import DecodePublicIdMixin
from mvp.models import RepositoryCommitStatusChoices, RepositoryPullRequest
from mvp.serializers import RepositoryPullRequestSerializer, ai_composition_serializer
from mvp.services import PullRequestService


class PullRequestScanView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, View):
    permission_required = "mvp.can_view_pull_request_scans"

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return super().handle_no_permission()

        organizations = self.get_pull_request_organizations(
            self.kwargs.get("external_id"), self.kwargs.get("pr_number")
        )

        url = reverse("request_access")
        if organizations:
            ids_list = ",".join([o.public_id() for o in organizations])
            url += f"?o={ids_list}"

        return HttpResponseRedirect(url)

    def get(self, request, external_id, pr_number):
        current_org = self.request.current_organization

        pull_request = self.get_pull_request(request, external_id, pr_number)
        if pull_request and pull_request.repository.organization != current_org:
            pull_request_org = pull_request.repository.organization
            CurrentOrganizationMiddleware.set_current_organization(request, pull_request_org)
            current_org = pull_request_org

        if not pull_request:
            raise Http404("Pull request not found")

        service = PullRequestService()

        if settings.DEBUG and request.GET.get("md"):
            # NOTE: use "View Source" on browser to see markdown with line breaks
            return render(
                request,
                "markdown/status-check.md",
                service.get_markdown_render_data(pull_request),
            )

        data = service.get_render_data(pull_request, include_not_evaluated=True)
        data["pull_request"] = RepositoryPullRequestSerializer(data["pull_request"]).data

        data["ai_composition"] = ai_composition_serializer(data["ai_composition"])
        data["analysis_failed"] = pull_request.head_commit_status() == RepositoryCommitStatusChoices.FAILURE
        data["BASE_URL"] = settings.SITE_DOMAIN

        return render(
            request,
            "mvp/ai_code_monitor/pull-request-scan-page.html",
            data,
        )

    def get_pull_request(self, request, external_id, pr_number):
        try:
            return RepositoryPullRequest.objects.prefetch_related("repository").get(
                repository__external_id=external_id,
                repository__organization=request.current_organization,
                pr_number=pr_number,
            )
        except RepositoryPullRequest.DoesNotExist:
            # don't use request.user_organizations because
            # that would grant superusers access to all PRs from all organizations
            user_organizations = request.user.organizations.all()
            if len(user_organizations) <= 1:
                return None

            prs = RepositoryPullRequest.objects.prefetch_related("repository").filter(
                repository__external_id=external_id,
                repository__organization__in=user_organizations,
                pr_number=pr_number,
            )
            return prs.first() or None

    def get_pull_request_organizations(self, external_id, pr_number):
        pull_requests = RepositoryPullRequest.objects.prefetch_related("repository", "repository__organization").filter(
            repository__external_id=external_id,
            pr_number=pr_number,
        )

        organizations = set()
        for pull_request in pull_requests:
            organizations.add(pull_request.repository.organization)

        return list(organizations)
