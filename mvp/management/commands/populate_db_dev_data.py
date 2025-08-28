import glob
import json
import os
import random
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from api.tasks import RecalculateCommitAICompositionTask
from compass.dashboard.models import GitDiffContext
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
    get_git_providers,
)
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import (
    Author,
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
    RepositoryGroup,
    RepositoryGroupCategoryChoices,
    Rule,
    RuleCondition,
    RuleConditionCodeTypeChoices,
    RuleConditionModeChoices,
    RuleConditionOperatorChoices,
    RuleRiskChoices,
)
from mvp.services import ContextualizationService, GroupsAICodeService


def date_between(since, until):
    return timezone.make_aware(datetime.combine(Faker().date_between_dates(since, until), datetime.min.time()))


def random_chance(chance=0.5):
    return random.random() < chance


def random_text_choice(class_name):
    choices = [choice for choice, _ in class_name.choices]
    return random.choice(choices)


def replace_file_extension(file_path, new_extension):
    return os.path.splitext(file_path)[0] + f".{new_extension}"


def zero_fill(index, length=5):
    return str(index).zfill(length)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Populate the database with data to speed up development."

    CONTEXTUALIZATION_CATEGORIES = [
        "Bug fix",
        "Documentation",
        "Feature Enhancement",
        "New Feature",
        "Security",
        "Tech debt",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--authors_num",
            type=int,
            default=50,
            help="Number of authors to create.",
        )
        parser.add_argument(
            "--authors_attach_group_chance",
            type=float,
            default=0.8,
            help="Chance of authors attaching to a group.",
        )
        parser.add_argument(
            "--authors_groups_num",
            type=int,
            default=4,
            help="Number of author groups.",
        )

        parser.add_argument(
            "--contextualization_max_changes_per_repository",
            type=int,
            default=20,
            help="Maximum number of changes per repository.",
        )

        parser.add_argument(
            "--contextualization_num_projects",
            type=int,
            default=5,
            help="Number of projects.",
        )

        parser.add_argument(
            "--org_prefix",
            type=str,
            default="DevOrg_",
            help="Prefix for organization.",
        )

        parser.add_argument(
            "--repositories_num",
            type=int,
            default=30,
            help="Number of repositories to create.",
        )
        parser.add_argument(
            "--repository_commit_max_days_ago",
            type=int,
            default=30,
            help="Maximum days ago for repository commits.",
        )
        parser.add_argument(
            "--repository_attach_group_chance",
            type=float,
            default=0.8,
            help="Chance of repositories attaching to a group.",
        )
        parser.add_argument(
            "--repository_groups_num",
            type=int,
            default=5,
            help="Number of repository groups.",
        )
        parser.add_argument(
            "--repository_groups_max_rules",
            type=int,
            default=2,
            help="Maximum number of rules per repository.",
        )
        parser.add_argument(
            "--repository_max_commits",
            type=int,
            default=4,
            help="Maximum number of commits per repository.",
        )
        parser.add_argument(
            "--repository_max_files",
            type=int,
            default=1000,
            help="Maximum number of files per repository.",
        )
        parser.add_argument(
            "--repository_max_file_commits",
            type=int,
            default=10,
            help="Maximum number of commits per file.",
        )
        parser.add_argument(
            "--repository_max_file_lines",
            type=int,
            default=100,
            help="Maximum number of lines per file.",
        )
        parser.add_argument(
            "--repository_max_file_authors",
            type=int,
            default=10,
            help="Maximum number of authors per file.",
        )
        parser.add_argument(
            "--repository_min_file_authors",
            type=int,
            default=1,
            help="Minimum number of authors per file.",
        )
        parser.add_argument(
            "--repository_max_chunk_size",
            type=int,
            default=50,
            help="Maximum chunk size.",
        )
        parser.add_argument(
            "--repository_min_chunk_size",
            type=int,
            default=15,
            help="Minimum chunk size.",
        )
        parser.add_argument(
            "--repository_chunk_ai_chance",
            type=float,
            default=0.1,
            help="Chance of AI-generated chunks.",
        )
        parser.add_argument(
            "--repository_chunk_ai_pure_chance",
            type=float,
            default=0.3,
            help="Chance of purely AI-generated chunks.",
        )
        parser.add_argument(
            "--repository_chunk_max_commits",
            type=int,
            default=4,
            help="Maximum number of commits per chunk.",
        )
        parser.add_argument(
            "--repository_not_evaluated_chance",
            type=float,
            default=0.01,
            help="Chance of repository not being evaluated.",
        )

        parser.add_argument(
            "--rules_prefix",
            type=str,
            default="Rule_",
            help="Prefix for rules.",
        )
        parser.add_argument(
            "--rules_num",
            type=int,
            default=10,
            help="Number of rules.",
        )
        parser.add_argument(
            "--rules_apply_org_chance",
            type=float,
            default=0.3,
            help="Chance of rules applying to the organization.",
        )
        parser.add_argument(
            "--rules_max_conditions",
            type=int,
            default=3,
            help="Maximum number of conditions per rule.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.TESTING:
            self.stdout.write(self.style.ERROR("This command is intended for development purposes only."))
            return

        if not self.confirm():
            self.stdout.write(self.style.WARNING("Operation cancelled."))
            return

        self.config = options

        self.git_providers = get_git_providers()

        self.python_code = self.get_python_code()

        organization = self.populate_db()

        self.create_contextualization_data(organization)

        self.stdout.write(self.style.SUCCESS(f"Data populated to organization '{organization.name}'!"))

    def confirm(self):
        self.stdout.write(
            "This command adds a lot of data to the database for development. It is NOT intended for production."
        )

        self.stdout.write(self.style.WARNING("\nThis operation may be hard to reverse."))

        confirmation = input(f"Are you sure you want to generate the data? [y/N] ").lower()

        return confirmation == "y"

    def populate_db(self):
        organization = self.create_organization()

        self.create_connections(organization)
        rules = self.create_rules(organization)
        self.authors = self.create_authors(organization)

        repositories = self.create_repositories(organization)
        self.create_repository_authors(repositories)

        self.create_repository_groups(organization, repositories, rules)

        # Create pull requests
        # Create attestations
        # Create repository groups
        # Create developer groups
        # Calculate AI fields for RepositoryAuthors

        RecalculateCommitAICompositionTask().run(
            list(RepositoryCommit.objects.filter(repository__organization=organization)),
            force=True,
        )

        GroupsAICodeService(organization).update_all()

        return organization

    def create_organization(self):
        return Organization.objects.create(
            name=self.get_org_name(),
            status_check_enabled=True,
            onboarding_completed=True,
        )

    def get_org_name(self):
        organization_names = self.get_organization_names()

        index = 0
        while True:
            org_name = f"{self.config['org_prefix']}{zero_fill(index + 1)}"
            if org_name not in organization_names:
                return org_name

            index += 1

    def get_organization_names(self):
        return Organization.objects.only("name").values_list("name", flat=True)

    def create_connections(self, organization):
        self.stdout.write("Creating data provider connections...")
        for provider in self.git_providers:
            data = {}
            if provider == GitHubIntegration().provider:
                data = {"installation_ids": [123]}
            elif provider == AzureDevOpsIntegration().provider:
                data = {"base_url": "", "personal_access_token": ""}
            elif provider == BitBucketIntegration().provider:
                data = {"workspace": "", "access_key": "", "refresh_token": ""}

            DataProviderConnection.objects.create(
                organization=organization,
                provider=provider,
                data=data,
            )

    def create_rules(self, organization):
        self.stdout.write("Creating rules...")
        rules = Rule.objects.bulk_create(self.rule_generator(organization))

        for rule in rules:
            RuleCondition.objects.bulk_create(self.rule_condition_generator(rule))

        return rules

    def rule_generator(self, organization):
        for num in range(self.config["rules_num"]):
            yield Rule(
                name=f"{self.config['rules_prefix']}{zero_fill(num)}",
                condition_mode=random_text_choice(RuleConditionModeChoices),
                risk=random_text_choice(RuleRiskChoices),
                organization=organization,
                apply_organization=random_chance(self.config["rules_apply_org_chance"]),
            )

    def rule_condition_generator(self, rule):
        for _ in range(random.randint(1, self.config["rules_max_conditions"])):
            yield RuleCondition(
                rule=rule,
                code_type=random_text_choice(RuleConditionCodeTypeChoices),
                operator=random_text_choice(RuleConditionOperatorChoices),
                percentage=random.randint(0, 100),
            )

    def create_authors(self, organization):
        self.stdout.write("Creating authors...")

        return Author.objects.bulk_create(self.author_generator(organization))

    def author_generator(self, organization):
        fake = Faker()
        for _ in range(self.config["authors_num"]):
            yield Author(
                organization=organization,
                provider=random.choice(self.git_providers),
                external_id=fake.unique.uuid4(),
                name=fake.name(),
                email=fake.email(),
                login=fake.user_name(),
            )

    def create_repositories(self, organization):
        self.stdout.write("Creating repositories...")
        repositories = Repository.objects.bulk_create(self.repository_generator(organization))

        for repository in repositories:
            self.create_repository_commits(repository)

        return repositories

    def repository_generator(self, organization):
        fake = Faker()

        for _ in range(self.config["repositories_num"]):
            yield Repository(
                organization=organization,
                provider=random.choice(self.git_providers),
                external_id=fake.unique.uuid4(),
                owner=slugify(fake.company()),
                name=slugify(fake.company()),
            )

    def create_repository_commits(self, repository):
        self.stdout.write(f"Creating commits for repository '{repository.full_name()}'...")
        commits = RepositoryCommit.objects.bulk_create(self.commit_generator(repository))

        last_commit = None
        for commit in commits:
            if not last_commit or commit.date_time > last_commit.date_time:
                last_commit = commit

            self.create_files(commit)

        if last_commit:
            repository.last_commit_sha = last_commit.sha
            repository.last_analysis_file = last_commit.analysis_file
            repository.last_analysis_num_files = commit.analysis_num_files
            repository.save()

    def commit_generator(self, repository):
        fake = Faker()

        today = datetime.now()
        yesterday = today - timedelta(days=1)
        max_ago = today - timedelta(days=self.config["repository_commit_max_days_ago"])

        for _ in range(random.randint(1, self.config["repository_max_commits"])):
            yield RepositoryCommit(
                repository=repository,
                sha=fake.unique.sha1(),
                date_time=date_between(max_ago, yesterday),
                status=RepositoryCommitStatusChoices.ANALYZED,
                analysis_num_files=random.randint(1, self.config["repository_max_files"]),
            )

    def create_files(self, commit):
        self.stdout.write(f"Creating {commit.analysis_num_files} files for commit '{commit.sha}'...")
        files = RepositoryFile.objects.bulk_create(self.file_generator(commit))

        commit_folder = commit.get_download_directory()
        commit.analysis_file = f"{commit_folder}.csv"
        commit.save()

        self.stdout.write(f"Writing {commit.analysis_num_files} files to '{commit_folder}'...")
        self.write_files(commit_folder, files)

        self.stdout.write(f"Creating files chunks for commit '{commit.sha}'...")

        self.create_files_chunks(files)

    def file_generator(self, commit):
        fake = Faker()
        file_paths = set()

        for _ in range(commit.analysis_num_files):
            # Because the extension is replaced, fake uniqueness can be broken
            while True:
                file_path = replace_file_extension(fake.unique.file_path(), "py")
                if file_path not in file_paths:
                    file_paths.add(file_path)
                    break

            not_evaluated = random_chance(self.config["repository_not_evaluated_chance"])
            if not_evaluated:
                yield RepositoryFile(
                    commit=commit,
                    file_path=file_path,
                    not_evaluated=True,
                )
                continue

            yield RepositoryFile(
                commit=commit,
                file_path=file_path,
                code_num_lines=random.randint(1, self.config["repository_max_file_lines"]),
                language=random_text_choice(RepositoryFileLanguageChoices),
                not_evaluated=False,
            )

    def create_files_chunks(self, files):
        chunks = RepositoryFileChunk.objects.bulk_create(self.files_chunks_generator(files))

        # Not evauated files have no chunks
        if chunks:
            self.create_chunks_blames(chunks)

    def files_chunks_generator(self, files):
        fake = Faker()
        for file in files:
            start_line = 1
            while start_line <= file.code_num_lines:
                num_lines = random.randint(
                    self.config["repository_min_chunk_size"],
                    self.config["repository_max_chunk_size"],
                )
                end_line = start_line + num_lines - 1
                if end_line > file.code_num_lines:
                    end_line = file.code_num_lines
                    num_lines = file.code_num_lines - start_line + 1

                label = CodeGenerationLabelChoices.HUMAN
                model_label = CodeGenerationLabelChoices.HUMAN
                num_ai_lines = 0

                is_ai = random_chance(self.config["repository_chunk_ai_chance"])
                is_pure_ai = is_ai and (
                    file.code_num_lines == 1 or random_chance(self.config["repository_chunk_ai_pure_chance"])
                )

                if is_ai:
                    num_ai_lines = random.randint(1, num_lines)
                    label = CodeGenerationLabelChoices.AI if is_pure_ai else CodeGenerationLabelChoices.BLENDED
                    model_label = CodeGenerationLabelChoices.AI

                end_line = start_line + num_lines - 1

                yield RepositoryFileChunk(
                    file=file,
                    name="",
                    code_hash=fake.unique.sha256(),
                    code_line_start=start_line,
                    code_line_end=end_line,
                    code_num_lines=num_lines,
                    code_ai_num_lines=num_ai_lines,
                    code_generation_score=1,
                    code_generation_label=label,
                    code_generation_model_label=model_label,
                )

                start_line = end_line + 1

    def create_chunks_blames(self, chunks):
        RepositoryFileChunkBlame.objects.bulk_create(self.chunks_blames_generator(chunks))

    def chunks_blames_generator(self, chunks):
        previous_file = None
        file_authors = []
        file_commits = []

        # Get random dates and use them for commits as this is very slow
        commit_date = chunks[0].file.commit.date_time
        max_ago = commit_date - timedelta(days=self.config["repository_commit_max_days_ago"])
        dates = [date_between(max_ago, commit_date) for _ in range(self.config["repository_commit_max_days_ago"])]

        for chunk in chunks:
            if not previous_file or chunk.file != previous_file:
                fake = Faker()  # uniqueness by file
                file_authors = random.sample(
                    self.authors,
                    random.randint(
                        self.config["repository_min_file_authors"],
                        self.config["repository_max_file_authors"],
                    ),
                )
                previous_file = chunk.file
                file_commits = [
                    (
                        fake.unique.sha1(),
                        random.choice(dates),
                        random.choice(file_authors),
                    )
                    for _ in range(random.randint(1, self.config["repository_max_file_commits"]))
                ]

            is_pure = chunk.code_generation_label == CodeGenerationLabelChoices.AI
            num_commits = 1 if is_pure else random.randint(1, len(file_commits))
            chunk_commits = random.sample(file_commits, num_commits)
            lines_per_commit = chunk.code_num_lines // num_commits

            start_line = chunk.code_line_start
            for index, (sha, date_time, author) in enumerate(chunk_commits):
                is_last_commit = index == num_commits - 1
                end_line = start_line + lines_per_commit - 1 if not is_last_commit else chunk.code_line_end

                yield RepositoryFileChunkBlame(
                    chunk=chunk,
                    author=author,
                    sha=sha,
                    date_time=date_time,
                    code_line_start=start_line,
                    code_line_end=end_line,
                    code_generation_label=chunk.code_generation_label,
                )

                start_line = end_line + 1

    def create_repository_authors(self, repositories):
        self.stdout.write("Creating repository authors...")

        for repository in repositories:
            authors = Author.objects.filter(
                repositoryfilechunkblame__chunk__file__commit__repository=repository
            ).distinct()

            RepositoryAuthor.objects.bulk_create(self.repository_author_generator(repository, authors))

    def repository_author_generator(self, repository, authors):
        for author in authors:
            yield RepositoryAuthor(repository=repository, author=author)

    def create_repository_groups(self, organization, repositories, rules):
        self.stdout.write("Creating repository groups...")

        groups = RepositoryGroup.objects.bulk_create(self.repository_group_generator(organization))

        non_global_rules = [rule for rule in rules if not rule.apply_organization]
        num_max_rules = min(
            self.config["repository_groups_max_rules"],
            len(non_global_rules),
        )

        for group in groups:
            if not (num_rules := random.randint(0, num_max_rules)):
                continue

            group_rules = random.sample(non_global_rules, num_rules)
            group.rules.add(*group_rules)
            group.save()

        attach_repositories = random.sample(
            repositories,
            int(self.config["repository_attach_group_chance"] * len(repositories)),
        )

        for repository in attach_repositories:
            repository.repository_group.add(random.choice(groups))
            repository.save()

    def repository_group_generator(self, organization):
        fake = Faker()

        for _ in range(self.config["repository_groups_num"]):
            yield RepositoryGroup(
                organization=organization,
                name=fake.company(),
                usage_category=random_text_choice(RepositoryGroupCategoryChoices),
            )

    def get_python_code(self):
        commands_dir = os.path.dirname(os.path.abspath(__file__))
        python_files = glob.glob(os.path.join(commands_dir, "**", "*.py"), recursive=True)

        files = []
        for python_file in python_files:
            with open(python_file) as file:
                files.append(file.readlines())

        return files

    def write_files(self, folder, files):
        os.makedirs(folder, exist_ok=True)
        for file in files:
            file_path = os.path.join(folder, file.relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w") as f:
                lines = random.choice(self.python_code)
                file_lines = lines[: file.code_num_lines]
                while len(file_lines) < file.code_num_lines:
                    file_lines.append("# NOTE: Repeating to fill the file")
                    file_lines.extend(lines)

                file_lines = file_lines[: file.code_num_lines]

                f.writelines(file_lines)

    def create_contextualization_data(self, organization):
        # NOTE: at some point contextualization data should be stored in the DB

        repositories = organization.repository_set.all()

        by_repo = {}
        by_category = {}
        total = 0
        for repo in repositories:
            repo_id = repo.public_id()
            by_repo[repo_id] = {}
            remaining_changes = random.randint(0, self.config["contextualization_max_changes_per_repository"])
            for category in self.CONTEXTUALIZATION_CATEGORIES:
                if not remaining_changes:
                    break

                num_changes = random.randint(0, remaining_changes)
                if not num_changes:
                    continue

                by_repo[repo_id][category] = num_changes
                by_category[category] = by_category.get(category, 0) + num_changes
                total += num_changes
                remaining_changes -= num_changes

                for i in range(num_changes):
                    GitDiffContext.objects.create(
                        repository=repo,
                        sha=f"sha_{i}",
                        file_path=f"/path/to/file_{i}.py",
                        git_diff_hash=f"{random.getrandbits(256):064x}",
                        category=category,
                        summary="This is the summary",
                        maintenance_relevance="This is the maintenance relevance",
                        description_of_maintenance_relevance="This is the description of maintenance relevance",
                        impact_on_product="This is the impact on product",
                        purpose_of_change="This is the purpose of change",
                        time=timezone.now() - timedelta(days=random.randint(1, 14)),
                    )

        categories = {}
        for category, num_changes in by_category.items():
            category_slug = slugify(category).replace("-", "_")
            categories[category_slug] = {
                "examples": f"This is a example for {category}",
                "justification": f"This is the justification of {category}",
                "percentage": num_changes / total * 100,
            }

        justification_data = {
            "categories": categories,
            "maintenance_relevance": {},
            "summary": "This is the summary",
        }
        self.write_contextualization_json(
            organization,
            ContextualizationService.OUTPUT_FILENAME_JUSTIFICATION,
            justification_data,
        )

        num_projects = self.config["contextualization_num_projects"]
        percentages = []
        remaining = 100
        for index in range(num_projects):
            max_value = remaining - (num_projects - index - 1)
            percentages.append(random.randint(1, max_value))
            remaining -= percentages[-1]

        percentages[-1] += remaining

        projects_data = [
            {
                "changes": [
                    {
                        "name": f"Project {index + 1}",
                        "justification": f"This is the justification of Project {index + 1}",
                        "percentage": percentages[index],
                    }
                    for index in range(num_projects)
                ]
            }
        ]
        self.write_contextualization_json(
            organization,
            ContextualizationService.OUTPUT_FILENAME_PROJECTS,
            projects_data,
        )

    def write_contextualization_json(self, organization, filename, data):
        file_path = ContextualizationService.get_output_file_path(organization, filename)

        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)

        self.stdout.write(f"Writing contextualization '{filename}' data to '{file_path}'...")

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
