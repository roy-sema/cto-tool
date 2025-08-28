import logging

import posthog
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import reverse
from django.template.loader import render_to_string
from django.views import View

from mvp.mixins import DecodePublicIdMixin
from mvp.models import Organization
from mvp.services import EmailService
from mvp.tasks import ExportGBOMTask
from mvp.utils import start_new_thread

logger = logging.getLogger(__name__)


class ExportGBOMView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request):
        organization = self.get_organization(request)

        download = request.GET.get("download")

        gbom = ExportGBOMTask()
        content = gbom.read_precomputed_gbom(organization)
        if not content:
            if not gbom.is_generating(organization):
                self.generate_gbom_background(organization, request.user)
            return JsonResponse({"status": "processing"})

        if download:
            posthog.capture(request.user.email, event="download_gbom")
            filename = gbom.get_gbom_filename(organization)
            return self.download_gbom(filename, content)

        return JsonResponse({"status": "ready"})

    def download_gbom(self, filename, content):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write(content)

        return response

    def get_organization(self, request):
        organization_id = request.GET.get("org")
        if organization_id:
            try:
                pk = self.decode_id(organization_id)
                organization = Organization.objects.get(pk=pk)
                if organization in request.user_organizations:
                    return organization
            except Organization.DoesNotExist:
                pass

        return request.current_organization

    @start_new_thread
    def generate_gbom_background(self, organization, user):
        gbom = ExportGBOMTask().generate_precomputed_gbom(organization)
        if gbom:
            self.send_gbom_ready_email(user, organization)

    def send_gbom_ready_email(self, user, organization):
        if not settings.SEND_GBOM_READY_EMAIL_ACTIVE:
            logger.info("Skipping sending GBOM ready email")
            return

        email_address = user.email

        url = settings.SITE_DOMAIN + reverse("export_gbom") + "?download=true&org=" + organization.public_id()

        message = render_to_string(
            "mvp/ai_code_monitor/gbom_ready_email.html",
            {
                "organization": organization,
                "url": url,
                "APP_NAME": settings.APP_NAME,
            },
        )

        EmailService().send_email(
            f"{settings.APP_NAME} GBOM ready",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email_address],
        )
