from django.conf import settings
from django.shortcuts import render
from django.views import generic

from mvp.forms import RequestAccessForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Organization
from mvp.services import EmailService


class RequestAccessView(DecodePublicIdMixin, generic.CreateView):
    form_class = RequestAccessForm
    template_name = "account/request_access.html"

    def get(self, request):
        form = RequestAccessForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = self.form_class(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            organizations = self.get_organizations(request.GET.get("o"))
            self.send_request_access_email(email, organizations)
            return render(request, self.template_name, {"sent": True})

        return render(request, self.template_name, {"form": form})

    def get_organizations(self, pk_list):
        if not pk_list:
            return None

        try:
            pks_encoded = pk_list.split(",")
            ids = [self.decode_id(pk_encoded) for pk_encoded in pks_encoded]
            return Organization.objects.filter(pk__in=ids)
        except Organization.DoesNotExist:
            return None

    def send_request_access_email(self, email, organizations=None):
        message = f"New account request from user '{email}'"
        if organizations:
            name_list = ", ".join([o.name for o in organizations])
            org_plural = "organizations" if len(organizations) > 1 else "organization"
            message += f" for {org_plural} '{name_list}'"

        EmailService().send_email(
            f"{settings.APP_NAME} new account request",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.SUPPORT_EMAIL],
        )
