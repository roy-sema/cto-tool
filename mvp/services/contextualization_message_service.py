import copy
import logging
import re
import statistics
from enum import Enum
from typing import Any, TypedDict

from django.db.models import QuerySet

from compass.contextualization.models import (
    MessageFilterData,
    SignificanceLevelChoices,
)
from compass.integrations.apis.jira_api import JiraApiConfig
from compass.integrations.integrations.git_base_integration import GitBaseIntegration
from compass.integrations.integrations.jira_integration import JiraIntegration
from mvp.mixins import DecodePublicIdMixin
from mvp.models import DataProviderConnection, JiraProject, Organization, Repository
from mvp.services import (
    ConnectedIntegrationsService,
    ContextualizationDayInterval,
    ContextualizationService,
)

logger = logging.getLogger(__name__)


class ContextualizationMessageData(TypedDict):
    last_updated: float
    user_configuration: dict[str, list]
    anomaly_insights_and_risks: dict[str, Any]
    aggregated_anomaly_insights_and_risks: list[dict]
    jira_completeness_score: dict[str, Any]
    jira_quality_summary: dict[str, Any]
    jira_completeness_summary: dict[str, Any]
    aggregated_anomaly_insights: dict[str, Any]
    data_sets_used: dict[str, Any]


class JiraQualityCategory(Enum):
    ADVANCED = "Advanced"
    MATURE = "Mature"
    EMERGING = "Emerging"
    INITIAL = "Initial"


