from typing import NamedTuple

import factory
from django.contrib.auth.models import Group

from compass.integrations.integrations.github_integration import GitHubIntegration
from cto_tool.testing.base_factories import ModelFactory
from mvp.models import CustomUser, Organization, Repository


class CustomUserFactory(ModelFactory):
    # using sequence since faker doesn't ensure uniqueness and has a limited pool of emails
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.Faker("password")
    is_staff = False
    is_active = True
    initials = factory.LazyAttribute(lambda obj: f"{obj.first_name[0]}{obj.last_name[0]}".upper())
    company_url = factory.Faker("url")
    company_number_of_developers = factory.Faker("pyint", min_value=1, max_value=1000)
    consent_marketing_notifications = False
    compass_anomaly_insights_notifications = False
    compass_summary_insights_notifications = False
    hide_environment_banner = False

    @factory.post_generation
    def organizations(self, *a, **kw):
        return ModelFactory.set_many_to_many(self, "organizations", *a, **kw)

    class Meta:
        model = CustomUser


class OrganizationFactory(ModelFactory):
    name = factory.Faker("company")

    @factory.post_generation
    def users(self, *a, **kw):
        return ModelFactory.set_many_to_many(self, "customuser_set", *a, **kw)

    class Meta:
        model = Organization


class OrganizationOwnerResult(NamedTuple):
    organization: object
    user: object
    owner_group: object


def create_organization_owner():
    organization = OrganizationFactory()
    user = CustomUserFactory(organizations=[organization])
    owner_group = Group.objects.get(name="Owner")
    owner_group.user_set.add(user)
    return OrganizationOwnerResult(
        organization=organization,
        user=user,
        owner_group=owner_group,
    )


class RepositoryFactory(ModelFactory):
    organization = factory.SubFactory(OrganizationFactory)
    provider = factory.LazyFunction(lambda: GitHubIntegration().provider)
    external_id = factory.Faker("uuid4")
    owner = factory.Faker("user_name")
    name = factory.Faker("word")

    class Meta:
        model = Repository
