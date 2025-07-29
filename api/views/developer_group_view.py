from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from mvp.mixins import DecodePublicIdMixin
from mvp.models import AuthorGroup, AuthorStat
from mvp.serializers import AggregatedAuthorStatSerializer, AuthorGroupSerializer
from mvp.services import ConnectedIntegrationsService, GroupsAICodeService


class DeveloperGroupView(DecodePublicIdMixin, PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_ai_code_monitor"
    serializer_class = AuthorGroupSerializer

    def get_queryset(self):
        return (
            AuthorGroup.objects.filter(organization=self.request.current_organization)
            .prefetch_related("rules", "organization__rule_set")
            .order_by("name")
        )

    def get(self, request):
        groups = self.get_queryset()
        organization = request.current_organization

        start_date = parse_date_param(request, "since") or None
        end_date = parse_date_param(request, "until") or None
        for group in groups:
            group.stats = AuthorStat.get_aggregated_group_stats(group.id, start_date=start_date, end_date=end_date)
        groups_serialized = self.serializer_class(groups, many=True).data
        ungrouped = GroupsAICodeService(organization).get_ungrouped_group()
        ungrouped["stats"] = AggregatedAuthorStatSerializer(ungrouped["stats"]).data
        groups_serialized.append(ungrouped)

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(
            organization=organization,
            integration_map_keys=ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS,
        )

        return Response({"groups": groups_serialized, "integrations": integrations})
