import json

import yaml
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.views import View

from mvp.services import ContextualizationDayInterval
from mvp.services.raw_contextualization_service import RawContextualizationService


class RawContextualization(LoginRequiredMixin, View):
    def get(self, request):
        day_interval_parameter = request.GET.get("day-interval", 1)
        try:
            day_interval = ContextualizationDayInterval(int(day_interval_parameter))
        except ValueError:
            return JsonResponse({"error": "day-interval should be an integer: 1, 7, 14."}, status=400)

        data = RawContextualizationService.get_for_day_interval(
            request.current_organization,
            day_interval,
        )

        if request.GET.get("as-json"):
            pretty_json = json.dumps(data, indent=2)
            return HttpResponse(pretty_json, content_type="application/json")

        pretty_yaml = yaml.dump(data, sort_keys=False, default_flow_style=False)
        return HttpResponse(pretty_yaml, content_type="text/yaml")
