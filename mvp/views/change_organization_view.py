from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.views import View

from mvp.middlewares import CurrentOrganizationMiddleware
from mvp.mixins import DecodePublicIdMixin


class ChangeOrganizationView(DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_organization"
    redirect_paths = ["/pulls/", "/repositories/"]

    def get(self, request):
        organization_id = self.decode_id(request.GET.get("organization_id"))

        organization = request.user_organizations.get(id=organization_id)
        CurrentOrganizationMiddleware.set_current_organization(request, organization)

        next_page = request.GET.get("next")
        # PR will not exist in a different organization

        if any(keyword in next_page for keyword in self.redirect_paths):
            return redirect("/")

        return redirect(next_page or "/")
