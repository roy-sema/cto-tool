import csv
import io
import zipfile

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.views import View

from mvp.models import Author, AuthorGroup, AuthorStat
from mvp.serializers import AggregatedAuthorStatSerializer
from mvp.services import GroupsAICodeService, RuleService


class DeveloperGroupsExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request, *args, **kwargs):
        buffer = io.BytesIO()
        organization = request.current_organization

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            csv_data_group = self.generate_author_group_csv(organization)
            zip_file.writestr("developer_groups.csv", csv_data_group)

            csv_data_author = self.generate_author_csv(organization)
            zip_file.writestr("developers.csv", csv_data_author)

        buffer.seek(0)

        response = HttpResponse(buffer, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{organization.name} developer groups.zip"'

        return response

    def generate_author_group_csv(self, organization, include_ungrouped=True):
        """Generate CSV data for AuthorGroup."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Developer Group Name",
                "GenAI%",
                "NotGenAI%",
                "Pure%",
                "Blended%",
                "Rules:Associated Risk",
            ]
        )

        author_groups = (
            AuthorGroup.objects.filter(organization=organization).prefetch_related("rules").order_by("name").all()
        )

        for group in author_groups:
            stats = AuthorStat.get_aggregated_group_stats(group.id)
            aggregated_stats = AggregatedAuthorStatSerializer(stats).data

            all_rules = list(RuleService.get_organization_rules(organization)) + group.rule_list()
            rules = RuleService.get_stats_rules_list(
                aggregated_stats,
                all_rules,
            )
            rules_status = " | ".join(f"{rule.name}: {risk}" for rule, risk in rules)
            writer.writerow(
                [
                    group.name,
                    aggregated_stats["percentage_ai_overall"],
                    aggregated_stats["percentage_human"],
                    aggregated_stats["percentage_ai_pure"],
                    aggregated_stats["percentage_ai_blended"],
                    rules_status,
                ]
            )

        if include_ungrouped:
            ungrouped = GroupsAICodeService(organization).get_ungrouped_group()
            ungrouped["stats"] = AggregatedAuthorStatSerializer(ungrouped["stats"]).data
            writer.writerow(
                [
                    ungrouped["name"],
                    ungrouped["stats"]["percentage_ai_overall"],
                    ungrouped["stats"]["percentage_human"],
                    ungrouped["stats"]["percentage_ai_pure"],
                    ungrouped["stats"]["percentage_ai_blended"],
                    "N/A",
                ]
            )

        return output.getvalue()

    def generate_author_csv(self, organization):
        """Generate CSV data for Author."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Developer Name",
                "Developer Group Name",
            ]
        )

        authors = (
            Author.objects.filter(organization=organization, linked_author__isnull=True)
            .select_related("group")
            .order_by("name")
            .all()
        )
        for author in authors:
            group_name = author.group.name if author.group else "Ungrouped"
            writer.writerow(
                [
                    author.name or author.email,
                    group_name,
                ]
            )

        return output.getvalue()
