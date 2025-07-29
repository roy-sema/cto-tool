from typing import Callable

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import Group
from django.urls import reverse

from compass.integrations.integrations import GitHubIntegration
from mvp.models import (
    Author,
    AuthorGroup,
    CustomUser,
    Organization,
    OrgRole,
    Repository,
    RepositoryGroup,
    RepositoryPullRequest,
    Rule,
)

from .base_view_test import BaseViewTestCase


class TestUserRolesMixin:
    role: str
    allowed_views: list
    assertTrue: Callable
    assertIn: Callable
    assertNotIn: Callable
    assertEqual: Callable
    assertIsNone: Callable
    assertIsNotNone: Callable
    client: BaseViewTestCase.client_class

    AUTHORIZATION_VIEWS = [
        "join_list",
        "request_access",
        "signup",
    ]

    COMMON_VIEWS = [
        "change_organization",
        "contact",
        "onboarding",
    ]

    COMPLIANCE_VIEWS = [
        "compliance_standards",
    ]

    GENAI_VIEWS = [
        "dashboard",
        "developer_groups_dashboard",
        "export_developer_groups",
        "export_gbom",
        "pull_request_scan",
        "repository_detail",
        "repository_groups_dashboard",
    ]

    USERS_VIEWS = [
        "users",
    ]

    SETTINGS_VIEWS = [
        "connect_azure_devops",
        "connect_bitbucket",
        "connect_codacy",
        "connect_github",
        "connect_iradar",
        "connect_snyk",
        "connections",
        "developer_group_edit",
        "developer_edit",
        "documents",
        "initiatives",
        "repository_groups",
        "other_settings",
        "repository_group_edit",
        "rule_edit",
        "daily_message",
        "settings",
    ]

    ALL_VIEWS = GENAI_VIEWS + AUTHORIZATION_VIEWS + COMMON_VIEWS + COMPLIANCE_VIEWS + USERS_VIEWS + SETTINGS_VIEWS

    SIDEBAR_MAP = [
        ("dashboard", "Dashboard"),
        ("repository_groups_dashboard", "Repository Groups "),
        ("developer_groups_dashboard", "Developer Groups BETA"),
        # ("compliance_standards", "Compliance Standards"),
    ]

    SETTINGS_SIDEBAR_MAP = [
        ("settings", "Organization Information"),
        ("connections", "Connections"),
        ("users", "Users"),
        ("repository_groups", "Repository Groups"),
        ("initiatives", "Initiatives"),
        ("other_settings", "Other Settings"),
        ("documents", "Documents"),
        ("daily_message", "Daily Message"),
    ]

    def init(self, role: str, allowed_views: list):
        self.role = role
        self.allowed_views = allowed_views

        self.organization = Organization.objects.create(name="TestOrg")

        self.credentials = {"email": f"{role}_user@domain.com", "password": "password"}
        self.user = CustomUser.objects.create_user(**self.credentials)
        self.user.organizations.add(self.organization)
        group = Group.objects.get(name=role)
        self.user.groups.add(group)

        self.repository = Repository.objects.create(
            organization=self.organization,
            provider=GitHubIntegration().provider,
            external_id="abc123",
            owner="test-org",
            name="repo1",
        )

        self.pr = RepositoryPullRequest.objects.create(
            repository=self.repository,
            pr_number=1,
        )

        self.author = Author.objects.create(
            organization=self.organization,
            provider=GitHubIntegration().provider,
            external_id="123",
            name="TestAuthor",
        )

        self.author_group = AuthorGroup.objects.create(organization=self.organization, name="TestAuthorGroup")

        self.repository_group = RepositoryGroup.objects.create(
            organization=self.organization, name="TestRepositoryGroup"
        )

        self.rule = Rule.objects.create(organization=self.organization, name="TestRule")

    def get_url_path_args(self, view_name: str):
        method = getattr(self, f"_get_{view_name}_args", None)
        return method() if method and callable(method) else {}

    def _get_pull_request_scan_args(self):
        return {
            "external_id": self.repository.external_id,
            "pr_number": self.pr.pr_number,
        }

    def _get_developer_edit_args(self):
        return {"pk_encoded": self.author.public_id()}

    def _get_developer_group_edit_args(self):
        return {"pk_encoded": self.author_group.public_id()}

    def _get_repository_detail_args(self):
        return {"pk_encoded": self.repository.public_id()}

    def _get_repository_group_edit_args(self):
        return {"pk_encoded": self.repository_group.public_id()}

    def _get_rule_edit_args(self):
        return {"pk_encoded": self.rule.public_id()}

    def login(self):
        response = self.client.login(**self.credentials)
        self.assertTrue(response)

    def test_redirect_after_login(self):
        """
        Assert user is redirected to a page they can see after login
        """
        self.login()

        response = self.client.get(settings.LOGIN_REDIRECT_URL, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_user_can_only_see_allowed_views(self):
        """
        Assert user can see views they have permission to access,
        and cannot see views they don't have permission to.
        """
        exclude_views = [
            *self.AUTHORIZATION_VIEWS,  # logged users don't need to see authorization views
            "connect_bitbucket",  # this is a callback for BitBucket Oauth consumer
            "connect_github",  # this is a callback for GitHub App
            "change_organization",  # this is a POST endpoint to change the organization
            "onboarding",  # only makes sense after signup
        ]
        views_to_test = [view for view in self.ALL_VIEWS if view not in exclude_views]

        self.login()

        for view_name in views_to_test:
            url = reverse(view_name, kwargs=self.get_url_path_args(view_name))

            response = self.client.get(url)
            status_code = response.status_code

            expected_status_code = 200 if view_name in self.allowed_views else 403
            self.assertEqual(status_code, expected_status_code, f"View: {view_name}")

    def test_visible_items_on_settings_sidebar(self):
        self.login()

        # On "settings" view the sidebar is different
        view_name = "settings"
        if view_name not in self.allowed_views:
            # skip settings sidebar test if user has no access
            return

        url = reverse(view_name, kwargs=self.get_url_path_args(view_name))
        response = self.client.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        side_bar = soup.find("div", {"id": "sidebar-container"})
        side_bar_items = side_bar.find_all("span", {"class": "sidebar-item"})
        side_bar_items = [item.get_text() for item in side_bar_items]

        restricted_roles = {
            "initiatives": ("ComplianceLeader", "EngineeringLeader", "Owner", "SettingsEditor"),
            "users": ("ComplianceLeader",),
            "connections": ("ComplianceLeader",),
        }
        for view, label in self.SETTINGS_SIDEBAR_MAP:
            if view in restricted_roles and self.role in restricted_roles[view]:
                continue

            if view in self.allowed_views:
                self.assertIn(
                    label,
                    side_bar_items,
                    f"View '{view}' not found for role '{self.role}'",
                )
            else:
                self.assertNotIn(
                    label,
                    side_bar_items,
                    f"View '{view}' found for role '{self.role}'",
                )

        # make sure we don't have unknown views in the sidebar
        view_labels = [label for view, label in self.SETTINGS_SIDEBAR_MAP]
        for item in side_bar_items:
            self.assertIn(
                item,
                view_labels,
                f"Unknown sidebar item: '{item}'. Did you add it to the SETTINGS_SIDEBAR_MAP?",
            )

    def test_visible_items_on_sidebar(self):
        """
        Assert the sidebar only shows the items the user has permission to access.
        """
        self.login()

        # TODO test settings page separately
        view_name = self.allowed_views[0]
        # skip this test for settings editor
        if view_name in self.SETTINGS_VIEWS:
            return

        url = reverse(view_name, kwargs=self.get_url_path_args(view_name))
        response = self.client.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        side_bar = soup.find("div", {"id": "sidebar-container"})
        side_bar_items = side_bar.find_all("span", {"class": "sidebar-item"})
        side_bar_items = [item.get_text() for item in side_bar_items]

        for view, label in self.SIDEBAR_MAP:
            if view in self.allowed_views:
                self.assertIn(
                    label,
                    side_bar_items,
                    f"View '{view}' not found for role '{self.role}'",
                )
            else:
                self.assertNotIn(
                    label,
                    side_bar_items,
                    f"View '{view}' found for role '{self.role}'",
                )

        # make sure we don't have unknown views in the sidebar
        view_labels = [label for view, label in self.SIDEBAR_MAP]
        for item in side_bar_items:
            self.assertIn(
                item,
                view_labels,
                f"Unknown sidebar item: '{item}'. Did you add it to the SIDEBAR_MAP?",
            )


class TestUserRolesDeveloper(BaseViewTestCase, TestUserRolesMixin):
    def setUp(self):
        self.init(
            OrgRole.DEVELOPER,
            TestUserRolesMixin.GENAI_VIEWS + TestUserRolesMixin.COMMON_VIEWS,
        )


class TestUserRolesEngineeringLeader(BaseViewTestCase, TestUserRolesMixin):
    def setUp(self):
        self.init(
            OrgRole.ENGINEERING_LEADER,
            TestUserRolesMixin.GENAI_VIEWS + TestUserRolesMixin.SETTINGS_VIEWS + TestUserRolesMixin.COMMON_VIEWS,
        )


class TestUserRolesComplianceLeader(BaseViewTestCase, TestUserRolesMixin):
    def setUp(self):
        self.init(
            OrgRole.COMPLIANCE_LEADER,
            TestUserRolesMixin.COMPLIANCE_VIEWS + TestUserRolesMixin.SETTINGS_VIEWS + TestUserRolesMixin.COMMON_VIEWS,
        )


class TestUserRolesSettingsEditor(BaseViewTestCase, TestUserRolesMixin):
    def setUp(self):
        self.init(
            OrgRole.SETTINGS_EDITOR,
            TestUserRolesMixin.SETTINGS_VIEWS + TestUserRolesMixin.COMMON_VIEWS,
        )


class TestUserRolesOwner(BaseViewTestCase, TestUserRolesMixin):
    def setUp(self):
        self.init(OrgRole.OWNER, TestUserRolesMixin.ALL_VIEWS)
