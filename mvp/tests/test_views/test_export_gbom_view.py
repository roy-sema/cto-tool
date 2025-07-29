import csv
import io
from datetime import datetime, timedelta

from django.contrib.auth.models import Group
from django.utils import timezone

from compass.integrations.integrations import GitHubIntegration
from mvp.models import (
    Author,
    CodeGenerationLabelChoices,
    CustomUser,
    Organization,
    Repository,
    RepositoryAuthor,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
    RepositoryFile,
    RepositoryFileChunk,
    RepositoryFileChunkBlame,
    RepositoryFileLanguageChoices,
    RepositoryGroup,
    RepositoryGroupCategoryChoices,
    Rule,
)
from mvp.tasks import ExportGBOMTask

from .base_view_test import BaseViewTestCase


class ExportGBOMViewTests(BaseViewTestCase):
    def setUp(self):
        self.credentials = {
            "email": "testuser@domain.com",
            "password": "testpass456",
        }

        self.organization = Organization.objects.create(name="TestOrg")
        self.user = CustomUser.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

        owner_group = Group.objects.get(name="Owner")
        owner_group.user_set.add(self.user)
        self.user.organizations.add(self.organization)

        self.repository = Repository.objects.create(
            organization=self.organization,
            provider=GitHubIntegration().provider,
            external_id="xyz987",
            name="test_repo",
            owner="test_owner",
            code_num_lines=1000,
            code_ai_num_lines=250,
            code_ai_blended_num_lines=100,
            code_ai_pure_num_lines=150,
            code_ai_percentage=25,
            code_ai_blended_percentage=10,
            code_ai_pure_percentage=15,
            last_analysis_num_files=10,
        )
        self.commit_old = RepositoryCommit.objects.create(
            repository=self.repository,
            sha="abc123456789",
            date_time=timezone.make_aware(datetime.utcnow()),
            status=RepositoryCommitStatusChoices.ANALYZED,
        )
        self.commit_current = RepositoryCommit.objects.create(
            repository=self.repository,
            sha="def123456789",
            date_time=timezone.make_aware(datetime.utcnow()),
            status=RepositoryCommitStatusChoices.ANALYZED,
        )
        self.file_old = RepositoryFile.objects.create(
            commit=self.commit_old,
            file_path="test/path_old.py",
            language=RepositoryFileLanguageChoices.PYTHON,
        )
        self.file_current = RepositoryFile.objects.create(
            commit=self.commit_current,
            file_path="test/path.py",
            language=RepositoryFileLanguageChoices.PYTHON,
            code_num_lines=100,
            code_ai_num_lines=25,
            code_ai_blended_num_lines=10,
            code_ai_pure_num_lines=15,
        )
        # make sure NotEvaluated is not included in GBOM
        self.file_not_evaluated = RepositoryFile.objects.create(
            commit=self.commit_current,
            file_path="test/image.png",
            language=RepositoryFileLanguageChoices.UNKNOWN,
            not_evaluated=True,
        )
        self.chunk_old = RepositoryFileChunk.objects.create(
            file=self.file_old,
            name="run",
            code_line_start=1,
            code_line_end=100,
            code_num_lines=100,
            code_generation_score=0.9,
            code_generation_label=CodeGenerationLabelChoices.AI,
        )
        self.chunks = [
            RepositoryFileChunk.objects.create(
                file=self.file_current,
                name="main",
                code_line_start=1,
                code_line_end=10,
                code_num_lines=10,
                code_generation_score=0.9,
                code_generation_label=CodeGenerationLabelChoices.AI,
            ),
            RepositoryFileChunk.objects.create(
                file=self.file_current,
                name="main",
                code_line_start=21,
                code_line_end=50,
                code_num_lines=30,
                code_generation_score=0.9,
                code_generation_label=CodeGenerationLabelChoices.BLENDED,
            ),
        ]
        # make sure NotEvaluated is not included in GBOM
        self.chunk_not_evaluated = RepositoryFileChunk.objects.create(
            file=self.file_current,
            name="main",
            code_line_start=1,
            code_line_end=5,
            code_num_lines=5,
            code_generation_score=1,
            code_generation_label=CodeGenerationLabelChoices.NOT_EVALUATED,
        )
        self.repository.last_commit_sha = self.commit_current.sha
        self.repository.save()

        self.author = Author.objects.create(
            organization=self.organization,
            provider=GitHubIntegration().provider,
            external_id=123,
            name="TestDeveloper",
        )
        self.repository_author = RepositoryAuthor.objects.create(
            repository=self.repository,
            author=self.author,
            code_num_lines=100,
            code_ai_num_lines=25,
            code_ai_blended_num_lines=10,
            code_ai_pure_num_lines=15,
            code_ai_percentage=25,
            code_ai_blended_percentage=10,
            code_ai_pure_percentage=15,
        )

        self.blames = [
            [
                RepositoryFileChunkBlame.objects.create(
                    chunk=self.chunks[0],
                    author=self.author,
                    sha=self.commit_current.sha,
                    date_time=timezone.make_aware(datetime.utcnow()),
                    code_line_start=1,
                    code_line_end=5,
                    code_generation_label=CodeGenerationLabelChoices.AI,
                ),
                RepositoryFileChunkBlame.objects.create(
                    chunk=self.chunks[0],
                    author=self.author,
                    sha=self.commit_current.sha,
                    date_time=timezone.make_aware(datetime.utcnow() + timedelta(seconds=1)),
                    code_line_start=6,
                    code_line_end=10,
                    code_generation_label=CodeGenerationLabelChoices.AI,
                ),
            ],
            [
                RepositoryFileChunkBlame.objects.create(
                    chunk=self.chunks[1],
                    author=self.author,
                    sha=self.commit_current.sha,
                    date_time=timezone.make_aware(datetime.utcnow() + timedelta(seconds=2)),
                    code_line_start=21,
                    code_line_end=25,
                    code_generation_label=CodeGenerationLabelChoices.HUMAN,
                ),
                RepositoryFileChunkBlame.objects.create(
                    chunk=self.chunks[1],
                    author=self.author,
                    sha=self.commit_current.sha,
                    date_time=timezone.make_aware(datetime.utcnow() + timedelta(seconds=3)),
                    code_line_start=26,
                    code_line_end=50,
                    code_generation_label=CodeGenerationLabelChoices.BLENDED,
                ),
            ],
        ]

        self.chunk_old_blame = RepositoryFileChunkBlame.objects.create(
            chunk=self.chunk_old,
            author=self.author,
            sha=self.commit_old.sha,
            date_time=timezone.make_aware(datetime.utcnow()),
            code_line_start=1,
            code_line_end=10,
            code_generation_label=CodeGenerationLabelChoices.AI,
        )

        self.repository_group = RepositoryGroup.objects.create(
            organization=self.organization,
            name="TestGroup",
            usage_category=RepositoryGroupCategoryChoices.PRODUCTION,
        )
        self.rules = []
        self.rules.append(Rule.objects.create(name="TestRule1"))
        self.rules.append(Rule.objects.create(name="TestRule2"))
        self.repository_group.rules.set(self.rules)

        self.grouped_repositories = []

        for num in range(4):
            self.grouped_repositories.append(
                Repository.objects.create(
                    organization=self.organization,
                    provider=GitHubIntegration().provider,
                    external_id=f"grouped_repo_{num}",
                    name=f"grouped_repo_{num}",
                    owner="grouped_owner",
                    code_num_lines=1000,
                    code_ai_num_lines=250,
                    code_ai_blended_num_lines=100,
                    code_ai_pure_num_lines=150,
                    code_ai_percentage=25,
                    code_ai_blended_percentage=10,
                    code_ai_pure_percentage=15,
                    last_analysis_num_files=10,
                    group=self.repository_group,
                )
            )

        ExportGBOMTask().generate_precomputed_gbom(self.organization, force=True)

    def login(self):
        self.client.login(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

    def assert_csv_content(self, csv_content, headers, rows):
        num_lines = self.count_rows(csv_content)
        self.assertEqual(num_lines, len(rows) + 1)

        self.assertIn(self.format_row_to_csv(headers), csv_content)

        for row in rows:
            self.assertIn(self.format_row_to_csv(row), csv_content)

    def count_rows(self, csv_content):
        reader = csv.reader(io.StringIO(csv_content))
        return sum(1 for row in reader)

    def format_row_to_csv(self, row):
        return ",".join(row) + "\n"

    def get_expected_csv_file(self, date):
        return {
            "filename": f"gbom-testorg-{date}.csv",
            "headers": [
                "repository_group",
                "repository",
                "file_path",
                "start_line",
                "end_line",
                "num_lines",
                "not_genai_lines",
                "pure_ai_lines",
                "blended_lines",
                "commit_sha",
                "commit_date",
                "language",
                "earliest_committer",
                "all_committers",
                "ranges__" + ExportGBOMTask.RANGE_DELIMITER.join(ExportGBOMTask.RANGE_COLUMNS),
                "code_hash",
            ],
            "rows": [
                self.get_expected_row(
                    chunk,
                    self.blames[index],
                )
                for index, chunk in enumerate(self.chunks)
            ],
        }

    def get_expected_row(self, chunk, blames):
        first_blame = blames[0]
        last_blame = blames[-1]

        line_counts = {
            CodeGenerationLabelChoices.HUMAN: 0,
            CodeGenerationLabelChoices.AI: 0,
            CodeGenerationLabelChoices.BLENDED: 0,
        }

        for blame in blames:
            line_counts[blame.code_generation_label] += blame.code_line_end - blame.code_line_start + 1

        return [
            (self.repository.group.name if self.repository.group else "Ungrouped"),
            self.repository.full_name(),
            self.file_current.file_path,
            chunk.code_line_start,
            chunk.code_line_end,
            chunk.code_num_lines,
            line_counts[CodeGenerationLabelChoices.HUMAN],
            line_counts[CodeGenerationLabelChoices.AI],
            line_counts[CodeGenerationLabelChoices.BLENDED],
            last_blame.sha,
            last_blame.date_time,
            self.file_current.language,
            first_blame.author.name,
            first_blame.author.name,
            self.blames2ranges(blames),
            chunk.code_hash,
        ]

    def blames2ranges(self, blames):
        return "\n".join(
            ExportGBOMTask.RANGE_DELIMITER.join(
                [
                    str(blame.code_line_start),
                    str(blame.code_line_end),
                    blame.get_code_generation_label_display(),
                    blame.author.name,
                    blame.sha,
                    str(blame.date_time),
                ]
            )
            for blame in blames
        )

    def escape_rows(self, rows):
        return [[self.escape_cell(cell) for cell in row] for row in rows]

    def escape_cell(self, cell):
        if cell is None:
            return ""

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([str(cell)])
        return output.getvalue().strip()
