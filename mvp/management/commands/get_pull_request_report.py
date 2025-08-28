import json
import logging
import os
import subprocess

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    GitHubIntegration,
    get_git_provider_integration,
    get_git_providers,
)
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import (
    DataProviderConnection,
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
)

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Creates a report of processed Pull Request for given organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "orgid",
            type=int,
            help="ID of the organization to check.",
        )

    def handle(self, *args, **options):
        organization_id = options["orgid"]

        connections = self.get_connections(organization_id)
        webhook_prs = self.parse_webhooks(connections)

        repositories = self.get_repositories(organization_id)

        shas = []
        azure_dev_ops_prs_by_project = {}
        for repository in repositories:
            for pr in repository.repositorypullrequest_set.all():
                # In Azure DevOps, PR number auto-increments per project, not per repository
                if repository.provider == AzureDevOpsIntegration().provider:
                    if repository.owner not in azure_dev_ops_prs_by_project:
                        azure_dev_ops_prs_by_project[repository.owner] = []

                    azure_dev_ops_prs_by_project[repository.owner].append(int(pr.pr_number))

                shas.append(pr.head_commit_sha)

        commits_by_repository = self.get_commits_by_repository(organization_id, shas)

        data = []
        for repository in repositories:
            data.append(
                self.get_repository_data(
                    repository,
                    commits_by_repository.get(repository.pk, {}),
                    webhook_prs.get(repository.external_id, []),
                )
            )

        azure_dev_ops_num_lost, azure_dev_ops_num_no_db = (
            self.get_azure_dev_ops_lost_process_error_prs(azure_dev_ops_prs_by_project, webhook_prs)
            if azure_dev_ops_prs_by_project
            else (0, 0)
        )

        self.print_report(data, azure_dev_ops_num_lost, azure_dev_ops_num_no_db)

    def print_report(self, data, azure_dev_ops_num_lost, azure_dev_ops_num_no_db):
        df = pd.DataFrame(data)

        counter = [
            "num_lost",
            "num_no_db",
            "num_no_commit",
            "num_failed",
            "num_pending",
            "num_analyzed",
        ]

        totals = df[["num_prs", *counter]].sum()
        totals["num_prs"] += azure_dev_ops_num_lost + azure_dev_ops_num_no_db
        totals["num_lost"] += azure_dev_ops_num_lost
        totals["num_no_db"] += azure_dev_ops_num_no_db

        for col_name in counter:
            df[col_name] = df[col_name].fillna(0)
            df["num_prs"] = df["num_prs"].fillna(0)
            df[col_name.replace("num_", "percent_")] = (df[col_name] / df["num_prs"] * 100).fillna(0)

            totals[col_name] = totals[col_name] if totals[col_name] is not None else 0
            totals["num_prs"] = totals["num_prs"] if totals["num_prs"] is not None else 0
            totals[col_name.replace("num_", "percent_")] = (
                totals[col_name] / totals["num_prs"] * 100 if totals["num_prs"] != 0 else 0
            )

        logger.info("\nBy repository:")
        logger.info(f"\n{df}")

        logger.info("\nTotals:")
        logger.info(f"\n{totals}")

        logger.info("\nLegend:")
        logger.info("- Lost: we didn't receive webhook or don't have the PR in the logs.")
        logger.info("- NoDB: we received the webhook, but we don't have the PR in the database.")
        logger.info(
            "- NoCommit: we have the PR in the database, but we don't have the commit (this may happen when we fetch closed PRs)."
        )
        logger.info("- Failed: the analysis has failed.")
        logger.info("- Pending: the analysis is pending.")
        logger.info("- Analyzed: the analysis has been completed.")

    def get_repository_data(self, repository, commits, webhook_pull_requests):
        prs = repository.repositorypullrequest_set.all()
        num_prs = len(prs)
        num_failed = 0
        num_no_commit = 0
        num_pending = 0
        num_analyzed = 0
        pr_numbers = []
        for pr in prs:
            pr_numbers.append(int(pr.pr_number))
            commit = commits.get(pr.head_commit_sha)
            if not commit:
                num_no_commit += 1
                continue

            if commit.status == RepositoryCommitStatusChoices.FAILURE:
                num_failed += 1

            if commit.status == RepositoryCommitStatusChoices.PENDING:
                num_pending += 1

            if commit.status == RepositoryCommitStatusChoices.ANALYZED:
                num_analyzed += 1

        num_lost = 0
        num_no_db = 0
        if num_prs and repository.provider == GitHubIntegration().provider:
            prs = sorted(set(pr_numbers))
            first = prs[0]
            last = prs[-1]
            for num in range(first, last):
                if num not in prs:
                    if num in webhook_pull_requests:
                        num_no_db += 1
                    else:
                        num_lost += 1

        return {
            "repository": repository.name,
            "num_prs": num_prs,
            "num_failed": num_failed,
            "num_lost": num_lost,
            "num_no_db": num_no_db,
            "num_no_commit": num_no_commit,
            "num_pending": num_pending,
            "num_analyzed": num_analyzed,
            "pr_numbers": pr_numbers,
        }

    def get_azure_dev_ops_lost_process_error_prs(self, prs_by_project, webhook_pull_requests):
        logger.info("\nAzure DevOps lost PRs:")
        total_lost = 0
        total_process_error = 0
        for project, pr_numbers in prs_by_project.items():
            unique_sorted_prs = sorted(set(pr_numbers))
            num_lost = 0
            num_no_db = 0

            lost_prs = []
            process_error_prs = []
            first = unique_sorted_prs[0]
            last = unique_sorted_prs[-1]
            for num in range(first, last):
                if num not in unique_sorted_prs:
                    if num in webhook_pull_requests:
                        num_no_db += 1
                        process_error_prs.append(str(num))
                    else:
                        num_lost += 1
                        lost_prs.append(str(num))

            if not num_lost and not num_no_db:
                continue

            total_lost += num_lost
            total_process_error += num_no_db

            if num_lost:
                logger.info(f"- Project '{project}': {num_lost} PRs lost: {', '.join(lost_prs)}")

            if num_no_db:
                logger.info(f"- Project '{project}': {num_no_db} PRs not in DB: {', '.join(process_error_prs)}")

        logger.info("\n---\n")

        return total_lost, total_process_error

    def get_repositories(self, organization_id):
        return (
            Repository.objects.filter(organization_id=organization_id)
            .prefetch_related("provider", "repositorypullrequest_set")
            .order_by("owner", "name")
            .all()
        )

    def get_commits_by_repository(self, organization_id, shas):
        commits = RepositoryCommit.objects.filter(repository__organization_id=organization_id, sha__in=shas).all()

        commits_by_repository = {}
        for commit in commits:
            if commit.repository_id not in commits_by_repository:
                commits_by_repository[commit.repository_id] = {}

            commits_by_repository[commit.repository_id][commit.sha] = commit

        return commits_by_repository

    def get_connections(self, organization_id):
        return (
            DataProviderConnection.objects.filter(
                organization_id=organization_id,
                provider__in=get_git_providers(),
                data__isnull=False,
            )
            .prefetch_related("provider")
            .all()
        )

    def parse_webhooks(self, connections):
        # We could parse all files in WebhookRequest, but it's slower since it's all organizations
        integrations = []
        for connection in connections:
            provider = connection.provider
            integration = get_git_provider_integration(provider)
            if provider == GitHubIntegration().provider:
                for installation_id in connection.data.get("installation_ids", []):
                    parse_str = f": {installation_id}, "
                    integrations.append((integration, parse_str))
            elif provider == AzureDevOpsIntegration().provider:
                parse_str = connection.data.get("base_url")
                if parse_str:
                    integrations.append((integration, parse_str))

        pull_requests = {}
        for integration, parse_str in integrations:
            output = subprocess.run(
                [
                    "fgrep",
                    "-rl",
                    f'"{parse_str}"',
                    os.path.abspath(settings.WEBHOOK_DATA_DIRECTORY),
                ],
                text=True,
                capture_output=True,
            )
            file_paths = output.stdout.splitlines() if output.stdout else []

            for file_path in file_paths:
                try:
                    _, payload = self.read_webhook_data(file_path)
                    data = integration().parse_pull_request_data(payload)
                    if data.repo_external_id and data.pr_number:
                        if data.repo_external_id not in pull_requests:
                            pull_requests[data.repo_external_id] = []

                        pull_requests[data.repo_external_id].append(data.pr_number)
                except Exception:
                    continue

        return pull_requests

    def read_webhook_data(self, json_file_path):
        with open(json_file_path) as file:
            data = json.load(file)

        headers = data.get("headers", {})
        payload = data.get("payload", {})

        return headers, payload
