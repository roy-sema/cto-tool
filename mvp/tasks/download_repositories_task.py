import json
import logging
import os
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from compass.integrations.apis.base_rest_api import GitInstallationDoesNotExist
from compass.integrations.integrations import (
    GitBaseIntegration,
    GitRepositoryData,
    GitServerBusyException,
    GitServerDisconnectException,
    get_git_provider_integration,
    get_git_providers,
)
from mvp.models import (
    DataProviderConnection,
    DataProviderProject,
    Organization,
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
)
from mvp.services.email_service import EmailService
from mvp.utils import (
    retry_on_exceptions,
    run_command_subprocess,
    shred_path,
    traceback_on_debug,
)

logger = logging.getLogger(__name__)


class ReferenceIsNotATreeException(Exception):
    # https://support.circleci.com/hc/en-us/articles/23781921297947-Understanding-the-fatal-reference-is-not-a-tree-Error-in-Git
    pass


class CheckoutRepositoryException(Exception):
    pass


class DownloadRepositoriesTask:
    GIT_CLONE_ERROR_MAP = {
        "The server is currently busy": GitServerBusyException,
        "disconnect": GitServerDisconnectException,
        "RPC failed": GitServerDisconnectException,
        "GnuTLS recv error": GitServerDisconnectException,
        "early EOF": GitServerDisconnectException,
    }

    HISTORIC_ANALYSIS_INTERVAL = 7  # days
    HISTORIC_ANALYSIS_NUM_COMMITS = 4  # commits

    REFERENCE_IS_NOT_A_TREE_ERROR = "fatal: reference is not a tree"

    def run(self, organization_id=None, repository_name=None, force=False):
        connections = self.get_connections(organization_id)
        if not connections:
            raise Exception(f"There are no connections for organization {organization_id}")

        organizations = self.get_organizations_from_connections(connections)
        for organization in organizations:
            try:
                self.process_organization(
                    organization["organization"],
                    organization["connections"],
                    repository_name=repository_name,
                    force=force,
                )
            except Exception:
                logger.exception(
                    "Failed to process organization", extra={"organization": organization["organization"].name}
                )

    def process_organization(self, organization, connections, repository_name=None, force=False):
        if self.organization_reached_max_scans(organization):
            logger.info(
                f"Reached maximum number of {organization.analysis_max_scans} scans for organization {organization.name}"
            )
            return

        repositories = []
        for connection in connections:
            repositories.extend(self.get_connection_repositories(connection))

        if not repositories:
            logger.info(f"No repositories found for organization {organization.name}")
            return

        logger.info(f"Processing organization {organization.name}")

        self.write_organization_config_file(organization)

        # Give priority to repositories analyzed previously (to avoid users connecting/disconnecting repositories),
        # but don't exceed the maximum number of repositories in any case (in case it was decreased)
        max_repos = organization.analysis_max_repositories
        analyzed_repos = set(self.get_analyzed_repositories_external_ids(organization))
        sorted_repositories = sorted(
            repositories,
            key=lambda repo: repo[0].id in analyzed_repos,
            reverse=True,
        )

        # First we fetch all repositories and add them to the database.
        # This allows having them available for PRs sooner.
        instances = []
        for index, (repository_data, integration) in enumerate(sorted_repositories):
            if repository_name and repository_name != repository_data.name:
                continue

            repository, commit = self.create_repository_commit(repository_data, organization, integration, force=force)
            if not repository:
                continue

            # Prioritize new commits over historic commits
            if commit:
                instances.append((repository_data, repository, commit, integration))
            else:
                historic_commits = self.create_historic_commits(repository_data, repository, organization, integration)
                for commit in historic_commits:
                    instances.append((repository_data, repository, commit, integration))

            if max_repos and index + 1 >= max_repos:
                logger.info(
                    f"Reached maximum number of repositories ({max_repos}) for organization {organization.name}"
                )
                break

        if not instances:
            logger.warning(f"No repositories found for organization {organization.name}")
            return

        # doing this here to avoid sending it when no repositories are found
        if not organization.first_email_sent:
            delivered = EmailService().send_analysis_started_email(organization)
            if delivered:
                organization.first_email_sent = True
                organization.save()

        # Then, we download each repository's code
        for repository_data, repository, commit, integration in instances:
            success = self.download_repository_commit(
                repository_data, organization, repository, commit, integration, force=force
            )
            if success:
                self.write_commit_config_file(commit, {"previous_analysis_path": repository.last_analysis_file})
                self.update_repository_last_commit(repository, commit)

    def get_connection_repositories(self, connection: DataProviderConnection):
        integration = get_git_provider_integration(connection.provider)
        if not integration:
            return []

        logger.info(f"Fetching repositories with provider {connection.provider}")

        try:
            return integration.get_connected_repositories_with_integration(connection)
        except GitInstallationDoesNotExist:
            # Intentionally preventing sentry from grouping those
            logger.exception(
                f"Git installation does not exist for {connection.organization.name} with provider {connection.provider}."
                f" Contact Product Team (Matt) to tell the user to re-connect the provider.",
                extra={"organization": connection.organization.name, "provider": connection.provider},
            )
            return []

    def create_repository_commit(
        self,
        repository: GitRepositoryData,
        organization: Organization,
        integration: GitBaseIntegration,
        force=False,
    ):
        if integration.is_empty_repository(repository):
            logger.info(f"Skipping '{repository.name}' repository - it's empty, provider: {integration.provider}")
            return None, None

        db_repository = self.get_repository(repository.id, organization, integration)

        # In case a commit gets stuck in pending status for more than one day
        yesterday = datetime.now() - timedelta(days=1)
        cutoff_date = timezone.make_aware(yesterday.replace(hour=0, minute=0, second=0, microsecond=0))

        if not force and db_repository and db_repository.has_pending_commits(exclude_prs=True, cutoff_date=cutoff_date):
            logger.info(f"Skipping '{repository.name}' repository - pending commits, provider: {integration.provider}")
            return None, None

        last_commit = integration.get_repository_last_commit(repository)
        if not last_commit:
            logger.info(f"Skipping '{repository.name}' repository - no commits, provider: {integration.provider}")
            return None, None

        db_repository = self.get_or_update_repository(organization, repository, integration)
        if not db_repository:
            logger.info(f"Skipping '{repository.name}' repository. Data provider not found")
            return None, None

        if not force and db_repository and db_repository.last_commit_sha == last_commit.sha:
            logger.info(f"Skipping '{repository.name}' repository - no new commits, provider: {integration.provider}")
            return db_repository, None

        db_commit = self.get_or_create_commit(db_repository, last_commit.sha, last_commit.date)

        return db_repository, db_commit

    def create_historic_commits(
        self,
        repository: GitRepositoryData,
        db_repository: Repository,
        organization: Organization,
        integration: GitBaseIntegration,
    ):
        if not organization.analysis_historic_enabled:
            logger.info(
                f"Skipping historic analysis for '{repository.name}' - disabled, provider: {integration.provider}"
            )
            return []

        if db_repository.analysis_historic_done:
            logger.info(
                f"Skipping historic analysis for '{repository.name}' - already done, provider: {integration.provider}"
            )
            return []

        interval = self.HISTORIC_ANALYSIS_INTERVAL
        num_commits = self.HISTORIC_ANALYSIS_NUM_COMMITS
        first_analyzed_commit = (
            RepositoryCommit.objects.filter(
                repository=db_repository,
                status=RepositoryCommitStatusChoices.ANALYZED,
                pull_requests__isnull=True,
            )
            .order_by("date_time")
            .values_list("date_time", flat=True)
            .first()
        )

        # Wait until we get the first analyzed commit to avoid analyzing historic before that
        if not first_analyzed_commit:
            logger.info(
                f"Skipping historic analysis for '{repository.name}' - no analyzed commits found :: {integration.WEBHOOK_ACTION_OPENED}"
            )
            return []

        dates = []
        for i in range(num_commits):
            dates.append(first_analyzed_commit - timedelta(days=interval * i))

        db_commits = []
        for date in dates:
            logger.info(f"Creating historic commit for '{repository.name}' - {date}")
            commit = integration.get_repository_commit_by_date(repository, date)

            if not commit:
                break

            db_commits.append(self.get_or_create_commit(db_repository, commit.sha, commit.date))

        db_repository.analysis_historic_done = True
        db_repository.save()

        return db_commits

    def download_repository_commit(
        self,
        repository_data: GitRepositoryData,
        organization: Organization,
        repository: Repository,
        commit: RepositoryCommit,
        integration: GitBaseIntegration,
        force=False,
    ):
        os.umask(0o002)
        org_directory = organization.get_download_directory()
        os.makedirs(org_directory, exist_ok=True)

        download_directory = commit.get_download_directory()
        if os.path.exists(download_directory):
            if force:
                self.delete_repository_from_disk(download_directory)
            else:
                logger.info(
                    f"Commit '{commit.sha}' already downloaded, skipping download, provider: {integration.provider}"
                )
                return False

        logger.info(f"Downloading commit '{commit.sha}' for '{repository.name}', provider: '{integration.provider}'")

        git_url = integration.get_repository_git_url(repository_data)
        if not git_url:
            logger.warning(
                "Could not find download link for repository",
                extra={
                    "repository": repository.name,
                    "provider": integration.provider,
                    "repository_data": repository_data,
                },
            )
            return False

        try:
            downloaded = self.download_commit(repository, commit, git_url, download_directory)
            if not downloaded:
                self.mark_commit_failed(commit)
                return False

            commit.analysis_file = f"{download_directory}.csv"
            commit.save()
        except ReferenceIsNotATreeException:
            logger.warning(
                f"Deleting commit as it no longer exists",
                {"organization": repository.organization, "repository": repository.name, "sha": commit.sha},
            )
            commit.delete()
            return False

        return True

    def download_commit(
        self,
        repository: Repository,
        commit: RepositoryCommit,
        git_url: str,
        download_directory: str,
    ):
        os.makedirs(download_directory, exist_ok=True)

        logger.info(f"Downloading '{repository.name}' repository - SHA: {commit.sha}")

        cloned = self.clone_repository(git_url, commit.sha, download_directory)
        if not cloned:
            logger.error(
                "Failed to download repository",
                extra={"repository": repository.name, "organization": repository.organization.name, "sha": commit.sha},
            )
            return False

        logger.info(f"Downloaded '{repository.name}' repository - SHA: {commit.sha}")

        return True

    def update_repository_last_commit(self, repository: Repository, commit: RepositoryCommit):
        repository.last_analysis_file = commit.analysis_file
        repository.last_commit_sha = commit.sha
        repository.save()

    def mark_commit_failed(self, commit: RepositoryCommit):
        commit.status = RepositoryCommitStatusChoices.FAILURE
        commit.save()

    def get_analyzed_repositories_external_ids(self, organization):
        return Repository.objects.filter(
            organization=organization,
            provider__in=get_git_providers(),
            last_analysis_file__isnull=False,
        ).values_list("external_id", flat=True)

    def clone_repository(self, url, ref, folder):
        lock_file = None
        try:
            lock_file = self.write_downloading_lock_file(folder)
            self._clone_repository(url, folder)
            self._setup_sparse_checkout(folder)
            self._checkout_repository(ref, folder)
            os.remove(lock_file)
            return True
        except ReferenceIsNotATreeException:
            if lock_file:
                os.remove(lock_file)
            # Raising here again so error is handled in download_repository_commit()
            raise
        except Exception:
            if lock_file:
                os.remove(lock_file)

            logger.exception(
                "Failed to clone repository",
                extra={"repository": folder, "url": url, "ref": ref},
            )

        return False

    @retry_on_exceptions(max_retries=5, delay=30)
    def _clone_repository(self, url, folder):
        success, error = run_command_subprocess(["git", "clone", url, folder])
        if not success:
            # move to avoid error "fatal: destination path already exists and is not an empty directory."
            timestamp = str(datetime.now().strftime("%Y%m%d%H%M%S"))
            error_folder = f"{folder}_error_{timestamp}_{uuid.uuid4()}"
            os.rename(folder, error_folder)

            error_str = error.lower()
            for text, exception in self.GIT_CLONE_ERROR_MAP.items():
                if text.lower() in error_str:
                    raise exception(error)

            raise ValueError(f"Failed to clone repository")

    def _setup_sparse_checkout(self, folder: str) -> None:
        """Configure sparse checkout to include only relevant files from the given Git ref.

        This improves performance when working with large repositories by excluding
        unnecessary or bulky files (e.g., media, binaries, models) based on file extensions.
        """
        excluded_patterns = {
            ".7z",
            ".aac",
            ".accdb",
            ".avi",
            ".bin",
            ".bmp",
            ".bz2",
            ".ckpt",
            ".class",
            ".crt",
            ".dat",
            ".db",
            ".der",
            ".dll",
            ".doc",
            ".docx",
            ".dylib",
            ".exe",
            ".fbx",
            ".feather",
            ".flac",
            ".flv",
            ".gif",
            ".glb",
            ".gltf",
            ".gz",
            ".h5",
            ".hdf5",
            ".heic",
            ".ico",
            ".img",
            ".iso",
            ".joblib",
            ".jpeg",
            ".jpg",
            ".key",
            ".m4a",
            ".mdb",
            ".mkv",
            ".mov",
            ".mp3",
            ".mp4",
            ".msgpack",
            ".npy",
            ".npz",
            ".obj",
            ".ogg",
            ".onnx",
            ".otf",
            ".p12",
            ".parquet",
            ".pb",
            ".pdf",
            ".pem",
            ".pfx",
            ".pkl",
            ".png",
            ".ppt",
            ".pptx",
            ".pt",
            ".pyc",
            ".pyo",
            ".rar",
            ".so",
            ".sqlite",
            ".sqlite3",
            ".stl",
            ".svg",
            ".tar",
            ".tflite",
            ".tiff",
            ".ttf",
            ".vdi",
            ".vmdk",
            ".wav",
            ".webm",
            ".webp",
            ".wmv",
            ".woff",
            ".woff2",
            ".xls",
            ".xlsx",
            ".xz",
            ".zip",
        }

        patterns = ["**/*", *[f"!**/*{p}" for p in excluded_patterns]]

        stdin_data = ("\n".join(patterns) + "\n").encode()

        run_command_subprocess(
            ["git", "sparse-checkout", "set", "--no-cone", "--stdin"],
            stdin=stdin_data,
            cwd=folder,
        )

    @retry_on_exceptions(delay=2, exceptions=(CheckoutRepositoryException,))
    def _checkout_repository(self, ref, folder):
        success, error = run_command_subprocess(["git", "checkout", ref], cwd=folder)
        if not success:
            if self.REFERENCE_IS_NOT_A_TREE_ERROR in error:
                raise ReferenceIsNotATreeException

            raise CheckoutRepositoryException(f"Failed to checkout repository: {error}")

    def get_connections(self, organization_id=None) -> QuerySet[DataProviderConnection]:
        qs = DataProviderConnection.objects.filter(
            provider__in=get_git_providers(), data__isnull=False
        ).prefetch_related("organization")

        if organization_id:
            qs = qs.filter(organization__id=organization_id)

        return qs.all()

    def get_organizations_from_connections(self, connections: QuerySet[DataProviderConnection]):
        organizations = {}
        for connection in connections:
            if not connection.is_connected():
                logger.info(f"Skipping provider {connection.provider} - not connected")
                continue
            if connection.organization.id not in organizations:
                organizations[connection.organization.id] = {
                    "organization": connection.organization,
                    "connections": [connection],
                }
            else:
                organizations[connection.organization.id]["connections"].append(connection)

        return organizations.values()

    def get_repository(self, external_id, organization, integration):
        try:
            return Repository.objects.get(
                organization=organization,
                provider=integration.provider,
                external_id=external_id,
            )
        except Repository.DoesNotExist:
            return None

    def _extract_branch_from_provider_meta(self, provider_name: str, meta: dict):
        if provider_name == "GitHub":
            return meta.get("default_branch")
        if provider_name == "BitBucket":
            return meta.get("mainbranch", {}).get("name")
        if provider_name == "AzureDevOps":
            default_branch = meta.get("default_branch")
            if not default_branch:
                return None
            parts = default_branch.split("/")
            if len(parts) > 2:
                return "/".join(parts[2:])
            return parts[-1] if parts else None
        raise ValueError(f"Default branch extraction not implemented for provider: {provider_name}")

    def get_or_update_repository(self, organization, repo: GitRepositoryData, integration: GitBaseIntegration):
        try:
            data_provider_project = DataProviderProject.objects.get(
                organization=organization,
                provider=integration.provider,
                external_id=repo.id,
            )
        except DataProviderProject.DoesNotExist:
            logger.exception(
                "Data provider project does not exist.",
                extra={
                    "provider": integration.provider,
                    "organization": organization.name,
                    "repo": repo.name,
                },
            )
            return None

        try:
            default_branch_name = self._extract_branch_from_provider_meta(
                integration.provider.name, data_provider_project.meta
            )
        except Exception:
            logger.exception(
                "Error extracting default branch from provider metadata",
                extra={
                    "provider": integration.provider,
                    "organization": organization.name,
                    "repo": repo.name,
                },
            )
            default_branch_name = None

        repository, created = Repository.objects.get_or_create(
            organization=organization,
            provider=integration.provider,
            external_id=repo.id,
            defaults={
                "owner": repo.owner,
                "name": repo.name,
                "external_data": repo.store_data,
                "default_branch_name": default_branch_name,
            },
        )

        if not created and (
            repository.owner != repo.owner
            or repository.name != repo.name
            or repository.external_data != repo.store_data
        ):
            repository.owner = repo.owner
            repository.name = repo.name
            repository.external_data = repo.store_data
            repository.save()

        if not created and default_branch_name and repository.default_branch_name != default_branch_name:
            repository.default_branch_name = default_branch_name
            repository.save()

        return repository

    def get_or_create_commit(self, repository, sha, date_time):
        commit, created = RepositoryCommit.objects.get_or_create(
            repository=repository, sha=sha, defaults={"date_time": date_time}
        )
        return commit

    def write_commit_config_file(self, commit, data):
        download_directory = commit.get_download_directory()
        os.makedirs(download_directory, exist_ok=True)

        # TODO: we should use this path instead of metadata to avoid writing in the git folder
        config_path = f"{download_directory}.config.json"

        try:
            with open(config_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            # In case of error, proceed. Only side effect is analyzing more data
            traceback_on_debug()
            logger.warning(
                f"Failed to write config file for commit",
                extra={
                    "repository": commit.repository.name,
                    "organization": commit.repository.organization.name,
                    "sha": commit.sha,
                    "error": str(e),
                },
            )

    def write_organization_config_file(self, organization):
        directory = organization.get_download_directory()
        os.makedirs(directory, exist_ok=True)

        config_path = os.path.join(directory, "config.json")
        data = {
            "max_repositories": organization.analysis_max_repositories,
            "max_lines_per_repository": organization.analysis_max_lines_per_repository,
        }
        try:
            with open(config_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            # In case of error, proceed. Only side effect is processing more data
            traceback_on_debug()
            logger.warning(
                f"Failed to write organization config file",
                extra={
                    "organization": organization.name,
                    "directory": directory,
                    "error": str(e),
                },
            )

    def organization_reached_max_scans(self, organization):
        if not organization.analysis_max_scans:
            return False

        return (
            Repository.objects.annotate(
                analyzed_commit_count=Count(
                    "repositorycommit",
                    filter=Q(repositorycommit__status=RepositoryCommitStatusChoices.ANALYZED),
                )
            )
            .filter(
                organization=organization,
                analyzed_commit_count__gt=organization.analysis_max_scans,
            )
            .exists()
        )

    def delete_repository_from_disk(self, repo_path):
        if settings.TESTING:
            return

        logger.info(f"Deleting repository from disk {repo_path}")

        try:
            shred_path(repo_path)
            logger.info(f"Deleted repository from disk {repo_path}")

        except Exception:
            logger.exception("Failed to delete repository from disk", extra={"repo_path": repo_path})

    def write_downloading_lock_file(self, folder):
        lock_file = f"{folder}.downloading"
        open(lock_file, "w").close()
        return lock_file
