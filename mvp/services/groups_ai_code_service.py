from mvp.models import Author, AuthorGroup, AuthorStat, RepositoryGroup
from mvp.utils import round_half_up


class GroupsAICodeService:
    def __init__(self, organization):
        self.organization = organization

    def update_all(self):
        self.update_repository_groups()
        self.update_author_groups()
        self.update_authors()

    def update_repository_groups(self, override_group: RepositoryGroup = None):
        groups = self.get_repository_groups()
        for group in groups:
            # to avoid having a change be overridden by the saving the group again (related to replica db setup)
            if override_group and group.id == override_group.id:
                group = override_group
            repositories = group.repository_set.all()
            self.set_group_ai_fields(group, repositories)
            group.save()

    def get_repository_groups(self):
        return RepositoryGroup.objects.filter(organization=self.organization).prefetch_related("repository_set")

    def update_author_groups(self, override_group: AuthorGroup = None):
        groups = self.get_author_groups()
        for group in groups:
            repo_authors = []
            # to avoid having a change be overridden by the saving the group again (related to replica db setup)
            if override_group and group.id == override_group.id:
                group = override_group
            for author in group.author_set.filter(linked_author__isnull=True):
                repo_authors.extend(list(author.repositoryauthor_set.all()))
                for linked_author in author.author_set.all():
                    repo_authors.extend(list(linked_author.repositoryauthor_set.all()))

            self.set_group_ai_fields(group, repo_authors)
            group.save()

    def get_author_groups(self):
        return AuthorGroup.objects.filter(organization=self.organization).prefetch_related(
            "author_set",
            "author_set__repositoryauthor_set",
            "author_set__author_set",
            "author_set__author_set__repositoryauthor_set",
        )

    def set_group_ai_fields(self, group, instances):
        ai_fields = self.calculate_ai_fields(instances)

        for field, value in ai_fields.items():
            setattr(group, field, value)

    def update_authors(self, override_author: Author = None):
        for author in self.get_authors():
            if override_author and author.id == override_author.id:
                author = override_author

            instances = list(author.repositoryauthor_set.all())
            for linked_author in author.author_set.all():
                instances.extend(list(linked_author.repositoryauthor_set.all()))

            ai_fields = self.calculate_ai_fields(instances)
            for field, value in ai_fields.items():
                setattr(author, field, value)
            author.save()

    def get_authors(self):
        return Author.objects.filter(organization=self.organization, linked_author__isnull=True).prefetch_related(
            "repositoryauthor_set",
            "author_set",
            "author_set__repositoryauthor_set",
        )

    def get_ungrouped_group(self):
        ungrouped_developers = Author.objects.filter(
            organization=self.organization,
            linked_author__isnull=True,
            group__isnull=True,
        )
        stats = AuthorStat.get_aggregated_authors_stats(author_ids=[dev.id for dev in ungrouped_developers])
        ungrouped = {
            "public_id": None,
            "name": "Ungrouped",
            "developers": [],
            "developers_count": ungrouped_developers.count(),
            "code_num_lines": stats["code_num_lines"],
            "rule_risk_list": [],
            "stats": stats,
        }
        return ungrouped

    @classmethod
    def calculate_ai_fields(cls, instances):
        num_lines = 0
        ai_num_lines = 0
        ai_pure_num_lines = 0
        ai_blended_num_lines = 0
        not_evaluated_num_files = 0
        not_evaluated_num_lines = 0
        for instance in instances:
            num_lines += instance.code_num_lines
            ai_num_lines += instance.code_ai_num_lines
            ai_pure_num_lines += instance.code_ai_pure_num_lines
            ai_blended_num_lines += instance.code_ai_blended_num_lines
            if hasattr(instance, "not_evaluated_num_files"):
                not_evaluated_num_files += instance.not_evaluated_num_files
                not_evaluated_num_lines += instance.not_evaluated_num_lines

        percentages = cls.calculate_ai_percentages(num_lines, ai_num_lines, ai_blended_num_lines)

        return {
            "code_num_lines": num_lines,
            "code_ai_num_lines": ai_num_lines,
            "code_ai_pure_num_lines": ai_pure_num_lines,
            "code_ai_blended_num_lines": ai_blended_num_lines,
            "code_ai_percentage": percentages["percentage_ai_overall"],
            "code_ai_pure_percentage": percentages["percentage_ai_pure"],
            "code_ai_blended_percentage": percentages["percentage_ai_blended"],
            "not_evaluated_num_files": not_evaluated_num_files,
            "not_evaluated_num_lines": not_evaluated_num_lines,
            **percentages,
        }

    @classmethod
    def calculate_ai_percentages(cls, num_lines, ai_num_lines, ai_blended_num_lines):
        overall = int(round_half_up(ai_num_lines / num_lines * 100, 0)) if num_lines else 0
        blended = int(round_half_up(ai_blended_num_lines / num_lines * 100, 0)) if num_lines else 0
        # To avoid rounding issues, force: Pure = Overall - Blended
        pure = overall - blended
        human = 100 - overall

        return {
            "percentage_ai_overall": overall,
            "percentage_ai_pure": pure,
            "percentage_ai_blended": blended,
            "percentage_human": human,
        }
