import csv
import io
import logging
import os

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify

from mvp.models import (
    CodeGenerationLabelChoices,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
    RepositoryFileChunk,
    RepositoryFileChunkBlame,
)

logger = logging.getLogger(__name__)


class ExportGBOMTask:
    RANGE_COLUMNS = ["start", "end", "label", "author", "commit_sha", "commit_date"]
    RANGE_DELIMITER = "|"

    CSV_HEADERS = [
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
        "ranges__" + RANGE_DELIMITER.join(RANGE_COLUMNS),
        "code_hash",
    ]
    GENERATE_MAX_TIME = 3600
    UNGROUPED_STR = "Ungrouped"

    def get_gbom(self, organization):
        filename = self.get_gbom_filename(organization)
        content = self.get_gbom_content(organization)
        return filename, content

    def get_gbom_filename(self, organization):
        org_slug = self.get_org_slug(organization)
        date_slug = self.get_date_slug()
        return f"gbom-{org_slug}-{date_slug}.csv"

    def get_gbom_content(self, organization):
        gbom = self.read_precomputed_gbom(organization)
        return gbom or self.generate_precomputed_gbom(organization)

    def generate_precomputed_gbom(self, organization, force=False):
        if not force and self.is_generating(organization):
            return None

        logger.info(f"Generating precomputed GBOM for {organization.name}...")
        self.write_generating_file(organization)
        content = self.create_gbom(organization)
        self.write_precomputed_gbom(organization, content)
        self.delete_generating_file(organization)
        logger.info(f"Generated precomputed GBOM for {organization.name}")

        return content

    def get_precomputed_gbom_file_path(self, organization):
        filename = f"{organization.public_id()}.csv"
        return os.path.join(settings.GBOM_PRECOMPUTED_DIRECTORY, filename)

    def get_generating_file_path(self, organization):
        filename = self.get_precomputed_gbom_file_path(organization)
        return filename.replace(".csv", ".generating.csv")

    def is_generating(self, organization):
        file_path = self.get_generating_file_path(organization)
        return os.path.exists(file_path) and self.is_generating_file_recent(file_path)

    def is_generating_file_recent(self, file_path):
        return (
            timezone.now() - timezone.make_aware(timezone.datetime.fromtimestamp(os.path.getmtime(file_path)))
        ).seconds < self.GENERATE_MAX_TIME

    def write_generating_file(self, organization):
        file_path = self.get_generating_file_path(organization)
        self.write_file(file_path, "")

    def delete_generating_file(self, organization):
        file_path = self.get_generating_file_path(organization)
        if os.path.exists(file_path):
            os.remove(file_path)

    def read_precomputed_gbom(self, organization):
        file_path = self.get_precomputed_gbom_file_path(organization)
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r") as file:
            return file.read()

    def write_precomputed_gbom(self, organization, content):
        file_path = self.get_precomputed_gbom_file_path(organization)
        self.write_file(file_path, content)

    def write_file(self, file_path, content):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as file:
            file.write(content)

    def delete_precomputed_gbom(self, organization):
        file_path = self.get_precomputed_gbom_file_path(organization)
        if os.path.exists(file_path):
            os.remove(file_path)

    def create_gbom(self, organization):
        output = io.StringIO()

        writer = csv.writer(output)
        writer.writerow(self.CSV_HEADERS)
        self.add_rows(organization, writer)
        return output.getvalue()

    def add_rows(self, organization, writer):
        shas = self.get_last_commits_shas(organization)
        chunks = self.get_chunks(organization, shas)
        label_dict = dict(CodeGenerationLabelChoices.choices)
        commit_data = self.get_chunks_commit_data(organization, shas)

        for chunk in chunks:
            if self.is_not_evaluated_chunk(chunk):
                continue

            commit = commit_data.get(chunk["id"], {})
            writer.writerow(self.format_chunk(chunk, label_dict, commit))

    def is_not_evaluated_chunk(self, chunk):
        return chunk["code_generation_label"] == CodeGenerationLabelChoices.NOT_EVALUATED

    def format_chunk(self, chunk, label_dict, commit_data):
        committers = commit_data.get("committers", [])
        first_committer = committers[0] if committers else ""
        last_date = commit_data.get("last_date", chunk["commit_date"])
        last_sha = commit_data.get("last_sha", chunk["commit_sha"])
        ranges = self.format_ranges(commit_data, label_dict)
        lines = self.count_ranges_lines(chunk, commit_data)
        labels = CodeGenerationLabelChoices

        return [
            chunk["group_name"] or self.UNGROUPED_STR,
            self.get_repository_full_name(chunk),
            chunk["file_path"],
            chunk["code_line_start"],
            chunk["code_line_end"],
            chunk["code_num_lines"],
            lines[labels.HUMAN],
            lines[labels.AI],
            lines[labels.BLENDED],
            last_sha,
            last_date,
            chunk["file_language"],
            first_committer,
            ", ".join(committers),
            ranges,
            chunk["code_hash"],
        ]

    def format_ranges(self, commit_data, label_dict):
        return "\n".join(
            self.RANGE_DELIMITER.join(
                [
                    str(blame["code_line_start"]),
                    str(blame["code_line_end"]),
                    label_dict[blame["code_generation_label"]],
                    blame["author_name"],
                    blame["sha"],
                    str(blame["date_time"]),
                ]
            )
            for blame in commit_data.get("blame", [])
        )

    def count_ranges_lines(self, chunk, commit_data):
        lines_count = {
            CodeGenerationLabelChoices.HUMAN: 0,
            CodeGenerationLabelChoices.AI: 0,
            CodeGenerationLabelChoices.BLENDED: 0,
        }

        chunk_label = chunk["code_generation_label"]
        if chunk_label != CodeGenerationLabelChoices.BLENDED:
            lines_count[chunk_label] = chunk["code_num_lines"]
            return lines_count

        for blame in commit_data.get("blame", []):
            code_line_start = blame["code_line_start"]
            code_line_end = blame["code_line_end"]
            label = blame["code_generation_label"]

            if label in lines_count:
                lines_count[label] += code_line_end - code_line_start + 1

        return lines_count

    def get_org_slug(self, organization):
        return slugify(organization.name)

    def get_date_slug(self):
        return timezone.now().strftime("%Y-%m-%d")

    def get_last_commits_shas(self, organization):
        return (
            RepositoryCommit.objects.filter(
                repository__organization=organization,
                status=RepositoryCommitStatusChoices.ANALYZED,
                pull_requests__isnull=True,
            )
            .order_by("repository", "-date_time")
            .distinct("repository")
            .values_list("sha", flat=True)
        )

    def get_chunks(self, organization, shas):
        return (
            RepositoryFileChunk.objects.filter(
                file__commit__repository__organization=organization,
                file__commit__sha__in=shas,
            )
            .prefetch_related(
                "file",
                "file__commit",
                "file__commit__repository",
                "file__commit__repository__group",
            )
            .annotate(
                file_path=F("file__file_path"),
                file_language=F("file__language"),
                repository_owner=F("file__commit__repository__owner"),
                repository_name=F("file__commit__repository__name"),
                commit_sha=F("file__commit__sha"),
                commit_date=F("file__commit__date_time"),
                group_name=F("file__commit__repository__group__name"),
            )
            .values(
                "id",
                "file_path",
                "file_language",
                "name",
                "code_line_start",
                "code_line_end",
                "code_num_lines",
                "code_generation_label",
                "repository_owner",
                "repository_name",
                "commit_sha",
                "commit_date",
                "group_name",
                "code_hash",
            )
        )

    def get_repository_full_name(self, data):
        return f"{data['repository_owner']}/{data['repository_name']}"

    def get_chunks_commit_data(self, organization, shas):
        chunks_blame = (
            RepositoryFileChunkBlame.objects.filter(
                chunk__file__commit__repository__organization=organization,
                chunk__file__commit__sha__in=shas,
            )
            .prefetch_related("author", "author__linked_author")
            .order_by("date_time")
            .values(
                "chunk_id",
                "author__name",
                "author__linked_author__name",
                "sha",
                "date_time",
                "code_line_start",
                "code_line_end",
                "code_generation_label",
            )
        )

        chunks = {}
        for chunk_blame in chunks_blame:
            chunk = chunks.setdefault(
                chunk_blame["chunk_id"],
                {"committers": [], "last_date": None, "last_sha": None, "blame": []},
            )
            author_name = (
                chunk_blame["author__name"]
                if not chunk_blame["author__linked_author__name"]
                else chunk_blame["author__linked_author__name"]
            )
            if author_name not in chunk["committers"]:
                chunk["committers"].append(author_name)

            chunk["last_date"] = chunk_blame["date_time"]
            chunk["last_sha"] = chunk_blame["sha"]

            chunk_blame["author_name"] = author_name
            chunk["blame"].append(chunk_blame)

        return chunks
