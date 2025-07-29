from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView


class ComplianceView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_compliance"

    def get(self, request, *args, **kwargs):
        return Response({"success": True})
