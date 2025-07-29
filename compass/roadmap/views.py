from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from compass.contextualization.models import Roadmap
from compass.contextualization.serializers import RoadmapSerializer
from mvp.models import Organization, RepositoryGroup
from mvp.serializers import RepositoryGroupSimpleSerializer
from mvp.services import ConnectedIntegrationsService


class RoadmapView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_roadmap"
    serializer_class = RoadmapSerializer

    INTEGRATION_MAP_KEYS = [
        *ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS,
        ConnectedIntegrationsService.JIRA,
    ]

    def get(self, request, *args, **kwargs):
        organization: Organization = request.current_organization

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(
            organization=organization,
            integration_map_keys=self.INTEGRATION_MAP_KEYS,
        )

        repository_group_public_id = request.GET.get("product")
        latest_roadmap = Roadmap.latest_by_org(
            organization,
            repository_group_public_id=repository_group_public_id,
        )
        if not latest_roadmap:
            return Response({"roadmap_ready": False, "integrations": integrations})

        roadmap_data = self.serializer_class(latest_roadmap)
        context = {
            "integrations": integrations,
            **roadmap_data.data,
        }
        return Response(context)


class RoadmapFiltersView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_roadmap"

    def get(self, request, *args, **kwargs):
        organization: Organization = request.current_organization

        repository_groups = RepositoryGroup.objects.filter(organization=organization)
        repository_groups_serialized = RepositoryGroupSimpleSerializer(repository_groups, many=True).data

        return Response(
            {
                "repository_groups": repository_groups_serialized,
            }
        )