class ContextualizationMessageService:
    # Class-level cache for expensive operations
    _jira_base_url_cache = {}
    _repository_cache = {}
    _decoded_id_cache = {}

    @classmethod
    def get_for_day_interval(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
    ) -> ContextualizationMessageData:
        """
        This collects data from various services across the system to
        provide data for the daily and weekly message emails and views.
        """
        repositories: QuerySet[Repository] = organization.repository_set.all()
        repository_public_id_map = {repo.public_id(): repo for repo in repositories}

        anomaly_insights_and_risks, anomaly_insights_and_risks_updated_at = cls.get_anomaly_insights_and_risks(
            organization, repository_public_id_map, day_interval
        )

        jira_completeness_score, jira_completeness_score_updated_at = cls.get_jira_completeness_score(
            organization, day_interval
        )

        jira_quality_summary, jira_quality_summary_updated_at = cls.get_jira_quality_summary(organization, day_interval)

        jira_completeness_summary = cls.get_jira_completeness_summary(jira_quality_summary)

        aggregated_anomaly_insights, aggregated_anomaly_insights_updated_at = cls.get_aggregated_anomaly_insights(
            organization, repository_public_id_map, day_interval
        )

        jira_anomaly_insights_and_risks, jira_anomaly_insights_and_risks_updated_at = (
            cls.get_jira_anomaly_insights_and_risks(organization, day_interval)
        )

        combined_code_and_jira_anomaly_and_risks = cls.combine_code_and_jira_anomaly_and_risks(
            anomaly_insights_and_risks,
            jira_anomaly_insights_and_risks,
        )

        user_configuration = cls.get_user_configuration(combined_code_and_jira_anomaly_and_risks)

        aggregated_anomaly_insights_and_risks = cls.aggregate_combined_anomaly_insights_and_risks(
            combined_code_and_jira_anomaly_and_risks
        )

        # Determine the most recent update time across all data sources
        updated_at = max(
            anomaly_insights_and_risks_updated_at,
            jira_completeness_score_updated_at,
            jira_quality_summary_updated_at,
            aggregated_anomaly_insights_updated_at,
            jira_anomaly_insights_and_risks_updated_at,
        )
        return ContextualizationMessageData(
            last_updated=updated_at,
            user_configuration=user_configuration,
            anomaly_insights_and_risks=combined_code_and_jira_anomaly_and_risks,
            aggregated_anomaly_insights_and_risks=aggregated_anomaly_insights_and_risks,
            jira_completeness_score=jira_completeness_score,
            jira_quality_summary=jira_quality_summary,
            jira_completeness_summary=jira_completeness_summary,
            aggregated_anomaly_insights=aggregated_anomaly_insights,
            data_sets_used=cls.get_data_sets_used(organization),
        )

    @classmethod
    def get_anomaly_insights_and_risks(
        cls,
        organization: Organization,
        repository_public_id_map: dict[str, Repository],
        day_interval: ContextualizationDayInterval,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            ContextualizationService.OUTPUT_FILENAME_COMBINED_ANOMALY_INSIGHTS,
            day_interval=day_interval,
        )
        if not data:
            return None, updated_at

        formatted_insights = cls.format_anomaly_insights_and_risks(data, repository_public_id_map, organization)

        return formatted_insights, updated_at

    @staticmethod
    def aggregate_combined_anomaly_insights_and_risks(
        combined_code_and_jira_anomaly_and_risks: dict,
    ):
        all_anomalies = sorted(
            (anomaly for anomalies in combined_code_and_jira_anomaly_and_risks.values() for anomaly in anomalies),
            key=lambda a: a.get("significance_score", 0),
            reverse=True,
        )
        return all_anomalies

    @staticmethod
    def get_user_configuration(combined_code_and_jira_anomaly_and_risks: dict):
        product_groups = set()
        significance_scores = set()

        for anomalies in combined_code_and_jira_anomaly_and_risks.values():
            for anomaly in anomalies:
                significance_scores.add(anomaly["significance_score"])
                if "project_name" in anomaly:
                    product_groups.add(anomaly["project_name"])

        return {
            "product_groups": list(product_groups),
            "significance_scores": sorted(significance_scores, reverse=True),
        }

    @classmethod
    def format_anomaly_insights_and_risks(
        cls,
        data: dict,
        repository_public_id_map: dict[str, Repository],
        organization: Organization,
    ):
        formatted_anomaly_insights_and_risks = {choice.value: [] for choice in SignificanceLevelChoices}

        data = {
            "anomaly": data.get("anomaly_insights", []),
            "risk": data.get("risk_insights", []),
        }

        for insight_type, insights in data.items():
            for insight in insights:
                significance_score = insight.get("significance_score", 0)
                if significance_score < SignificanceLevelChoices.SEVEN.value:
                    logger.warning(
                        "Anomaly insight found with significance score lower than 7",
                        extra={
                            "insight_type": insight_type,
                            "organization": organization.name,
                            "insight": insight,
                        },
                    )
                    continue

                repo_public_id = insight["repo"]
                repo = repository_public_id_map[repo_public_id]

                formatted_anomaly_insights_and_risks[round(significance_score)].append(
                    {
                        "type": insight_type,
                        **cls.enhance_repo_insight(insight, repo_public_id, repo),
                    }
                )

        insights_with_repos = cls.add_repos_to_formatted_anomaly_insights_and_risks(
            formatted_anomaly_insights_and_risks, repository_public_id_map
        )

        return insights_with_repos

    @classmethod
    def get_filtered_daily_message_data(cls, data, message_filter: MessageFilterData | None):
        if not message_filter:
            return data

        filtered_data = copy.deepcopy(data)

        filtered_insights = filtered_data.get("anomaly_insights_and_risks", {})

        # filter by significance level
        if message_filter["significance_levels"]:
            filtered_insights = {
                key: value
                for key, value in filtered_insights.items()
                if str(key) in message_filter["significance_levels"]
            }

        if message_filter["ticket_categories"]:
            selected_categories = set(message_filter["ticket_categories"])
            for significance_level, insights in filtered_insights.items():
                filtered_insights[significance_level] = [
                    insight
                    for insight in insights
                    # if no ticket categories, or one of categories matches to user filter - include the insight
                    if not insight.get("ticket_categories")
                    or set(insight["ticket_categories"]).intersection(selected_categories)
                ]

        aggregated_anomaly_insights = filtered_data.get("aggregated_anomaly_insights", {})
        filtered_groups_of_insights = (
            aggregated_anomaly_insights.get("groups_of_insights", []) if aggregated_anomaly_insights else []
        )

        # filter by group
        if repository_groups := message_filter["repository_groups"]:
            # TODO check how to handle ungrouped repos currently they are being shown regardless
            for significance_level in filtered_insights:
                filtered_insights[significance_level] = [
                    item
                    for item in filtered_insights[significance_level]
                    if (repo_group := item.get("repo_group")) is None or repo_group in repository_groups
                ]
            for insight_group in filtered_groups_of_insights:
                insight_group["details_of_insights"] = [
                    item
                    for item in insight_group["details_of_insights"]
                    if (repo_group := item.get("repo_group")) is None or repo_group in repository_groups
                ]

            # Filter by Jira projects associated with repository groups
            jira_project_names = set()
            jira_project_keys = set()
            for repo_group in repository_groups:
                repo_group_id = DecodePublicIdMixin().decode_id(repo_group)
                jira_projects = JiraProject.objects.filter(repository_group=repo_group_id)
                jira_project_names.update(jira_projects.values_list("name", flat=True))
                jira_project_keys.update(jira_projects.values_list("key", flat=True))

            # Apply Jira project filtering to insights
            if jira_project_names:
                for significance_level in filtered_insights:
                    filtered_insights[significance_level] = [
                        item
                        for item in filtered_insights[significance_level]
                        if (project_name := item.get("project_name")) is None or project_name in jira_project_names
                    ]
                for insight_group in filtered_groups_of_insights:
                    insight_group["details_of_insights"] = [
                        item
                        for item in insight_group["details_of_insights"]
                        if (project_name := item.get("project_name")) is None or project_name in jira_project_names
                    ]

                if filtered_data.get("jira_quality_summary"):
                    # Completes score filters
                    filtered_data["jira_quality_summary"]["by_project"] = [
                        item
                        for item in data["jira_quality_summary"]["by_project"]
                        if (project_name := item.get("project")) is None or project_name in jira_project_keys
                    ]
                    # Generate new summary after filters
                    filtered_data["jira_completeness_summary"] = cls.get_jira_completeness_summary(
                        filtered_data["jira_quality_summary"]
                    )

        filtered_data["anomaly_insights_and_risks"] = filtered_insights
        if filtered_groups_of_insights:
            filtered_data["aggregated_anomaly_insights"]["groups_of_insights"] = filtered_groups_of_insights

        # Uses filtered insights to generate user configuration
        filtered_data["user_configuration"] = cls.get_user_configuration(filtered_insights)

        # Uses filtered insights to generate aggregated insights
        filtered_data["aggregated_anomaly_insights_and_risks"] = cls.aggregate_combined_anomaly_insights_and_risks(
            filtered_insights
        )

        return filtered_data

    @classmethod
    def get_jira_url(cls, organization: Organization, task_id: str):
        # Use class-level cache for Jira base URL to prevent repetitive DB lookups
        org_id = organization.id
        if org_id not in cls._jira_base_url_cache:
            try:
                connection = DataProviderConnection.objects.get(
                    organization=organization,
                    provider__name="Jira",
                )

                if not connection.is_connected():
                    return None

                jira_integration = JiraIntegration()
                jira_integration.init_api(
                    config=JiraApiConfig(
                        access_token=connection.data.get("access_token"),
                        refresh_token=connection.data.get("refresh_token"),
                        cloud_id=connection.data.get("cloud_id"),
                    ),
                    connection=connection,
                )
                cls._jira_base_url_cache[org_id] = jira_integration.get_base_jira_url(connection)
            except Exception:
                logger.exception("Error getting Jira URL", extra={"organization": organization})
                cls._jira_base_url_cache[org_id] = None
        base_url = cls._jira_base_url_cache[org_id]
        return f"{base_url}/browse/{task_id}" if base_url else None

    @classmethod
    def get_resource_url(cls, repository_pk: int, resource_type: str, args: list):
        # Use repository cache to avoid repetitive database lookups
        repository = cls._repository_cache.get(repository_pk)
        if not repository:
            repository = Repository.objects.select_related("organization", "provider").get(pk=repository_pk)
            cls._repository_cache[repository_pk] = repository

        provider_name = repository.provider.name.lower()

        integration_class = ConnectedIntegrationsService.INTEGRATION_MAP.get(provider_name)

        # Check if it's a git integration and is a subclass of GitBaseIntegration
        if (not integration_class) or (provider_name not in ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS):
            return None

        if issubclass(integration_class, GitBaseIntegration):
            # Call the appropriate method based on resource type
            if resource_type == "commit":
                return integration_class.get_commit_url(repository, *args)
            elif resource_type == "file":
                file_name = args[0].get("file_name", "")
                commit_hash = args[0].get("commit_id", "")
                branch_name = args[0].get("branch_name", "")
                return integration_class.get_file_url(repository, file_name, commit_hash, branch_name)

        return None

    @classmethod
    def create_detailed_sources_and_files(cls, organization: Organization, insight: dict):
        """Transform insight data into a list of sources and files with URLs.

        Args:
            insight: Dictionary containing insight data

        Returns:
            List of dictionaries with 'url' and 'label' keys
        """

        if insight.get("source"):
            insight["sources"] = insight["source"]

        detailed_sources_and_files = []

        if "project_name" in insight:
            # If we are support other projects other than JIRA
            project_key = insight.get("project_name")

            for task_id in insight.get("sources", []):
                # If it is a Jira ticket
                if bool(re.match(r"^([A-Z]+)-\d+$", task_id)):
                    detailed_sources_and_files.append(
                        {
                            "url": cls.get_jira_url(organization, task_id),
                            "label": task_id,
                        }
                    )
                else:
                    detailed_sources_and_files.append(
                        {
                            "url": None,
                            "label": task_id,
                        }
                    )

        if "repo" in insight:
            # "repo" is the public_id of the repository
            repo_public_id = insight.get("repo")

            # Use cache for decoded IDs to avoid repetitive decoding operations
            if repo_public_id not in cls._decoded_id_cache:
                cls._decoded_id_cache[repo_public_id] = DecodePublicIdMixin().decode_id(repo_public_id)

            repo_pk = cls._decoded_id_cache[repo_public_id]

            if isinstance(insight.get("sources"), list):
                for commit_hash in insight["sources"]:
                    try:
                        url = cls.get_resource_url(repo_pk, "commit", [commit_hash])
                    except Exception:
                        logger.exception(
                            "Error determining commit URL",
                            extra={
                                "organization": organization,
                                "repo_public_id": repo_public_id,
                                "commit_hash": commit_hash,
                            },
                        )
                        url = None

                    detailed_sources_and_files.append(
                        {
                            "url": url,
                            "label": commit_hash,
                        }
                    )

            if isinstance(insight.get("files"), list):
                for file_details in insight["files"]:
                    try:
                        url = cls.get_resource_url(repo_pk, "file", [file_details])
                    except Exception:
                        logger.exception(
                            "Error determining file URL",
                            extra={
                                "organization": organization,
                                "repo_public_id": repo_public_id,
                                "file_details": file_details,
                            },
                        )
                        url = None

                    file_name = file_details.get("file_name")

                    if file_name:
                        if "<UNKNOWN>" in file_name or "." not in file_name or file_name.endswith("."):
                            continue
                        detailed_sources_and_files.append(
                            {
                                "url": url,
                                "label": file_name,
                            }
                        )
                    else:
                        logger.error(
                            "File name is missing for file from contextualization insight",
                            extra={
                                "organization": organization,
                                "repo_public_id": repo_public_id,
                                "file_details_that_failed": file_details,
                            },
                        )

        return detailed_sources_and_files

    @classmethod
    def enhance_repo_insight(
        cls,
        insight: dict,
        repo_public_id: str,
        repo: Repository,
    ):
        repo_full_name = repo.full_name()
        repo_group = repo.group

        # Prepare the enhanced insight without the detailed_sources_and_files
        # This allows us to batch process or defer the expensive operation
        enhanced_insight = {
            "repo": insight["repo"],
            "repo_full_name": repo_full_name,
            "repo_group": repo_group.public_id() if repo_group else None,
            "repo_group_name": repo_group.name if repo_group else None,
            "category": insight.get("category", "").replace("_", " ").title(),
            "title": insight.get("title", "").title(),
            "insight": insight.get("insight", "").replace(repo_public_id, repo_full_name),
            "evidence": insight.get("evidence", "").replace(repo_public_id, repo_full_name),
            "significance_score": insight.get("significance_score"),
            "confidence_level": insight.get("confidence_level"),
            "resolution": insight.get("resolution", "").replace(repo_public_id, repo_full_name),
            "messages": [
                {
                    "audience": message["audience"],
                    "message_for_audience": message.get("message_for_audience", "").replace(
                        repo_public_id, repo_full_name
                    ),
                }
                for message in insight.get("messages", [])
            ],
            "sources": insight.get("sources", []),
            "files": insight.get("files", []),
        }

        # Add detailed_sources_and_files - this is an expensive operation
        enhanced_insight["detailed_sources_and_files"] = cls.create_detailed_sources_and_files(
            repo.organization, insight
        )

        return enhanced_insight

    @staticmethod
    def add_repos_to_formatted_anomaly_insights_and_risks(
        formatted_anomaly_insights_and_risks: dict,
        repository_public_id_map: dict[str, Repository],
    ) -> dict:
        result = {}

        for key, insights in formatted_anomaly_insights_and_risks.items():
            if not insights:
                result[key] = {}
                continue

            repo_names = {repository_public_id_map[insight["repo"]].full_name() for insight in insights}

            result[key] = {
                "repos": ", ".join(repo_names),
                "insights": insights,
            }

        return result

    @classmethod
    def get_jira_completeness_score(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            ContextualizationService.OUTPUT_FILENAME_JIRA_COMPLETENESS_SCORE,
            day_interval=day_interval,
        )
        if not data:
            return None, updated_at

        return cls.format_jira_completeness_score(data), updated_at

    @classmethod
    def get_jira_quality_summary(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            ContextualizationService.OUTPUT_FILENAME_JIRA_QUALITY_SUMMARY,
            day_interval=day_interval,
        )
        if not data:
            return None, updated_at

        return cls.enhance_jira_quality_summary(organization, data), updated_at

    @classmethod
    def get_jira_completeness_summary(cls, jira_quality_summary: dict | None):
        if not jira_quality_summary:
            return None

        projects = jira_quality_summary.get("by_project")
        if not projects:
            return None

        by_project = [
            {
                "project_key": project["project"],
                "score": project["average_score"],
                "quality_category": project["quality_category"],
            }
            for project in projects
        ]

        by_stage = {}
        by_category = {}
        for project in projects:
            for stage_data in project["by_stage"]:
                stage = stage_data["stage"]
                stage_entry = by_stage.setdefault(stage, {"ticket_count": 0, "average_counts": []})
                stage_entry["ticket_count"] += stage_data["ticket_count"]
                stage_entry["average_counts"].append(stage_data["average_count"])

            for category_data in project["by_category"]:
                category = category_data["category"]
                category_entry = by_category.setdefault(category, {"ticket_count": 0, "average_counts": []})
                category_entry["ticket_count"] += category_data["ticket_count"]
                category_entry["average_counts"].append(category_data["average_count"])

        by_stage_with_average_score_and_quality_category = []
        for stage, data in by_stage.items():
            avg_score = statistics.mean(data["average_counts"])
            by_stage_with_average_score_and_quality_category.append(
                {
                    "stage": stage,
                    "ticket_count": data["ticket_count"],
                    "score": avg_score,
                    "average_count": avg_score,  # backward compatibility
                    "average_counts": data["average_counts"],
                    "quality_category": cls.get_jira_quality_category(avg_score),
                }
            )

        by_category_with_average_score_and_quality_category = []
        for category, data in by_category.items():
            avg_score = statistics.mean(data["average_counts"])
            by_category_with_average_score_and_quality_category.append(
                {
                    "category": category,
                    "ticket_count": data["ticket_count"],
                    "score": avg_score,
                    "average_count": avg_score,  # backward compatibility
                    "average_counts": data["average_counts"],
                    "quality_category": cls.get_jira_quality_category(avg_score),
                }
            )

        return {
            "by_projects": by_project,
            "by_stage": by_stage_with_average_score_and_quality_category,
            "by_category": by_category_with_average_score_and_quality_category,
        }

    @classmethod
    def enhance_jira_quality_summary(cls, organization: Organization, data: dict):
        data["all_projects"] = {
            "quality_category": cls.get_jira_quality_category(data["all_projects"]["average_score"]),
            **data["all_projects"],
        }
        data["by_project"] = [
            {
                "quality_category": cls.get_jira_quality_category(project["average_score"]),
                "project_name": cls.get_jira_project_name(organization, project["project"]),
                **project,
            }
            for project in data.get("by_project", [])
        ]
        return data

    @classmethod
    def get_jira_quality_category(cls, value: float):
        if value >= 76:
            return JiraQualityCategory.ADVANCED.value
        elif value >= 51:
            return JiraQualityCategory.MATURE.value
        elif value >= 26:
            return JiraQualityCategory.EMERGING.value
        elif value >= 1:
            return JiraQualityCategory.INITIAL.value
        else:
            return "Unknown"

    @staticmethod
    def get_jira_project_name(organization: Organization, project_key: str):
        # Getting first here as `key` is not a unique field.
        jira_project = JiraProject.objects.filter(organization=organization, key=project_key).first()

        if not jira_project:
            return None

        return jira_project.name

    @classmethod
    def format_jira_completeness_score(cls, data: list):
        """
        This returns the score and the three highest and three lowest scored tickets.
        """
        excellent_tickets = []
        initial_quality_tickets = []

        for project in data:
            excellent_tickets.extend(cls.get_tickets("excellent_tickets", project))
            initial_quality_tickets.extend(cls.get_tickets("initial_quality_tickets", project))

        tickets_with_highest_score = sorted(excellent_tickets, key=lambda ticket: ticket["score"], reverse=True)[:3]
        tickets_with_lowest_score = sorted(initial_quality_tickets, key=lambda ticket: ticket["score"])[:3]

        return {
            "average_score": (sum(project["average_score"] for project in data) / len(data) if data else 0),
            "tickets_with_highest_score": tickets_with_highest_score,
            "tickets_with_lowest_score": tickets_with_lowest_score,
        }

    @staticmethod
    def get_tickets(field: str, data: dict):
        try:
            return data[field]["summary"]["examples"]
        except KeyError:
            return []

    @classmethod
    def get_jira_anomaly_insights_and_risks(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            ContextualizationService.OUTPUT_FILENAME_JIRA_ANOMALY_INSIGHTS,
            day_interval=day_interval,
        )
        if not data:
            return None, updated_at

        return cls.format_jira_anomaly_insights_and_risks(organization, data), updated_at

    @classmethod
    def format_jira_anomaly_insights_and_risks(cls, organization: Organization, data: dict):
        formatted_anomaly_insights_and_risks = {choice.value: [] for choice in SignificanceLevelChoices}

        data = {
            "anomaly": data.get("anomaly_insights", []),
            "risk": data.get("risk_insights", []),
        }

        for insight_type, insights in data.items():
            for insight in insights:
                significance_score = insight.get("significance_score", 0)
                if significance_score < SignificanceLevelChoices.SEVEN.value:
                    logger.info(
                        "Anomaly insight found with significance score lower than 7",
                        extra={
                            "insight_type": insight_type,
                            "organization": organization.name,
                            "insight": insight,
                        },
                    )
                    continue

                formatted_insight = {
                    **insight,
                    "category": insight["category"].replace("_", " ").title(),
                    "sources": insight.get("sources", []),
                    "files": insight.get("files", []),
                    "detailed_sources_and_files": cls.create_detailed_sources_and_files(organization, insight),
                }

                formatted_anomaly_insights_and_risks[round(significance_score)].append(
                    {
                        "type": insight_type,
                        **formatted_insight,
                    }
                )

        insights_with_projects = cls.add_projects_to_formatted_jira_anomaly_insights_and_risks(
            formatted_anomaly_insights_and_risks
        )

        return insights_with_projects

    @staticmethod
    def add_projects_to_formatted_jira_anomaly_insights_and_risks(
        formatted_anomaly_insights_and_risks: dict,
    ) -> dict:
        result = {}

        for key, insights in formatted_anomaly_insights_and_risks.items():
            if not insights:
                result[key] = {}
                continue

            repo_names = {insight["project_name"] for insight in insights}

            result[key] = {
                "projects": ", ".join(repo_names),
                "insights": insights,
            }

        return result

    @classmethod
    def get_aggregated_anomaly_insights(
        cls,
        organization: Organization,
        repository_public_id_map: dict[str, Repository],
        day_interval: ContextualizationDayInterval,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            ContextualizationService.OUTPUT_FILENAME_INSIGHTS_AGGREGATION,
            day_interval=day_interval,
        )
        if not data:
            return None, updated_at

        formatted_aggregated_anomaly_insights = cls.format_aggregated_anomaly_insights(data, repository_public_id_map)

        return formatted_aggregated_anomaly_insights, updated_at

    @classmethod
    def format_aggregated_anomaly_insights(
        cls,
        data: dict,
        repository_public_id_map: dict[str, Repository],
    ):
        return {
            "summary": cls.replace_repo_public_id_with_full_name(data["summary"], repository_public_id_map),
            "groups_of_insights": [
                {
                    "similar_insight_ids": group_of_insights["similar_insight_ids"],
                    "similarity_reason": cls.replace_repo_public_id_with_full_name(
                        group_of_insights["similarity_reason"], repository_public_id_map
                    ),
                    "details_of_insights": [
                        cls.enhance_aggregated_anomaly_insight(insight, repository_public_id_map)
                        for insight in group_of_insights["details_of_insights"]
                    ],
                }
                for group_of_insights in data["groups_of_insights"]
            ],
        }

    @classmethod
    def enhance_aggregated_anomaly_insight(
        cls,
        insight: dict,
        repository_public_id_map: dict[str, Repository],
    ):
        # An insight here can be either a repo or project insight.
        repo_public_id = insight.get("repo")
        if repo_public_id:
            repo = repository_public_id_map[repo_public_id]
            return {
                **cls.enhance_repo_insight(insight, repo_public_id, repo),
                "unique_id": insight["unique_id"],
            }

        # Assumed to be a Jira project insight.
        return {**insight, "category": insight["category"].replace("_", " ").title()}

    @staticmethod
    def replace_repo_public_id_with_full_name(data: str, repository_public_id_map: dict[str, Repository]):
        for public_id, repo in repository_public_id_map.items():
            data = data.replace(public_id, repo.full_name())
        return data

    @classmethod
    def combine_code_and_jira_anomaly_and_risks(cls, code_anomaly_and_risks: dict, jira_anomaly_and_risks: dict):
        code_anomaly_and_risks = code_anomaly_and_risks or {}
        jira_anomaly_and_risks = jira_anomaly_and_risks or {}

        significance_levels = [choice.value for choice in SignificanceLevelChoices]

        return {
            level: [
                *(code_anomaly_and_risks.get(level) or {}).get("insights", []),
                *(jira_anomaly_and_risks.get(level) or {}).get("insights", []),
            ]
            for level in significance_levels
        }

    @staticmethod
    def get_data_sets_used(organization: Organization):
        return ConnectedIntegrationsService.get_connected_integration_statuses(organization)
