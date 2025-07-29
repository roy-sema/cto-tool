import hashlib
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.contrib.auth.models import Group
from django.test import TransactionTestCase

from compass.contextualization.models import MessageFilter, SignificanceLevelChoices
from mvp.models import (
    CustomUser,
    DataProvider,
    DataProviderConnection,
    ModuleChoices,
    Organization,
    OrgRole,
    Repository,
    RepositoryCommit,
    RepositoryGroup,
)

logger = logging.getLogger(__name__)

CASSETTES_PATH = ".ci_cassettes"


class TestDailyPipelineE2E(TransactionTestCase):
    """
    End-to-end tests for daily pipeline execution.
    """

    def setUp(self):
        """
        Set up a test environment.
        """
        super().setUp()

        last_commit_sha = "last_commit_sha"

        groups = create_groups()

        custom_user = create_custom_user(groups)

        organization_github = create_organization(custom_user)
        org_id_hash = organization_github.public_id()
        self.organization_github_id = organization_github.id

        create_message_filter(custom_user, organization_github)

        provider = create_provider()

        create_data_provider_connection(custom_user, organization_github, provider)

        repository_group = create_repository_group(organization_github)

        repository = create_repository(organization_github, provider, last_commit_sha)
        repository_id_hash = repository.public_id()
        target_repo = create_target_repo(org_id_hash, repository_id_hash, last_commit_sha)

        repository.last_analysis_file = f"{target_repo}.csv"
        repository.group = repository_group
        repository.save()

        create_repository_commit(repository, target_repo, last_commit_sha)

        update_environment_variables()

    def run_daily_pipeline_with_jira_connection(self):
        """
        Test daily pipeline execution for organization with JIRA connection.
        """

        returncode, logs = run_pipeline_command_with_retry()

        # Assert a pipeline completed without critical errors
        # We expect some warnings but not fatal errors
        self.assertIn(
            returncode,
            [0, 1],
            f"Pipeline failed with return code {returncode}",
        )

        # Check that no critical error messages are present
        critical_errors = [
            "CRITICAL",
            "FATAL",
            "Exception:",
            "Traceback (most recent call last):",
        ]

        for error in critical_errors:
            self.assertNotIn(error, logs, f"Critical error found: {error}")

        # Verify daily message generation doesn't crash
        # (We're not asserting content, just that it runs without fatal errors)
        assert "contextualization completed" in logs.lower() or returncode == 0

    def test_daily_pipeline_without_jira_connection(self):
        """
        Test daily pipeline execution for an organization without JIRA connection.
        """

        # Run the pipeline command
        returncode, logs = run_pipeline_command_with_retry(org_id=self.organization_github_id)

        # Assert a pipeline completed without critical errors
        self.assertIn(
            returncode,
            [0, 1],
            f"Pipeline failed with return code {returncode}",
        )

        # Check that no critical error messages are present
        critical_errors = [
            "CRITICAL",
            "FATAL",
            "Exception:",
            "Traceback (most recent call last):",
        ]

        for error in critical_errors:
            self.assertNotIn(error, logs, f"Critical error found: {error}")

        # Verify daily message generation doesn't crash
        self.assertTrue(
            "Successfully generated" in logs and returncode == 0,
            f"Generation failed with code {returncode}",
        )


