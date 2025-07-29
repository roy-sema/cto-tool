from django.contrib.auth.models import Group
from django.urls import reverse

from compass.integrations.integrations import GitHubIntegration
from mvp.models import (
    CustomUser,
    Organization,
    Repository,
    RepositoryCommit,
    RepositoryPullRequest,
)

from .base_view_test import BaseViewTestCase


class PullRequestScanViewTests(BaseViewTestCase):
    def setUp(self):
        self.credentials = {"email": "testuser@domain.com", "password": "testpass456"}
        self.user = CustomUser.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

        self.owner_group = Group.objects.get(name="Owner")
        self.owner_group.user_set.add(self.user)

        self.organization1 = Organization.objects.create(name="TestOrg1")
        self.organization2 = Organization.objects.create(name="TestOrg2")

        self.repository1 = Repository.objects.create(
            organization=self.organization1,
            provider=GitHubIntegration().provider,
            external_id="abc123",
            owner="org1",
            name="repo1",
        )
        self.repository2 = Repository.objects.create(
            organization=self.organization2,
            provider=GitHubIntegration().provider,
            external_id="abc234",
            owner="org2",
            name="repo2",
        )

        self.commit1_1 = RepositoryCommit.objects.create(
            repository=self.repository1,
            sha="123456",
            date_time="2024-01-01T00:00:00Z",
        )
        self.commit1_2 = RepositoryCommit.objects.create(
            repository=self.repository1,
            sha="123457",
            date_time="2024-01-02T00:00:00Z",
        )
        self.commit2_1 = RepositoryCommit.objects.create(
            repository=self.repository2,
            sha="234567",
            date_time="2024-01-01T00:00:00Z",
        )
        self.commit2_2 = RepositoryCommit.objects.create(
            repository=self.repository2,
            sha="234568",
            date_time="2024-01-02T00:00:00Z",
        )

        self.pr1 = RepositoryPullRequest.objects.create(
            repository=self.repository1,
            pr_number=1,
            base_commit_sha=self.commit1_1.sha,
            head_commit_sha=self.commit1_2.sha,
        )
        self.pr2 = RepositoryPullRequest.objects.create(
            repository=self.repository2,
            pr_number=2,
            base_commit_sha=self.commit2_1.sha,
            head_commit_sha=self.commit2_2.sha,
        )

        self.commit1_2.pull_requests.add(self.pr1)
        self.commit2_2.pull_requests.add(self.pr2)

    def login(self):
        self.client.login(email=self.credentials["email"], password=self.credentials["password"])

    def request_pr(self, pr):
        return self.client.get(
            reverse(
                "pull_request_scan",
                kwargs={
                    "external_id": pr.repository.external_id,
                    "pr_number": pr.pr_number,
                },
            )
        )

    def test_access_other_own_pr(self):
        self.user.organizations.add(self.organization1)
        self.login()

        response = self.request_pr(self.pr1)
        self.assertEqual(response.status_code, 200)

    def test_access_other_org_pr(self):
        self.user.organizations.add(self.organization1)
        self.login()

        response = self.request_pr(self.pr2)
        self.assertEqual(response.status_code, 404)

    def test_access_other_both_pr(self):
        self.user.organizations.add(self.organization1)
        self.user.organizations.add(self.organization2)
        self.login()

        response = self.request_pr(self.pr1)
        self.assertEqual(response.status_code, 200)

        response = self.request_pr(self.pr2)
        self.assertEqual(response.status_code, 200)

    def test_access_superuser_no_access_other_pr(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()

        self.user.organizations.add(self.organization1)
        self.login()

        response = self.request_pr(self.pr1)
        self.assertEqual(response.status_code, 200)

        # let's make sure we keep code from customers safe, even from ourselves
        response = self.request_pr(self.pr2)
        self.assertEqual(response.status_code, 404)
