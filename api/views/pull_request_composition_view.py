from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from mvp.mixins import DecodePublicIdMixin
from mvp.models import RepositoryPullRequest
from mvp.serializers import ai_composition_serializer
from mvp.services import PullRequestService


class PullRequestCompositionView(DecodePublicIdMixin, PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_pull_request_scans"

    def get(self, request, *args, **kwargs):
        pk_encoded = kwargs.get("pk_encoded")
        pr_number = kwargs.get("pr_number")

        repo_pk = self.decode_id(pk_encoded)

        current_org = request.current_organization

        pr = get_object_or_404(
            RepositoryPullRequest,
            repository_id=repo_pk,
            pr_number=pr_number,
            repository__organization=current_org,
        )

        # TODO: optimize, overkill to get all data
        data = PullRequestService().get_render_data(pr)

        return Response(
            {
                "ai_composition": ai_composition_serializer(data["ai_composition"]),
                "needs_composition_recalculation": pr.needs_composition_recalculation,
            }
        )
