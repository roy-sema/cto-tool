from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from pydantic import BaseModel, Field

from compass.contextualization.models import Initiative, InitiativeEpic, Roadmap
from mvp.mixins import DecodePublicIdMixin


class EpicUpdateSchema(BaseModel):
    id: int
    pinned: bool = Field(default=False)
    disabled: bool = Field(default=False)
    custom_name: str = Field(default="")


class InitiativeUpdateSchema(BaseModel):
    id: int
    pinned: bool = Field(default=False)
    disabled: bool = Field(default=False)
    custom_name: str = Field(default="")
    epics: list[EpicUpdateSchema] = Field(default_factory=list)


class InitiativesPayloadSchema(BaseModel):
    initiatives: list[InitiativeUpdateSchema] = Field(default_factory=list)


class InitiativesView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.render_page(request)

    def post(self, request: HttpRequest) -> HttpResponse:
        organization = request.current_organization
        payload = request.POST.get("payload")

        try:
            data = InitiativesPayloadSchema.model_validate_json(payload)
        except Exception as e:
            messages.error(request, f"Invalid payload: {e}")
            return redirect(reverse_lazy("initiatives"))

        latest_roadmap = Roadmap.latest_by_org(organization)
        if latest_roadmap:
            initiatives_qs = Initiative.objects.filter(roadmap=latest_roadmap)
            epics_qs = InitiativeEpic.objects.filter(initiative__roadmap=latest_roadmap)
        else:
            initiatives_qs = Initiative.objects.none()
            epics_qs = InitiativeEpic.objects.none()

        initiatives_map = {str(i.id): i for i in initiatives_qs}
        epics_map = {str(e.id): e for e in epics_qs}

        updated_initiatives = []
        updated_epics = []

        for i_data in data.initiatives:
            initiative = initiatives_map.get(str(i_data.id))
            if not initiative:
                continue

            initiative.pinned = i_data.pinned
            initiative.disabled = i_data.disabled
            initiative.custom_name = i_data.custom_name
            updated_initiatives.append(initiative)

            for e_data in i_data.epics:
                epic = epics_map.get(str(e_data.id))
                if not epic:
                    continue

                epic.pinned = e_data.pinned
                epic.disabled = e_data.disabled
                epic.custom_name = e_data.custom_name
                updated_epics.append(epic)

        with transaction.atomic():
            if updated_initiatives:
                Initiative.objects.bulk_update(updated_initiatives, ["pinned", "disabled", "custom_name"])
            if updated_epics:
                InitiativeEpic.objects.bulk_update(updated_epics, ["pinned", "disabled", "custom_name"])

        messages.success(request, "Initiatives and Epics updated!")
        return redirect(reverse_lazy("initiatives"))

    def render_page(self, request: HttpRequest) -> HttpResponse:
        organization = request.current_organization
        latest_roadmap = Roadmap.latest_by_org(organization)
        if latest_roadmap:
            initiatives = (
                Initiative.objects.filter(roadmap=latest_roadmap).prefetch_related("epics").order_by("-pinned", "name")
            )
        else:
            initiatives = Initiative.objects.none()

        return render(
            request,
            "mvp/settings/initiatives.html",
            {"initiatives": initiatives},
        )
