from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.tasks import ProcessPullRequestTask
from mvp.mixins import DecodePublicIdMixin
from mvp.models import RepositoryPullRequest
from mvp.tasks import ForceAiEngineRerunTask
from mvp.utils import start_new_thread


class PullRequestReRunAnalysisView(DecodePublicIdMixin, PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_pull_request_scans"

    def get(self, request, *args, **kwargs):
        pk_encoded = kwargs.get("pk_encoded")
        pr_number = kwargs.get("pr_number")
        repo_pk = self.decode_id(pk_encoded)
        organization = request.current_organization

        pull_request = get_object_or_404(
            RepositoryPullRequest,
            repository_id=repo_pk,
            pr_number=pr_number,
            repository__organization=organization,
        )

        (
            data,
            integration,
        ) = ForceAiEngineRerunTask().prepare_pull_request_for_re_analysis(
            pull_request,
        )
        if data and integration:
            self.process_pull_request(data, integration)
            return Response({"operation": "started"})
        else:
            return Response({"operation": "aborted"})

    @start_new_thread
    def process_pull_request(self, data, integration):
        ProcessPullRequestTask().run(data, integration)
