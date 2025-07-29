import json
import os
import subprocess
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import DataProvider, Organization, Repository, RepositoryCommit


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Creates an organization, moves given repositories to scan folder, adds repositories to the database, and prepares them for analysis. If the organization exists, repositories will be added to it."

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "org_name",
            type=str,
            help="The name of the organization to create.",
        )

        parser.add_argument(
            "repos_path",
            type=str,
            help="The folder where the repositories are stored (each repository in one folder).",
        )

    def handle(self, *args, **options):
        org_name = options.get("org_name").strip()
        repos_path = os.path.abspath(options.get("repos_path"))

        if not org_name:
            raise CommandError("Organization name can't be empty.")

        if not os.path.exists(repos_path):
            raise CommandError(f"Source path '{repos_path}' does not exist.")

        repositories = self.get_repositories_from_disk(repos_path)
        if not repositories:
            raise CommandError(f"No repositories found in '{repos_path}'.")

        if self.confirm(org_name, repositories):
            self.stdout.write("Creating repositories...")
            self.create(org_name, repositories)
        else:
            self.stdout.write(self.style.WARNING("Operation cancelled."))

    def create(self, org_name, repositories):
        org, created_org = Organization.objects.get_or_create(name=org_name)

        if created_org:
            self.stdout.write(self.style.SUCCESS(f"Organization '{org_name}' created successfully!"))

        org_directory = self.get_organization_directory(org)
        os.makedirs(org_directory, exist_ok=True)

        self.stdout.write(self.style.SUCCESS(f"Organization directory: {org_directory}"))

        created_repositories = 0
        for repo in repositories:
            repo_path = self.create_repository(org, repo)
            if not repo_path:
                continue

            created_repositories += 1

        # create this file so the autodiscovery script handles the analysis
        config_path = os.path.join(org_directory, "config.json")
        json.dump({}, open(config_path, "w"))

        os.makedirs(org_directory, exist_ok=True)

        if created_repositories:
            self.stdout.write(self.style.SUCCESS(f"Analysis and import will start automatically in a few minutes."))
        else:
            self.stdout.write(self.style.ERROR("No repositories created."))

    def create_repository(self, org, repo):
        repo_name = repo["name"]
        source_path = repo["source"]

        last_commit_sha = self.get_last_commit_sha(source_path)
        if not last_commit_sha:
            self.stdout.write(
                self.style.ERROR(
                    f"Could not get last commit SHA for {source_path}. Is this a git repository?\n"
                    f"Repository '{repo_name}' NOT created. Files not moved."
                )
            )
            return None

        target_path = self.get_repository_directory(org.public_id(), repo_name)

        if os.path.exists(target_path):
            self.stdout.write(
                self.style.ERROR(
                    f"Folder '{target_path}' already exists.Repository '{repo_name}' NOT created. Files not moved."
                )
            )
            return None

        os.makedirs(target_path, exist_ok=True)
        os.rename(source_path, target_path)

        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=target_path)

        last_analysis_file = f"{target_path}.csv"

        github = DataProvider.objects.get(name="GitHub")

        repo, created = Repository.objects.get_or_create(
            organization=org,
            provider=github,
            external_id=slugify(f"{org.name}-{repo_name}"),
            owner=org.name,
            name=repo_name,
            last_commit_sha=last_commit_sha,
            last_analysis_file=last_analysis_file,
            external_data={"manual": True},
        )

        yesterday = datetime.now(tz=timezone.utc) - timedelta(hours=24)

        RepositoryCommit.objects.get_or_create(
            repository=repo,
            sha=last_commit_sha,
            date_time=yesterday,
            analysis_file=last_analysis_file,
        )

        self.stdout.write(self.style.SUCCESS(f"Repository '{repo_name}' created successfully!"))

        return target_path

    def get_last_commit_sha(self, repo_path):
        return (
            (
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo_path,
                    stdout=subprocess.PIPE,
                )
            )
            .stdout.decode("utf-8")
            .strip()
        )

    def confirm(self, org_name, repositories):
        count = len(repositories)
        if self.exists_organization(org_name):
            message = f"Add {count} repositories to existing organization '{org_name}'?"
        else:
            message = f"Create organization '{org_name}' with {count} repositories?"

        message += "\nRepositories will be moved from source to target:\n"
        for repo in repositories:
            message += f"  - {repo['name']}:\n"
            message += f"    - Source: {repo['source']}\n"
            message += f"    - Target: {repo['target']}\n"

        self.stdout.write(message)
        self.stdout.write(self.style.WARNING("This operation is not reversible."))
        confirmation = input("Are you sure you want to proceed? [y/N] ").lower()

        return confirmation == "y"

    def exists_organization(self, org_name):
        return Organization.objects.filter(name=org_name).exists()

    def get_repositories_from_disk(self, repos_path):
        repositories = []
        for path in os.listdir(repos_path):
            source_path = os.path.join(repos_path, path)
            if not os.path.isdir(source_path):
                continue

            repo_name = os.path.basename(source_path)
            target_path = self.get_repository_directory("<org_id>", repo_name)

            repositories.append({"name": repo_name, "source": source_path, "target": target_path})

        return repositories

    def get_organization_directory(self, organization):
        return os.path.abspath(os.path.join(settings.AI_CODE_REPOSITORY_DIRECTORY, organization.public_id()))

    def get_repository_directory(self, org_public_id, repo_name):
        return os.path.abspath(
            os.path.join(
                settings.AI_CODE_REPOSITORY_DIRECTORY,
                org_public_id,
                repo_name,
                repo_name,
            )
        )
