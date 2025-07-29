from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from mvp.models import (
    CustomUser,
    DataProviderConnection,
    DataProviderRecord,
    Organization,
    OrgRole,
)


class InitGroupsTask:
    def run(self):
        # sees AI Code Monitor + PR scans
        developer_group, created = Group.objects.get_or_create(name=OrgRole.DEVELOPER)

        # sees settings + AI Code Monitor + PR scans
        engineering_leader_group, created = Group.objects.get_or_create(name=OrgRole.ENGINEERING_LEADER)

        # sees settings + Compliance Standards
        compliance_leader_group, created = Group.objects.get_or_create(name=OrgRole.COMPLIANCE_LEADER)

        # can only edit settings
        settings_group, created = Group.objects.get_or_create(name=OrgRole.SETTINGS_EDITOR)

        # full access to all sections
        owner_group, created = Group.objects.get_or_create(name=OrgRole.OWNER)

        # reset permissions
        Permission.objects.all().delete()

        can_edit_connections, created = Permission.objects.get_or_create(
            codename="can_edit_connections",
            name="Can edit connections",
            content_type=ContentType.objects.get_for_model(DataProviderConnection),
        )

        can_edit_members, created = Permission.objects.get_or_create(
            codename="can_edit_members",
            name="Can edit members",
            content_type=ContentType.objects.get_for_model(CustomUser),
        )

        can_edit_organization, created = Permission.objects.get_or_create(
            codename="can_edit_organization",
            name="Can edit organization",
            content_type=ContentType.objects.get_for_model(Organization),
        )

        can_view_compass_budget, created = Permission.objects.get_or_create(
            codename="can_view_compass_budget",
            name="Can view compass budget",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_compliance, created = Permission.objects.get_or_create(
            codename="can_view_compass_compliance",
            name="Can view compass compliance",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_dashboard, created = Permission.objects.get_or_create(
            codename="can_view_compass_dashboard",
            name="Can view compass dashboard",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_integrations, created = Permission.objects.get_or_create(
            codename="can_view_compass_integrations",
            name="Can view compass integrations",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_assign_git_setup, created = Permission.objects.get_or_create(
            codename="can_view_compass_assign_git_setup_to_colleague",
            name="Can view compass assign git setup to colleague",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_assign_jira_setup, created = Permission.objects.get_or_create(
            codename="can_view_compass_assign_jira_setup_to_colleague",
            name="Can view compass assign jira setup to colleague",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_organization_developer_groups, created = Permission.objects.get_or_create(
            codename="can_view_compass_organization_developer_groups",
            name="Can view compass organization developer groups",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_organization_repository_groups, created = Permission.objects.get_or_create(
            codename="can_view_compass_organization_repository_groups",
            name="Can view compass organization repository groups",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_organization_users, created = Permission.objects.get_or_create(
            codename="can_view_compass_organization_users",
            name="Can view compass organization users",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_get_compass_document, created = Permission.objects.get_or_create(
            codename="can_get_compass_document",
            name="Can get compass document",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_list_compass_documents, created = Permission.objects.get_or_create(
            codename="can_list_compass_documents",
            name="Can list compass documents",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_upload_compass_documents, created = Permission.objects.get_or_create(
            codename="can_upload_compass_documents",
            name="Can upload compass documents",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_projects, created = Permission.objects.get_or_create(
            codename="can_view_compass_projects",
            name="Can view compass projects",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_make_compass_projects_chat_input, created = Permission.objects.get_or_create(
            codename="can_make_compass_projects_chat_input",
            name="Can make compass projects chat input",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_set_compass_insights_notifications, created = Permission.objects.get_or_create(
            codename="can_set_compass_insights_notifications",
            name="Can set compass insights notifications",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_roadmap, created = Permission.objects.get_or_create(
            codename="can_view_compass_roadmap",
            name="Can view compass roadmap",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compass_team, created = Permission.objects.get_or_create(
            codename="can_view_compass_team",
            name="Can view compass team",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_ai_code_monitor, created = Permission.objects.get_or_create(
            codename="can_view_ai_code_monitor",
            name="Can view ai code monitor",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_compliance_standards, created = Permission.objects.get_or_create(
            codename="can_view_compliance_standards",
            name="Can view compliance standards",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_insights, created = Permission.objects.get_or_create(
            codename="can_view_insights",
            name="Can view insights",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_view_pull_request_scans, created = Permission.objects.get_or_create(
            codename="can_view_pull_request_scans",
            name="Can view pull request scans",
            content_type=ContentType.objects.get_for_model(DataProviderRecord),
        )

        can_edit_settings, created = Permission.objects.get_or_create(
            codename="can_edit_settings",
            name="Can edit settings",
            content_type=ContentType.objects.get_for_model(Organization),
        )

        developer_group.permissions.add(can_view_ai_code_monitor)
        developer_group.permissions.add(can_view_compass_dashboard)
        developer_group.permissions.add(can_view_pull_request_scans)

        engineering_leader_group.permissions.add(can_view_ai_code_monitor)
        engineering_leader_group.permissions.add(can_view_compass_budget)
        engineering_leader_group.permissions.add(can_view_compass_compliance)
        engineering_leader_group.permissions.add(can_view_compass_dashboard)
        engineering_leader_group.permissions.add(can_view_compass_integrations)
        engineering_leader_group.permissions.add(can_view_compass_assign_git_setup)
        engineering_leader_group.permissions.add(can_view_compass_assign_jira_setup)
        engineering_leader_group.permissions.add(can_view_compass_organization_developer_groups)
        engineering_leader_group.permissions.add(can_view_compass_organization_repository_groups)
        engineering_leader_group.permissions.add(can_view_compass_organization_users)
        engineering_leader_group.permissions.add(can_get_compass_document)
        engineering_leader_group.permissions.add(can_list_compass_documents)
        engineering_leader_group.permissions.add(can_upload_compass_documents)
        engineering_leader_group.permissions.add(can_view_compass_projects)
        engineering_leader_group.permissions.add(can_make_compass_projects_chat_input)
        engineering_leader_group.permissions.add(can_set_compass_insights_notifications)
        engineering_leader_group.permissions.add(can_view_compass_roadmap)
        engineering_leader_group.permissions.add(can_view_compass_team)
        engineering_leader_group.permissions.add(can_view_pull_request_scans)
        engineering_leader_group.permissions.add(can_edit_settings)
        engineering_leader_group.permissions.add(can_edit_organization)
        engineering_leader_group.permissions.add(can_edit_connections)

        compliance_leader_group.permissions.add(can_view_compliance_standards)
        compliance_leader_group.permissions.add(can_edit_settings)
        compliance_leader_group.permissions.add(can_edit_organization)
        compliance_leader_group.permissions.add(can_edit_connections)

        settings_group.permissions.add(can_edit_settings)
        settings_group.permissions.add(can_edit_organization)
        settings_group.permissions.add(can_edit_connections)

        owner_group.permissions.add(can_edit_members)
        owner_group.permissions.add(can_edit_organization)
        owner_group.permissions.add(can_view_ai_code_monitor)
        owner_group.permissions.add(can_view_compass_budget)
        owner_group.permissions.add(can_view_compass_compliance)
        owner_group.permissions.add(can_view_compass_dashboard)
        owner_group.permissions.add(can_view_compass_integrations)
        owner_group.permissions.add(can_view_compass_assign_git_setup)
        owner_group.permissions.add(can_view_compass_organization_users)
        owner_group.permissions.add(can_get_compass_document)
        owner_group.permissions.add(can_list_compass_documents)
        owner_group.permissions.add(can_upload_compass_documents)
        owner_group.permissions.add(can_view_compass_organization_developer_groups)
        owner_group.permissions.add(can_view_compass_organization_repository_groups)
        owner_group.permissions.add(can_view_compass_projects)
        owner_group.permissions.add(can_make_compass_projects_chat_input)
        owner_group.permissions.add(can_set_compass_insights_notifications)
        owner_group.permissions.add(can_view_compass_roadmap)
        owner_group.permissions.add(can_view_compass_team)
        owner_group.permissions.add(can_view_pull_request_scans)
        owner_group.permissions.add(can_view_compliance_standards)
        owner_group.permissions.add(can_view_insights)
        owner_group.permissions.add(can_edit_settings)
        owner_group.permissions.add(can_edit_connections)
