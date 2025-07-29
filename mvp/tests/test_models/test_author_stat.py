import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from mvp.models import (
    Author,
    AuthorGroup,
    AuthorStat,
    DataProvider,
    Organization,
    Repository,
    RepositoryCommit,
)
from mvp.serializers import (
    AggregatedAuthorStatByDaySerializer,
    AggregatedAuthorStatSerializer,
)
from mvp.utils import normalize_end_date, normalize_start_date


class AuthorStatTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Org",
        )
        self.senior_group = AuthorGroup.objects.create(
            name="Senior Group",
            organization=self.organization,
        )
        self.provider = DataProvider.objects.create(
            name="GitHub",
        )
        self.repository_1 = Repository.objects.create(
            name=f"Repository 1",
            organization=self.organization,
            provider=self.provider,
            external_id=f"author-1",
        )
        self.repository_2 = Repository.objects.create(
            name=f"Repository 2",
            organization=self.organization,
            provider=self.provider,
            external_id=f"author-2",
        )

    def create_authors_stats_data(self, group, number_of_authors, no_stats=False):
        authors = [
            Author(
                name=f"Author {i}",
                organization=self.organization,
                provider=self.provider,
                external_id=f"author-{i}",
                group=group,
            )
            for i in range(number_of_authors)
        ]
        Author.objects.bulk_create(authors)
        authors = authors
        if no_stats:
            return authors

        for author in authors:
            for repository in [self.repository_1, self.repository_2]:
                code_ai_blended_num_lines = 50
                code_ai_pure_num_lines = 50
                code_ai_num_lines = code_ai_blended_num_lines + code_ai_pure_num_lines
                code_not_ai_num_lines = 50
                code_num_lines = code_ai_num_lines + code_not_ai_num_lines
                for i in range(1, 14):
                    if not i % 5:
                        # Simulates no stats for every 5th day
                        continue

                    time = timezone.now() - timedelta(days=i)
                    commit = RepositoryCommit.objects.create(
                        sha=uuid.uuid4(),
                        repository=repository,
                        date_time=time,
                    )
                    # Simulates 3 records per day
                    author_stats = [
                        AuthorStat(
                            time=time + timedelta(minutes=minutes),
                            author=author,
                            repository=repository,
                            commit=commit,
                            code_num_lines=code_num_lines,
                            code_ai_num_lines=code_ai_num_lines,
                            code_ai_blended_num_lines=code_ai_blended_num_lines,
                            code_ai_pure_num_lines=code_ai_pure_num_lines,
                            code_not_ai_num_lines=code_not_ai_num_lines,
                        )
                        for minutes in [1, 5, 10]
                    ]
                    AuthorStat.objects.bulk_create(author_stats)

        return authors

    def calculate_percentages(self, author_ids, query_params_for_time=None):
        # Calculate percentages in python to compare with AuthorStat methods

        if not query_params_for_time:
            query_params_for_time = AuthorStat.get_query_params_for_time()

        stats = AuthorStat.timescale.filter(
            author_id__in=author_ids,
            **query_params_for_time,
        ).values(
            "code_num_lines",
            "code_ai_num_lines",
            "code_ai_blended_num_lines",
            "code_ai_pure_num_lines",
            "code_not_ai_num_lines",
        )
        code_num_lines = sum(stat["code_num_lines"] for stat in stats)
        code_ai_blended_num_lines = sum(stat["code_ai_blended_num_lines"] for stat in stats)
        code_ai_num_lines = sum(stat["code_ai_num_lines"] for stat in stats)
        code_ai_pure_num_lines = sum(stat["code_ai_pure_num_lines"] for stat in stats)
        code_not_ai_num_lines = sum(stat["code_not_ai_num_lines"] for stat in stats)
        return {
            "code_num_lines": code_num_lines,
            "code_ai_blended_num_lines": code_ai_blended_num_lines,
            "code_ai_num_lines": code_ai_num_lines,
            "code_ai_pure_num_lines": code_ai_pure_num_lines,
            "code_not_ai_num_lines": code_not_ai_num_lines,
            "percentage_ai_blended": (
                Decimal(code_ai_blended_num_lines) * Decimal(100) / Decimal(code_num_lines) if code_num_lines else 0
            ),
            "percentage_ai_overall": (
                Decimal(code_ai_num_lines) * Decimal(100) / Decimal(code_num_lines) if code_num_lines else 0
            ),
            "percentage_ai_pure": (
                Decimal(code_ai_pure_num_lines) * Decimal(100) / Decimal(code_num_lines) if code_num_lines else 0
            ),
            "percentage_human": (
                Decimal(code_not_ai_num_lines) * Decimal(100) / Decimal(code_num_lines) if code_num_lines else 0
            ),
        }

    def compare_results(self, result, expected_result):
        for key, value in result.items():
            if key == "bucket":
                continue
            self.assertAlmostEqual(value, expected_result.get(key, 0), places=7)

    def parse_bucket_time(self, bucket_time):
        parsed_date = datetime.strptime(bucket_time, "%Y-%m-%dT%H:%M:%SZ")
        return timezone.make_aware(parsed_date, timezone=timezone.utc)

    def test_get_aggregated_authors_stats_with_single_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 1)
        expected_result = self.calculate_percentages(
            author_ids=[authors[0].id],
        )
        stats = AuthorStat.get_aggregated_authors_stats(
            author_ids=[authors[0].id],
        )
        result = AggregatedAuthorStatSerializer(stats).data
        self.compare_results(result, expected_result)

    def test_get_aggregated_authors_stats_with_linked_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 2)
        author_1 = authors[0]
        author_2 = authors[1]
        author_2.linked_author = author_1
        author_2.save()

        expected_result = self.calculate_percentages(
            author_ids=[author_1.id, author_2.id],
        )
        stats = AuthorStat.get_aggregated_authors_stats(
            author_ids=[author_1.id],
        )
        result = AggregatedAuthorStatSerializer(stats).data
        self.compare_results(result, expected_result)

    def test_get_aggregated_group_stats_with_stats(self):
        self.create_authors_stats_data(self.senior_group, 4)
        expected_result = self.calculate_percentages(
            author_ids=[author.id for author in self.senior_group.author_list()],
        )
        stats = AuthorStat.get_aggregated_group_stats(
            group_id=self.senior_group.id,
        )
        result = AggregatedAuthorStatSerializer(stats).data
        self.compare_results(result, expected_result)

    def test_get_aggregated_group_stats_with_stats_and_linked_authors(self):
        self.create_authors_stats_data(self.senior_group, 4)
        authors = self.senior_group.author_list()

        author_1 = authors[0]
        author_with_linked_author_1 = authors[1]
        author_with_linked_author_1.linked_author = author_1
        author_with_linked_author_1.save()

        author_2 = authors[2]
        author_with_linked_author_2 = authors[3]
        author_with_linked_author_2.linked_author = author_2
        author_with_linked_author_2.save()

        expected_result = self.calculate_percentages(
            author_ids=authors,
        )
        stats = AuthorStat.get_aggregated_group_stats(
            group_id=self.senior_group.id,
        )
        result = AggregatedAuthorStatSerializer(stats).data
        self.compare_results(result, expected_result)

    def test_get_aggregated_group_stats_without_stats(self):
        self.create_authors_stats_data(self.senior_group, 4, no_stats=True)
        stats = AuthorStat.get_aggregated_group_stats(
            group_id=self.senior_group.id,
        )
        for author in self.senior_group.author_list():
            result = AggregatedAuthorStatSerializer(stats.get(author.id, {})).data
            for value in result.values():
                self.assertAlmostEqual(value, 0)

    def test_get_annotated_authors_stats_with_single_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 1)
        author = authors[0]
        expected_result = self.calculate_percentages(
            author_ids=[author.id],
        )
        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=[author.id],
        )
        result = AggregatedAuthorStatSerializer(stats.get(author.id)).data
        self.compare_results(result, expected_result)

    def test_get_annotated_authors_stats_with_linked_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 2)
        author = authors[0]
        author_with_linked_author = authors[1]
        author_with_linked_author.linked_author = author
        author_with_linked_author.save()

        expected_result = self.calculate_percentages(
            author_ids=[author.id, author_with_linked_author.id],
        )
        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=[author.id],
        )
        result = AggregatedAuthorStatSerializer(stats.get(author.id)).data
        self.compare_results(result, expected_result)

    def test_get_annotated_authors_stats_with_linked_author_for_day(self):
        authors = self.create_authors_stats_data(self.senior_group, 3)
        author = authors[0]
        author_with_linked_author = authors[1]
        author_with_linked_author.linked_author = author
        author_with_linked_author.save()

        time = AuthorStat.timescale.filter(author=author).order_by("time").last().time
        expected_result = self.calculate_percentages(
            author_ids=[author.id, author_with_linked_author.id],
            query_params_for_time=AuthorStat.get_query_params_for_time(time),
        )
        other_author = authors[2]
        expected_result_for_other_author = self.calculate_percentages(
            author_ids=[other_author.id],
            query_params_for_time=AuthorStat.get_query_params_for_time(time),
        )
        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=[author.id, other_author.id],
            start_date=time,
        )
        self.compare_results(
            AggregatedAuthorStatSerializer(stats.get(author.id)).data,
            expected_result,
        )
        self.compare_results(
            AggregatedAuthorStatSerializer(stats.get(other_author.id)).data,
            expected_result_for_other_author,
        )

    def test_get_annotated_authors_stats_with_group_with_stats(self):
        self.create_authors_stats_data(self.senior_group, 4)
        author_ids = [author.id for author in self.senior_group.author_list()]
        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=author_ids,
        )
        for author_id in author_ids:
            self.compare_results(
                AggregatedAuthorStatSerializer(stats.get(author_id)).data,
                self.calculate_percentages([author_id]),
            )

    def test_get_annotated_authors_stats_with_group_with_stats_and_linked_authors(self):
        self.create_authors_stats_data(self.senior_group, 4)
        authors = self.senior_group.author_list()

        author_1 = authors[0]
        author_with_linked_author_1 = authors[1]
        author_with_linked_author_1.linked_author = author_1
        author_with_linked_author_1.save()

        author_2 = authors[2]
        author_with_linked_author_2 = authors[3]
        author_with_linked_author_2.linked_author = author_2
        author_with_linked_author_2.save()

        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=[author.id for author in self.senior_group.author_list()],
        )
        self.compare_results(
            AggregatedAuthorStatSerializer(stats.get(author_1.id)).data,
            self.calculate_percentages([author_1.id, author_with_linked_author_1.id]),
        )
        self.compare_results(
            AggregatedAuthorStatSerializer(stats.get(author_2.id)).data,
            self.calculate_percentages([author_2.id, author_with_linked_author_2.id]),
        )

        rest_of_authors = self.senior_group.author_set.exclude(
            id__in=[
                author_1.id,
                author_with_linked_author_1.id,
                author_2.id,
                author_with_linked_author_2.id,
            ]
        ).values_list("id", flat=True)

        for author_id in rest_of_authors:
            self.compare_results(
                AggregatedAuthorStatSerializer(stats.get(author_id)).data,
                self.calculate_percentages([author_id]),
            )

    def test_get_annotated_authors_stats_with_group_without_stats(self):
        self.create_authors_stats_data(self.senior_group, 4, no_stats=True)
        author_ids = [author.id for author in self.senior_group.author_list()]
        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=author_ids,
        )
        for author_id in author_ids:
            result = AggregatedAuthorStatSerializer(stats.get(author_id, {})).data
            for value in result.values():
                self.assertAlmostEqual(value, 0, places=7)

    def test_get_annotated_authors_stats_with_code_not_ai_num_lines_0(self):
        authors = self.create_authors_stats_data(self.senior_group, 1)
        author = authors[0]
        AuthorStat.objects.filter(author=author).update(code_not_ai_num_lines=0)

        stats = AuthorStat.get_annotated_authors_stats(
            author_ids=[author.id],
        )
        result = AggregatedAuthorStatSerializer(stats[author.id]).data
        self.assertEqual(result["percentage_human"], 0)

    def test_get_aggregated_author_stats_by_day_with_single_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 1)
        author = authors[0]
        stats = AuthorStat.get_aggregated_single_author_stats_by_day(
            author=author,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data

        # Check every 5th day is present but empty
        for index in [4, 9]:
            for key, value in result[index].items():
                if key == "bucket":
                    continue
                self.assertAlmostEqual(value, 0, places=0)

        for bucket in result:
            bucket_time = self.parse_bucket_time(bucket["bucket"])
            expected_result = self.calculate_percentages(
                author_ids=[author.id],
                query_params_for_time={
                    "time__gte": normalize_start_date(bucket_time),
                    "time__lt": normalize_end_date(bucket_time),
                },
            )
            self.compare_results(bucket, expected_result)

    def test_get_aggregated_author_stats_by_day_with_linked_author(self):
        authors = self.create_authors_stats_data(self.senior_group, 2)
        author_1 = authors[0]
        author_2 = authors[1]
        author_2.linked_author = author_1
        author_2.save()

        stats = AuthorStat.get_aggregated_single_author_stats_by_day(
            author=author_1,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data
        for bucket in result:
            bucket_time = self.parse_bucket_time(bucket["bucket"])
            expected_result = self.calculate_percentages(
                author_ids=[author_1.id, author_2.id],
                query_params_for_time={
                    "time__gte": normalize_start_date(bucket_time),
                    "time__lt": normalize_end_date(bucket_time),
                },
            )
            self.compare_results(bucket, expected_result)

    def test_get_aggregated_author_stats_by_day_with_single_author_no_stats(self):
        self.create_authors_stats_data(self.senior_group, 4, no_stats=True)
        author = self.senior_group.author_list()[0]
        stats = AuthorStat.get_aggregated_single_author_stats_by_day(
            author=author,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data
        for bucket in result:
            for key, value in bucket.items():
                if key == "bucket":
                    continue
                self.assertAlmostEqual(value, 0, places=0)

    def test_get_aggregated_group_stats_by_day(self):
        self.create_authors_stats_data(self.senior_group, 4)
        stats = AuthorStat.get_aggregated_group_stats_by_day(
            group=self.senior_group,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data
        for bucket in result:
            bucket_time = self.parse_bucket_time(bucket["bucket"])
            expected_result = self.calculate_percentages(
                author_ids=[author.id for author in self.senior_group.author_list()],
                query_params_for_time={
                    "time__gte": normalize_start_date(bucket_time),
                    "time__lt": normalize_end_date(bucket_time),
                },
            )
            self.compare_results(bucket, expected_result)

    def test_get_aggregated_group_stats_by_day_with_linked_authors(self):
        self.create_authors_stats_data(self.senior_group, 4)
        authors = self.senior_group.author_list()

        author_1 = authors[0]
        author_with_linked_author_1 = authors[1]
        author_with_linked_author_1.linked_author = author_1
        author_with_linked_author_1.save()

        author_2 = authors[2]
        author_with_linked_author_2 = authors[3]
        author_with_linked_author_2.linked_author = author_2
        author_with_linked_author_2.save()

        stats = AuthorStat.get_aggregated_group_stats_by_day(
            group=self.senior_group,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data
        for bucket in result:
            bucket_time = self.parse_bucket_time(bucket["bucket"])
            expected_result = self.calculate_percentages(
                author_ids=authors,
                query_params_for_time={
                    "time__gte": normalize_start_date(bucket_time),
                    "time__lt": normalize_end_date(bucket_time),
                },
            )
            self.compare_results(bucket, expected_result)

    def test_get_aggregated_group_stats_by_day_with_group_with_no_stats(self):
        self.create_authors_stats_data(self.senior_group, 4, no_stats=True)
        stats = AuthorStat.get_aggregated_group_stats_by_day(
            group=self.senior_group,
        )
        result = AggregatedAuthorStatByDaySerializer(stats, many=True).data
        for bucket in result:
            for key, value in bucket.items():
                if key == "bucket":
                    continue
                self.assertAlmostEqual(value, 0, places=0)