def hash_file(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_cassette_hashes(folder: Path) -> dict[str, str]:
    """
    Return a dictionary mapping filenames to their SHA-256 hash.
    Only includes .json files in the given folder.
    """
    return {file.name: hash_file(file) for file in folder.glob("*.json") if file.is_file()}


def run_pipeline_command_with_retry(org_id: int = 1) -> tuple[int, str]:
    env = os.environ.copy()

    original_hashes = get_cassette_hashes(Path(__file__).parent.parent / CASSETTES_PATH)

    returncode, logs = run_pipeline_command(org_id=org_id, env=env)
    cassettes_changed = delete_changed_cassette_files(original_hashes)

    if cassettes_changed:
        return run_pipeline_command(org_id=org_id, env=env)

    return returncode, logs


def delete_changed_cassette_files(original_hashes: dict[str, str]) -> bool:
    """Delete cassette files that changed based on hash comparison."""
    cwd = Path(__file__).parent.parent
    cassette_dir = cwd / CASSETTES_PATH
    updated_hashes = get_cassette_hashes(cassette_dir)

    changed = False
    for name, orig_hash in original_hashes.items():
        updated_hash = updated_hashes.get(name)
        if updated_hash and updated_hash != orig_hash:
            logger.info(f"Deleting changed cassette: {name}")
            (cassette_dir / name).unlink()
            changed = True

    return changed


def run_pipeline_command(
    org_id: int = 1,
    day_interval: int = 1,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """
    Run the daily pipeline command.
    """
    cmd = [
        "python3",
        "manage.py",
        "experiment_contextualization_script",
        "--orgid",
        str(org_id),
        "--by-group",
        "--day-interval",
        str(day_interval),
    ]

    full_log = []

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    ) as proc:
        for line in proc.stdout:
            logger.info(line.rstrip())
            full_log.append(line)
        proc.wait()

    return proc.returncode, "".join(full_log)


def update_environment_variables():
    """
    Setup test environment with all required variables.
    """
    os.environ.update(
        {
            "USE_HTTP_CALL_MOCKS": "True",
            "MOCKED_END_DATE": "2025-06-25",
            "AI_CODE_REPOSITORY_DIRECTORY": "test_repos",
            "GENAI_FEEDBACK_DIRECTORY": "test_gen_ai_feedback",
            "DJANGO_SETTINGS_MODULE": "cto_tool.settings",  # Ensure Django settings are loaded
            "RDS_DB_NAME": "test_sema",
            "CASSETTES_PATH": CASSETTES_PATH,
        }
    )


def create_target_repo(org_id_hash: str, repository_id_hash: str, last_commit_sha: str) -> Path:
    """
    Create the target repository path.
    """
    return Path(f"test_repos/{org_id_hash}/{repository_id_hash}/{last_commit_sha}").resolve()


def clone_repo(target_repo: Path) -> None:
    """
    Clone the repository to the test directory.
    """
    logger.info(f"Current working dir: {Path.cwd()}")
    logger.info(f".git exists: {(Path.cwd() / '.git').exists()}")
    logger.info(f"Git status: {subprocess.run(['git', 'status'], capture_output=True, text=True).stdout}")

    target_repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--no-checkout", ".", str(target_repo)],
        cwd=str(Path.cwd()),
        check=True,
    )
    subprocess.run(["git", "checkout", "HEAD"], cwd=str(target_repo), check=True)
    logger.info(f"Cloned Git repo into test directory: {target_repo}")


def create_test_repo(target_repo: Path) -> None:
    """
    Create a brand-new Git repository with a few commits.
    This is useful for tests that require a Git history without cloning an existing repo.
    """
    logger.info(f"Creating new Git repo at: {target_repo}")
    target_repo.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "--initial-branch=main"], cwd=str(target_repo), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(target_repo), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(target_repo),
        check=True,
    )

    for i in range(25):
        file_path = target_repo / f"file_{i}.txt"
        file_path.write_text(f"Test file {i}\n")

        subprocess.run(["git", "add", file_path.name], cwd=str(target_repo), check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Initial commit {i}"],
            cwd=str(target_repo),
            check=True,
        )

    logger.info(f"Created Git repo with commits at {target_repo}")


