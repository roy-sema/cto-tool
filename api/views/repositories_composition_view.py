from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from mvp.mixins import DecodePublicIdMixin
from mvp.serializers import ai_composition_serializer, charts_serializer
from mvp.services import AICompositionService


class RepositoriesCompositionView(DecodePublicIdMixin, PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request, *args, **kwargs):
        current_org = request.current_organization

        # TODO: add default values to since and until
        since = parse_date_param(request, "since")
        until = parse_date_param(request, "until")

        service = AICompositionService(current_org)
        cumulative_charts, daily_charts = service.get_charts(since=since, until=until, daily_charts=True)
        ai_composition = service.get_composition(cumulative_charts)

        return Response(
            {
                "ai_composition": ai_composition_serializer(ai_composition),
                "cumulative_charts": charts_serializer(cumulative_charts),
                "daily_charts": charts_serializer(daily_charts),
            }
        )
