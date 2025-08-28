import json
import logging
import os
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import IntegrityError
from django.utils import timezone

from compass.integrations.integrations import (
    get_git_provider_integration,
    get_git_providers,
)
from mvp.models import (
    Author,
    AuthorStat,
    CodeGenerationLabelChoices,
    DataProviderConnection,
    Organization,
    Repository,
    RepositoryAuthor,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
    RepositoryFile,
    RepositoryFileChunk,
    RepositoryFileChunkBlame,
    RepositoryFileLanguageChoices,
)
from mvp.services import FuzzyMatchingService, GroupsAICodeService
from mvp.services.email_service import EmailService
from mvp.tasks import ExportGBOMTask
from mvp.utils import process_csv_file

logger = logging.getLogger(__name__)


class ImportAIEngineDataTask:
    CSV_DELIMITER = ","

    LABEL_MAP = {
        settings.AI_CODE_SCORE_LABEL_AI: CodeGenerationLabelChoices.AI,
        settings.AI_CODE_SCORE_LABEL_BLENDED: CodeGenerationLabelChoices.BLENDED,
        settings.AI_CODE_SCORE_LABEL_HUMAN: CodeGenerationLabelChoices.HUMAN,
        settings.AI_CODE_SCORE_LABEL_NOT_EVALUATED: CodeGenerationLabelChoices.NOT_EVALUATED,
    }

    def __init__(self):
        self._authors: dict[str, RepositoryAuthor] = {}
        self._files = {}
        self._attestations = {}
        self._author_stats: dict[str, AuthorStat] = {}

        self.gbom = ExportGBOMTask()

        self.commit: RepositoryCommit | None = None
        self.repository: Repository | None = None

        self.author_name_max_length = Author._meta.get_field("name").max_length
        self.author_login_max_length = Author._meta.get_field("login").max_length

    def run(self, organization_id=None, repository_id=None, commit_sha=None, erase=False):
        repositories = self.get_repositories(organization_id, repository_id)

        if not repositories:
            logger.info("No repositories found. Do they have external data set?")
            return

        organizations = {}
        for repository in repositories:
            try:
                updated = self.process_repository(repository, commit_sha=commit_sha, erase=erase)
                if updated:
                    organizations[repository.organization.pk] = repository.organization
            except Exception:
                logger.exception(
                    "Failed to process repository",
                    extra={"repository_id": repository.id, "repository": repository.name},
                )

        for organization in organizations.values():
            self.update_organization(organization)
            self.notify_first_analysis_complete(organization)

    def update_organization(self, organization):
        FuzzyMatchingService.set_organization_linked_authors(organization)
        GroupsAICodeService(organization).update_all()
        self.gbom.generate_precomputed_gbom(organization, force=True)

    def process_repository(self, repository, erase=False, commit_sha=None):
        # Manually imported repositories don't use a git provider.
        # Check create_external_repositories command for more info.
        if not repository.is_manual_imported() and not self.is_repository_connected(repository):
            logger.warning(
                f"Repository '{repository.name}' is not connected anymore. User may have disconnected it or deleted the repository."
            )
            return False

        # first import data from the last or given commit
        sha = commit_sha or repository.last_commit_sha
        commit = self.get_commit_by_sha(repository, sha)

        updated = self.process_commit(repository, commit, erase=erase) if commit else False

        self.import_pending_commits(repository, sha, erase=erase)

        if not commit:
            logger.warning(
                f"Commit not found for repository",
                extra={
                    "organization": repository.organization.name,
                    "repository": repository.name,
                    "commit_sha": sha,
                    "csv": repository.last_analysis_file,
                },
            )
            return False

        if updated:
            logger.info(f"Imported '{repository.name}' analysis results.")

        return updated

    def import_pending_commits(self, repository, last_commit_sha, erase=False):
        commits = RepositoryCommit.objects.filter(
            repository=repository,
            status=RepositoryCommitStatusChoices.PENDING,
        ).exclude(sha=last_commit_sha)

        if commits:
            logger.info(f"Found {len(commits)} pending commits for '{repository.name}'")

        for commit in commits:
            imported = self.process_commit(repository, commit, erase=erase, update_repository=False)
            if imported:
                logger.info(f"Imported pending commit '{commit.sha}' for '{repository.name}'")

    def get_commit_by_sha(self, repository, sha):
        try:
            return RepositoryCommit.objects.get(repository=repository, sha=sha, pull_requests__isnull=True)
        except RepositoryCommit.DoesNotExist:
            return None

    def process_commit(self, repository, commit, pull_request=None, erase=False, update_repository=True):
        logger.info(f"Processing commit '{commit.sha}' for repository '{repository.name}'")
        if commit.status == RepositoryCommitStatusChoices.ANALYZED and not erase:
            logger.info("Analysis already exists")
            return False

        csv_path = commit.analysis_file
        if not csv_path or not os.path.exists(csv_path):
            logger.warning(f"CSV file {csv_path} does not exist")
            return False

        logger.info(f"Processing CSV '{csv_path}'")

        self._authors = {}
        self._files = {}
        self._attestations = self.get_attestation_map(repository)
        self.commit = commit
        self.repository = repository
        self._author_stats = {}

        try:
            logger.info("Resetting data")
            commit.reset()
            self.delete_previous_files(commit)
            commit.analysis_metadata = self.load_metadata(commit.metadata_analysis_file())

            csv_authors_path = csv_path.replace(".csv", ".authors.csv")
            if os.path.exists(csv_authors_path):
                logger.info("Importing authors")
                process_csv_file(
                    csv_authors_path,
                    self.process_author_row,
                    delimiter=self.CSV_DELIMITER,
                )

            logger.info("Importing files")
            process_csv_file(csv_path, self.process_file_row, delimiter=self.CSV_DELIMITER)

            self.update_files_analysis(self._files)
            self.update_commit_analysis(commit, self._files)

            if pull_request:
                self.set_not_evaluated_files_from_metadata(commit, self._files)
                self.update_pull_request_analysis(pull_request, commit, self._files)
            elif update_repository:
                self.update_repository_analysis(repository, commit)
                self.update_repository_authors_analysis(repository, self._authors)

                # Now that we have the new data, we can delete the previous GBOM
                self.gbom.delete_precomputed_gbom(repository.organization)

            AuthorStat.objects.bulk_create(
                self._author_stats.values(),
                unique_fields=AuthorStat._meta.unique_together[0],
                update_conflicts=True,
                update_fields=[
                    "code_num_lines",
                    "code_ai_num_lines",
                    "code_ai_blended_num_lines",
                    "code_ai_pure_num_lines",
                    "code_not_ai_num_lines",
                ],
            )
            return True

        except Exception:
            logger.exception(
                "Could not process CSV",
                extra={"repository": repository.name, "sha": commit.sha, "csv": csv_path},
            )
            commit.status = RepositoryCommitStatusChoices.FAILURE
            commit.save()
            return False

    def update_files_analysis(self, files):
        for file in files.values():
            self.set_ai_percentages(file)
            file.save()

    def update_pull_request_analysis(self, pull_request, commit, files):
        pull_request.code_num_lines = commit.code_num_lines
        pull_request.code_ai_num_lines = commit.code_ai_num_lines
        pull_request.code_ai_blended_num_lines = commit.code_ai_blended_num_lines
        pull_request.code_ai_pure_num_lines = commit.code_ai_pure_num_lines

        self.set_ai_percentages(pull_request)
        pull_request.analysis_num_files = len(files)
        pull_request.not_evaluated_num_files = commit.not_evaluated_num_files
        pull_request.not_evaluated_num_lines = commit.not_evaluated_num_lines

        pull_request.head_commit_sha = commit.sha
        pull_request.save()

    def update_commit_analysis(self, commit, files):
        count_per_lang = {}
        for file in files.values():
            lang = file.language
            count_per_lang[lang] = count_per_lang.get(lang, 0) + 1

            self.increment_commit_code_lines(commit, file)

        self.set_ai_percentages(commit)
        commit.analysis_num_files = len(files)
        commit.status = RepositoryCommitStatusChoices.ANALYZED

        commit.languages = count_per_lang
        commit.save()

    def update_repository_analysis(self, repository, commit):
        repository.languages = commit.languages
        self.copy_commit_stats_to_repository(commit, repository)
        repository.save()

    def copy_commit_stats_to_repository(self, commit, repository):
        repository.code_num_lines = commit.code_num_lines
        repository.code_ai_num_lines = commit.code_ai_num_lines
        repository.code_ai_blended_num_lines = commit.code_ai_blended_num_lines
        repository.code_ai_pure_num_lines = commit.code_ai_pure_num_lines
        repository.code_ai_percentage = commit.code_ai_percentage
        repository.code_ai_blended_percentage = commit.code_ai_blended_percentage
        repository.code_ai_pure_percentage = commit.code_ai_pure_percentage
        repository.last_analysis_num_files = commit.analysis_num_files
        repository.not_evaluated_num_files = commit.not_evaluated_num_files
        repository.not_evaluated_num_lines = commit.not_evaluated_num_lines

    def set_ai_percentages(self, instance):
        code_num_lines = instance.code_num_lines

        code_ai_num_lines = instance.code_ai_num_lines
        instance.code_ai_percentage = (
            code_ai_num_lines / code_num_lines * 100 if code_num_lines and code_ai_num_lines else 0
        )

        code_ai_blended_num_lines = instance.code_ai_blended_num_lines
        instance.code_ai_blended_percentage = (
            (code_ai_blended_num_lines / code_num_lines * 100) if code_num_lines and code_ai_blended_num_lines else 0
        )

        code_ai_pure_num_lines = instance.code_ai_pure_num_lines
        instance.code_ai_pure_percentage = (
            (code_ai_pure_num_lines / code_num_lines * 100) if code_num_lines and code_ai_pure_num_lines else 0
        )

    def process_file_row(self, row):
        file_path = row["file_path"]
        language = row.get("language", RepositoryFileLanguageChoices.UNKNOWN)
        label = self.normalize_label(row["label"])
        model_label = row["model_label"]
        num_lines = int(row["num_lines"])

        is_not_evaluated = label == CodeGenerationLabelChoices.NOT_EVALUATED
        if is_not_evaluated and not num_lines:
            # we used to include NotEvaluated files in GBOM, let's keep this to have a record of them just in case
            self.record_not_evaluated_file(file_path, language)
            return

        if file_path not in self._files:
            self._files[file_path] = RepositoryFile.objects.create(
                commit=self.commit,
                file_path=file_path,
                language=language,
            )

        file = self._files[file_path]

        score = float(row["score"])
        start_line = int(row["start_line"])
        end_line = int(row["end_line"])
        code_hash = None if is_not_evaluated else row.get("code_hash")
        ranges = row["ranges__start:end:label:author:commit_sha:commit_timestamp"]

        chunk_blame, code_ai_num_lines = self.process_ranges(ranges)

        attestation = self._attestations.get(code_hash) if code_hash else None

        chunk = RepositoryFileChunk.objects.create(
            file=file,
            code_hash=code_hash,
            # Avoiding storing function names for now
            name="",  # row["function_name"],
            code_line_start=start_line,
            code_line_end=end_line,
            code_num_lines=num_lines,
            code_ai_num_lines=code_ai_num_lines,
            code_generation_score=score,
            code_generation_label=label,
            code_generation_model_label=model_label,
            attestation=attestation,
        )

        RepositoryFileChunkBlame.objects.bulk_create(
            [RepositoryFileChunkBlame(chunk=chunk, **blame) for blame in chunk_blame]
        )

        if is_not_evaluated:
            file.chunks_not_evaluated += 1
            self.commit.not_evaluated_num_lines += num_lines
            return

        if attestation:
            label = attestation.label

        self.increment_file_chunk_lines(file, label, num_lines, code_ai_num_lines)

    def increment_file_chunk_lines(self, file, label, num_lines, num_ai_lines):
        file.code_num_lines += num_lines

        if label == CodeGenerationLabelChoices.HUMAN:
            file.chunks_human += 1
            return

        file.code_ai_num_lines += num_ai_lines

        if label == CodeGenerationLabelChoices.BLENDED:
            file.chunks_ai_blended += 1
            file.code_ai_blended_num_lines += num_ai_lines
        elif label == CodeGenerationLabelChoices.AI:
            file.chunks_ai_pure += 1
            file.code_ai_pure_num_lines += num_ai_lines

    def increment_commit_code_lines(self, commit, file):
        commit.code_num_lines += file.code_num_lines
        commit.code_ai_num_lines += file.code_ai_num_lines
        commit.code_ai_blended_num_lines += file.code_ai_blended_num_lines
        commit.code_ai_pure_num_lines += file.code_ai_pure_num_lines

    def normalize_label(self, model_label):
        return self.LABEL_MAP[model_label]

    def process_ranges(self, raw):
        ai_num_lines = 0
        chunk_blame = []
        for row in raw.split("\n"):
            if not row:
                continue

            start, end, _label, author_id, commit_sha, commit_timestamp = self.parse_range_row(row)

            label = self.normalize_label(_label)
            num_lines = int(end) - int(start) + 1

            author = self._authors.get(author_id)
            if not author:
                logger.warning(
                    "Author not found in authors CSV", extra={"author_id": author_id, "commit_sha": commit_sha}
                )

                author = self.get_or_create_author(author_id, author_id, author_id, None)
                self._authors[author_id] = author

            author.code_num_lines += num_lines
            chunk_blame.append(
                {
                    "author": author.author,
                    "sha": commit_sha,
                    "date_time": timezone.make_aware(datetime.fromtimestamp(int(commit_timestamp))),
                    "code_line_start": start,
                    "code_line_end": end,
                    "code_generation_label": label,
                }
            )

            author_stat = self._author_stats.get(
                author_id,
                AuthorStat(
                    author=author.author,
                    commit=self.commit,
                    repository=self.repository,
                    time=self.commit.date_time,
                ),
            )

            author_stat.code_num_lines += num_lines
            # TODO remove saving in author since everything should be un author_stat
            if label != CodeGenerationLabelChoices.HUMAN:
                ai_num_lines += num_lines

                author.code_ai_num_lines += num_lines
                author_stat.code_ai_num_lines += num_lines

                if label == CodeGenerationLabelChoices.BLENDED:
                    author.code_ai_blended_num_lines += num_lines
                    author_stat.code_ai_blended_num_lines += num_lines

                else:
                    author.code_ai_pure_num_lines += num_lines
                    author_stat.code_ai_pure_num_lines += num_lines
            else:
                author_stat.code_not_ai_num_lines += num_lines

            self._author_stats[author_id] = author_stat

        return chunk_blame, ai_num_lines

    def parse_range_row(self, row):
        try:
            return json.loads(row)
        except json.JSONDecodeError:
            # old version of the CSV used a different format
            return row.split(":")

    def get_repositories(self, organization_id, repository_id):
        qs = Repository.objects.filter(provider__in=get_git_providers(), external_data__isnull=False)

        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        if repository_id:
            qs = qs.filter(id=repository_id)

        return qs.all()

    def delete_previous_files(self, commit):
        RepositoryFile.objects.filter(commit=commit).delete()

    def record_not_evaluated_file(self, file_path, language):
        try:
            _, created = RepositoryFile.objects.get_or_create(
                commit=self.commit,
                file_path=file_path,
                defaults={"language": language, "not_evaluated": True},
            )
            if created:
                self.commit.not_evaluated_num_files += 1
        except IntegrityError:
            # in case the CSV contains duplicate rows, we only want to create the file once
            pass

    def process_author_row(self, row):
        external_id = row["external_id"]
        email = row["email"] or None
        login = row["login"] or None

        # name can't be empty, use what's available
        name = row["name"] or login or email or external_id

        author = self.get_or_create_author(external_id, name, email, login)
        self._authors[external_id] = author

    def get_or_create_author(self, external_id: str, name: str, email: str, login: str | None) -> RepositoryAuthor:
        name, email, login = self.clean_author_data(name, email, login)
        author, created = Author.objects.get_or_create(
            organization=self.repository.organization,
            provider=self.repository.provider,
            external_id=external_id,
            defaults={"name": name, "email": email, "login": login},
        )
        if (not created and author.name != name) or author.email != email or author.login != login:
            author.name = name
            author.email = email
            author.login = login
            author.save()

        instance, created = RepositoryAuthor.objects.get_or_create(
            repository=self.repository,
            author=author,
        )
        instance.reset_ai_fields()

        return instance

    def clean_author_data(self, name, email, login):
        name = name[: self.author_name_max_length] if name else None
        login = login[: self.author_login_max_length] if login else None
        email = email if email and self.is_valid_email(email) else None

        return name, email, login

    def is_valid_email(self, email):
        try:
            EmailValidator()(email)
            return True
        except ValidationError:
            return False

    def update_repository_authors_analysis(self, repository, authors):
        for author in authors.values():
            # values may have changed, so we need to recalculate percentages always
            self.set_ai_percentages(author)

        RepositoryAuthor.objects.bulk_update(
            authors.values(),
            [
                "code_num_lines",
                "code_ai_num_lines",
                "code_ai_blended_num_lines",
                "code_ai_pure_num_lines",
                "code_ai_percentage",
                "code_ai_blended_percentage",
                "code_ai_pure_percentage",
            ],
        )

        # as authors are based on git blame, it's possible that some of them disappear over time
        # set not found authors stats to 0
        RepositoryAuthor.objects.filter(repository=repository).exclude(
            id__in=[author.id for author in authors.values()]
        ).update(
            code_ai_num_lines=0,
            code_num_lines=0,
            code_ai_blended_num_lines=0,
            code_ai_pure_num_lines=0,
            code_ai_percentage=0,
            code_ai_blended_percentage=0,
            code_ai_pure_percentage=0,
        )

    def notify_first_analysis_complete(self, organization: Organization):
        # TODO add another flag for first_import_email_sent and fix logic
        if not organization.first_analysis_done and organization.all_repos_analyzed():
            EmailService().send_import_done_email(organization)

            organization.first_analysis_done = True
            organization.save()

    def is_repository_connected(self, repository: Repository) -> bool:
        integration = get_git_provider_integration(repository.provider)
        if not integration:
            return False

        integration = integration()

        connection = DataProviderConnection.objects.filter(
            organization=repository.organization, provider=repository.provider
        ).first()

        if not connection or not integration.is_connection_connected(connection):
            return False

        return integration.is_repository_connected(repository)

    def set_not_evaluated_files_from_metadata(self, commit, evaluated_files):
        # AI Engine will not report non-source files
        # For PRs, we want to count all non-evaluated files, even non-source files
        commit.not_evaluated_num_files = 0

        metadata = self.load_metadata(commit.metadata_file())
        files = metadata.get("changed_files", {})
        for file in files:
            file_path = f"/{file['filename']}"
            if file_path not in evaluated_files:
                commit.not_evaluated_num_files += 1

    def load_metadata(self, metadata_path) -> dict:
        if not metadata_path or not os.path.exists(metadata_path):
            logger.warning(f"Failed to find metadata path: {metadata_path}")
            return {}

        try:
            with open(metadata_path) as file:
                return json.load(file)
        except Exception:
            logger.exception("Failed to read metadata file", extra={"metadata_path": metadata_path})
            return {}

    def get_attestation_map(self, repository):
        return {attestation.code_hash: attestation for attestation in repository.repositorycodeattestation_set.all()}