def create_organization(custom_user: CustomUser, name="Test") -> Organization:
    """
    Create an organization with all required fields.
    """
    organization = Organization.objects.create(
        name=name,
        num_developers=10,
        num_code_lines=1000,
        all_time_developers=10,
        contextualization_enabled=True,
        onboarding_completed=True,
        analysis_historic_enabled=True,
        analysis_max_lines_per_repository=10000,
        analysis_max_repositories=2,
        analysis_max_scans=1,
        first_commit_date=datetime.strptime("2020-01-01", "%Y-%m-%d").date(),
        avg_developer_cost=100000,
        avg_dev_annual_work_hours=1500,
        connection_issued_by=custom_user,
    )

    # Add a relationship for mvp_customuser_organizations
    organization.customuser_set.add(custom_user)

    return organization


def create_custom_user(groups: dict[str, Group]) -> CustomUser:
    """
    Create the main test user.
    """
    custom_user = CustomUser.objects.create_user(
        email="test@example.com",
        password="password",
        first_name="Ivan",
        last_name="Rykov",
        is_active=True,
    )

    # Add a relationship for mvp_customuser_groups
    custom_user.groups.add(groups[OrgRole.OWNER])

    return custom_user


def create_provider() -> DataProvider:
    """
    Create a GitHub data provider with modules matching local data.
    """
    return DataProvider.objects.create(
        name="GitHub",
        modules=[ModuleChoices.PROCESS, ModuleChoices.TEAM],
    )


def create_data_provider_connection(custom_user, organization, provider) -> DataProviderConnection:
    """
    Create a GitHub data provider connection with all required fields.
    """
    return DataProviderConnection.objects.create(
        organization=organization,
        provider=provider,
        connected_at=datetime.now(),
        connected_by=custom_user,
    )


def create_repository(organization, provider, last_commit_sha, name="test-repo") -> Repository:
    """
    Create the main repository.
    """
    return Repository.objects.create(
        name=name,
        organization=organization,
        provider=provider,
        external_id="external_id",
        owner="owner",
        analysis_historic_done=False,
        last_analysis_num_files=0,
        not_evaluated_num_files=0,
        not_evaluated_num_lines=0,
        default_branch_name="main",
        last_commit_sha=last_commit_sha,
    )


def create_repository_group(organization, name="test-repo-group") -> RepositoryGroup:
    """
    Create a repository group for the test organization.
    """
    return RepositoryGroup.objects.create(name=name, organization=organization)


def create_repository_commit(repository, target_repo, last_commit_sha) -> RepositoryCommit:
    """
    Create a repository commit matching local data.
    """
    return RepositoryCommit.objects.create(
        sha=last_commit_sha,
        analysis_file=f"{target_repo}.csv",
        repository=repository,
        date_time=datetime.strptime("2025-06-12 07:09:36", "%Y-%m-%d %H:%M:%S"),
        code_num_lines=0,
        code_ai_num_lines=0,
        code_ai_percentage=0.00,
        analysis_num_files=0,
        code_ai_blended_num_lines=0,
        code_ai_blended_percentage=0.00,
        code_ai_pure_num_lines=0,
        code_ai_pure_percentage=0.00,
        status="pending",
        not_evaluated_num_files=0,
        not_evaluated_num_lines=0,
        shredded=False,
    )


def create_message_filter(custom_user, organization) -> MessageFilter:
    """
    Create a Contextualization MessageFilter instance.
    """
    return MessageFilter.objects.create(
        day_interval=1,
        significance_levels=f"{','.join(SignificanceLevelChoices.labels)}",
        organization=organization,
        user=custom_user,
    )


def create_groups() -> dict[str, Group]:
    """
    Create auth groups required for the tests.
    """
    group_data = [
        {"name": OrgRole.DEVELOPER},
        {"name": OrgRole.ENGINEERING_LEADER},
        {"name": OrgRole.COMPLIANCE_LEADER},
        {"name": OrgRole.SETTINGS_EDITOR},
        {"name": OrgRole.OWNER},
    ]

    groups = {}
    for data in group_data:
        group, created = Group.objects.get_or_create(name=data["name"])
        group.save()
        groups[group.name] = group

    return groups
