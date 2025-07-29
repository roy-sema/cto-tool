from datetime import datetime, timedelta

from compass.codebasereports.widgets import BaseWidget
from compass.integrations.integrations import GitHubIntegration
from mvp.models import (
    AppComponentChoices,
    AppComponentVersion,
    DataProviderConnection,
    DataProviderProject,
)
from mvp.utils import get_tz_date


class CaveatsWidget(BaseWidget):
    NUM_DAYS = 7

    TEXT_ADDED_CONNECTIONS = "Caveat: {num} more Engineering tools were connected in the last week."
    TEXT_ADDED_REPOSITORIES = "Caveat: {num} more repositories were added in the last week."
    TEXT_SEMA_SCORE = "Sema has updated the analytics calculations in the last week."

    def get_widgets(self):
        since = get_tz_date(datetime.utcnow().date() - timedelta(days=self.NUM_DAYS))

        # if organization is new, then omitt caveats
        if self.organization.created_at >= since:
            return {}

        return {"caveats": self.get_caveats(since)}

    def get_caveats(self, since):
        caveats = {}

        num_added_connections = self.get_added_connections(since)
        if num_added_connections:
            caveats["connections"] = self.TEXT_ADDED_CONNECTIONS.format(num=num_added_connections)

        num_added_repositories = self.get_added_repositories(since)
        if num_added_repositories:
            caveats["repositories"] = self.TEXT_ADDED_REPOSITORIES.format(num=num_added_repositories)

        sema_score_changed = self.check_sema_score_changed(since)
        if sema_score_changed:
            caveats["sema_score"] = self.TEXT_SEMA_SCORE

        return caveats

    def get_added_connections(self, since):
        return DataProviderConnection.objects.filter(
            organization=self.organization, data__isnull=False, created_at__gte=since
        ).count()

    def get_added_repositories(self, since):
        # TODO add other providers that count repositories when we have them, such as BitBucket
        return DataProviderProject.objects.filter(
            organization=self.organization,
            provider=GitHubIntegration().provider,
            created_at__gte=since,
        ).count()

    def check_sema_score_changed(self, since):
        return AppComponentVersion.objects.filter(
            component=AppComponentChoices.SEMA_SCORE,
            updated_at__gte=since,
        ).exists()
