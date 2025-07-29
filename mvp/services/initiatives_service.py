from typing import TYPE_CHECKING

from django.db.models import Prefetch, QuerySet

from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.pin_initiatives_prompt import (
    pin_initiatives_template,
)
from mvp.models import Organization

if TYPE_CHECKING:
    from compass.contextualization.models import Initiative


def add_pinned_initiatives_input_prompt(organization: Organization) -> str:
    pinned_initiatives = get_pinned_initiatives(organization)

    pinned_initiatives_data = []
    for initiative in pinned_initiatives:
        initiative_data = {
            "name": initiative.custom_name or initiative.name,
            "description": initiative.justification,
            "epics": [],
        }

        # Add pinned epics
        pinned_epics = initiative.epics.filter(pinned=True)
        for epic in pinned_epics:
            initiative_data["epics"].append({"name": epic.custom_name or epic.name, "description": epic.description})

        pinned_initiatives_data.append(initiative_data)

    if pinned_initiatives_data:
        return pin_initiatives_template.format(initiatives={"initiatives": pinned_initiatives_data})

    return ""


def get_pinned_initiatives(organization: Organization) -> QuerySet["Initiative"]:
    # Import models inside the function to avoid circular import
    from compass.contextualization.models import Initiative, InitiativeEpic, Roadmap

    latest_roadmap = Roadmap.latest_by_org(organization)
    if not latest_roadmap:
        return Initiative.objects.none()

    pinned_epics = Prefetch("epics", queryset=InitiativeEpic.objects.filter(pinned=True, disabled=False))

    return Initiative.objects.filter(roadmap=latest_roadmap, pinned=True, disabled=False).prefetch_related(pinned_epics)
