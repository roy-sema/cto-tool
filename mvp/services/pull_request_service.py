import json
import os

from compass.integrations.integrations import get_git_provider_integration
from mvp.models import (
    AITypeChoices,
    CodeGenerationLabelChoices,
    RepositoryFile,
    RepositoryPullRequest,
    Rule,
)
from mvp.utils import get_whole_decimal

from .rule_service import RuleService


class PullRequestService:
    # This is the order in which labels will be displayed in dropdowns
    LABELS_ORDERED = [
        CodeGenerationLabelChoices.BLENDED,
        CodeGenerationLabelChoices.AI,
        CodeGenerationLabelChoices.HUMAN,
        CodeGenerationLabelChoices.NOT_EVALUATED,
    ]

    NUM_DECIMALS = 2

    def get_render_data(self, pull_request, include_not_evaluated=False):
        not_evaluated = []
        base_commit = pull_request.base_commit()
        head_commit = pull_request.head_commit()
        repository = pull_request.repository
        has_files = pull_request.analysis_num_files > 0
        rules = self.get_all_rules(repository.organization, repository) if has_files else []
        if head_commit and include_not_evaluated:
            not_evaluated = self.get_not_evaluated_files(head_commit)

        pull_request_url = None
        repository_url = None
        integration = get_git_provider_integration(repository.provider)
        if integration:
            pull_request_url = integration.get_pull_request_url(pull_request)
            repository_url = integration.get_repository_url(repository)

        return {
            "not_evaluated": not_evaluated,
            "ai_composition": self.get_pull_request_ai_composition(pull_request, rules),
            "is_analyzed": head_commit and head_commit.is_analyzed,
            "pull_request": pull_request,
            "pull_request_url": pull_request_url,
            "repository": repository,
            "repository_url": repository_url,
            "code_generation_labels": self.get_code_generation_labels(),
            "git_provider_name": integration().provider.name,
        }

    def get_not_evaluated_files(self, commit):
        metadata = self.get_metadata(commit)
        pr_files = metadata.get("changed_files", [])
        evaluated = self.get_commit_evaluated_file_paths(commit)
        file_paths = [file.relative_path for file in evaluated]
        return [file["filename"] for file in pr_files if file["filename"] not in file_paths]

    def get_metadata(self, commit):
        metadata_path = commit.metadata_file()
        if not metadata_path or not os.path.exists(metadata_path):
            return {}

        with open(metadata_path) as f:
            return json.load(f)

    def get_commit_evaluated_file_paths(self, commit):
        return RepositoryFile.objects.filter(commit=commit, not_evaluated=False).only("file_path")

    def load_file_lines(self, file_path):
        if not os.path.exists(file_path):
            return []

        with open(file_path) as code_file:
            return code_file.readlines()

    def get_pull_request_ai_composition(self, instance, rule_list):
        labels = {
            AITypeChoices.OVERALL: "percentage_ai_overall",
            AITypeChoices.PURE: "percentage_ai_pure",
            AITypeChoices.BLENDED: "percentage_ai_blended",
        }

        percentages = {}
        for label, method in labels.items():
            percentage = getattr(instance, method)(self.NUM_DECIMALS)
            percentages[label] = self.get_ai_values(percentage)

        return RuleService.format_ai_percentage_rules(percentages, rule_list, is_pull_request=True)

    def get_ai_values(self, value):
        whole, decimal = get_whole_decimal(value)
        sign = "+" if value >= 0 else "-"
        return {"value": value, "sign": sign, "whole": abs(whole), "decimal": decimal}

    def get_pull_request(self, request, external_id, pr_number):
        try:
            return RepositoryPullRequest.objects.prefetch_related("repository").get(
                repository__external_id=external_id,
                # don't use request.user_organizations because
                # that would grant superusers access to all PRs from all organizations
                repository__organization__in=request.user.organizations.all(),
                pr_number=pr_number,
            )
        except RepositoryPullRequest.DoesNotExist:
            return None

    def get_all_rules(self, organization, repository):
        rules = list(RuleService.get_organization_rules(organization))

        if repository.repository_group.exists():
            rules += list(Rule.objects.filter(repositorygroup__in=repository.repository_group.all()))

        return rules

    def get_markdown_render_data(self, pull_request):
        render_data = PullRequestService().get_render_data(pull_request)
        render_data["rules"] = self.get_rule_matrix(render_data["ai_composition"])
        return render_data

    def get_rule_matrix(self, ai_composition):
        matrix = []
        max_length = 0
        for ai_type in ai_composition:
            rules = ai_type["rules"]
            max_length = max(max_length, len(rules))
            matrix.append(rules)

        if not max_length:
            return []

        # unjagged matrix
        for row in matrix:
            row.extend([(None, None)] * (max_length - len(row)))

        # invert rows and columns
        return list(map(list, zip(*matrix, strict=False)))

    def get_code_generation_labels(self):
        return {choice.value: choice.label for choice in self.LABELS_ORDERED}
