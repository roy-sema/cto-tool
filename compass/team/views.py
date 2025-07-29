from datetime import datetime

from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView


class TeamView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_team"

    def get(self, request, *args, **kwargs):
        # TODO get real data
        updated_at = datetime(2024, 10, 30).timestamp()
        integrations = {
            "github": {"status": True, "display_name": "GitHub"},
            "jira": {"status": True, "display_name": "Jira"},
        }
        metrics = [
            {
                "name": "Team Retention",
                "current": "76",
                "goal": "85",
                "max": "100",
                "postfix": "%",
                "status": "At Risk",
                "color": "red",
            },
            {
                "name": "Cycle Time",
                "current": "7",
                "goal": "10",
                "max": "14",
                "postfix": " days",
                "status": "On track",
                "color": "green",
            },
            {
                "name": "On-call Incidents",
                "current": "45",
                "goal": "0",
                "max": "100",
                "postfix": "% increase",
                "status": "At Risk",
                "color": "red",
            },
            {
                "name": "Pull Request Review Time",
                "current": "12",
                "goal": "24",
                "max": "24",
                "postfix": " hours",
                "status": "Warning",
                "color": "yellow",
            },
            {
                "name": "Build Success Rate",
                "current": "92",
                "goal": "95",
                "max": "100",
                "postfix": "%",
                "status": "Warning",
                "color": "yellow",
            },
        ]
        summary = "Team health metrics show concerning trends across all key indicators. Team retention (76%) and incident rate (+45%) are significantly below targets, while cycle time and PR reviews show workflow bottlenecks. Build success rate remains close to target but requires attention."
        insights = [
            "High correlation between cycle time increase and team retention decline suggests workload issues",
            "Rising on-call incidents impacting both retention and PR review times - consider revising on-call rotations",
            "Build failures concentrated in payment integration components - prioritize infrastructure stability",
        ]

        return Response(
            {
                "updated_at": int(updated_at),
                "integrations": integrations,
                "metrics": metrics,
                "summary": summary,
                "insights": insights,
            }
        )
