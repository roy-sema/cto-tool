from datetime import datetime

from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView


class BudgetView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_budget"

    def get(self, request, *args, **kwargs):
        # TODO get real data
        updated_at = datetime(2024, 10, 30).timestamp()
        integrations = {
            "github": {"status": True, "display_name": "GitHub"},
            "jira": {"status": True, "display_name": "Jira"},
        }
        metrics = [
            {
                "name": "Infrastructure and Operations",
                "current": 945000,
                "total_budget": 1575000,
                "color": "green",
                "sub_metrics": [
                    {
                        "name": "Cloud resources",
                        "color": "green",
                        "status": "$120k under",
                    },
                    {
                        "name": "Data center",
                        "color": "green",
                        "status": "$45k under",
                    },
                    {
                        "name": "Network",
                        "color": "green",
                        "status": "$30k under",
                    },
                    {
                        "name": "Continuity systems",
                        "color": "green",
                        "status": "$60k under",
                    },
                ],
            },
            {
                "name": "Personnel and Talent",
                "current": 1368900,
                "total_budget": 1755000,
                "color": "yellow",
                "sub_metrics": [
                    {
                        "name": "Technical staff salaries and benefits",
                        "color": "green",
                        "status": "$120k under",
                    },
                    {
                        "name": "Training and professional development",
                        "color": "red",
                        "status": "$45k over",
                    },
                    {
                        "name": "External consultants and contractors",
                        "color": "green",
                        "status": "$45k under",
                    },
                    {
                        "name": "Technical Recruitment",
                        "color": "red",
                        "status": "$45k over",
                    },
                ],
            },
            {
                "name": "Security and Compliance",
                "current": 513000,
                "total_budget": 855000,
                "color": "green",
                "sub_metrics": [
                    {
                        "name": "Cybersecurity tools",
                        "color": "green",
                        "status": "$50k under",
                    },
                    {
                        "name": "Audit requirements",
                        "color": "green",
                        "status": "$40k under",
                    },
                    {
                        "name": "Personnel and training",
                        "color": "green",
                        "status": "$45k under",
                    },
                    {
                        "name": "Incident response",
                        "color": "green",
                        "status": "$35k under",
                    },
                ],
            },
            {
                "name": "Development and Innovation",
                "current": 585900,
                "total_budget": 630000,
                "color": "red",
                "sub_metrics": [
                    {
                        "name": "Tools and platforms",
                        "color": "red",
                        "status": "$40k over",
                    },
                    {
                        "name": "Quality assurance",
                        "color": "red",
                        "status": "$35k over",
                    },
                    {
                        "name": "DevOps",
                        "color": "green",
                        "status": "$45k under",
                    },
                    {
                        "name": "Innovation labs",
                        "color": "yellow",
                        "status": "$1k under",
                    },
                ],
            },
            {
                "name": "Support and Maintenance",
                "current": 491400,
                "total_budget": 630000,
                "color": "yellow",
                "sub_metrics": [
                    {
                        "name": "Operations",
                        "color": "yellow",
                        "status": "$1k over",
                    },
                    {
                        "name": "Hardware replacement",
                        "color": "green",
                        "status": "$20k under",
                    },
                    {
                        "name": "Software maintenance",
                        "color": "red",
                        "status": "$30k over",
                    },
                    {
                        "name": "Debt reduction",
                        "color": "green",
                        "status": "$15k under",
                    },
                ],
            },
        ]
        summary = "Development/Innovation nearing budget limit at 93% (S630,000), requiring immediate attention. Core departments show varied utilization - Personnel at 78% ($1.75M) with mixed spending patterns, while Infrastructure and Security maintain 60% utilization of their respective budgets ($1.57M, $855K). Total IT budget execution indicates need for resource rebalancing."
        insights = [
            "Development and Innovation's 93% utilization rate versus other departments' 60-78% suggests an immediate need for budget review or reallocation.",
            "Personnel and Talent shows mixed efficiency with $120k under-spending on salaries but over-spending on training and recruitment, indicating a shift in workforce strategy.",
            "Security and Compliance's low 60% utilization despite a $855k budget raises potential risk concerns in the current cybersecurity landscape.",
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
