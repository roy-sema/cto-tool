import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from mvp.forms import RepositoryGroupForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import (
    JiraProject,
    ProductivityImprovementChoices,
    Repository,
    RepositoryGroup,
    RepositoryGroupCategoryChoices,
)
from mvp.services import GroupsAICodeService
from mvp.tasks import ExportGBOMTask


class RepositoryGroupEditView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request, pk_encoded):
        if not pk_encoded:
            return self.redirect_to_view(request)

        pk = self.decode_id(pk_encoded)
        return self.render_page(request, pk)

    def post(self, request, pk_encoded):
        if not pk_encoded:
            return self.redirect_to_view(request)

        pk = self.decode_id(pk_encoded)
        current_org = request.current_organization
        try:
            repo_group = RepositoryGroup.objects.get(id=pk, organization=current_org)
        except RepositoryGroup.DoesNotExist:
            return self.redirect_to_view(request)

        form = RepositoryGroupForm(data=request.POST, instance=repo_group, request=request)

        try:
            if form.is_valid():
                saved_group = self.save_form(form, request)
                ExportGBOMTask().delete_precomputed_gbom(current_org)
                GroupsAICodeService(current_org).update_repository_groups(override_group=saved_group)
                # TODO: delete GitDiffRepositoryGroupInsight if repositories change,
                # then re-execute insight generation for default date range
                messages.success(request, f"Repository group '{saved_group.name}' updated!")
                return self.redirect_to_view(request)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        except IntegrityError:
            messages.error(request, "Group names should be unique")

        return self.render_form(request, repo_group, form)

    def render_page(self, request, repo_group_id):
        current_org = request.current_organization
        try:
            repo_group = RepositoryGroup.objects.prefetch_related("repositories", "rules", "jira_projects").get(
                id=repo_group_id, organization=current_org
            )
        except RepositoryGroup.DoesNotExist:
            return self.redirect_to_view(request)

        form = RepositoryGroupForm(instance=repo_group, request=request)
        return self.render_form(request, repo_group, form)

    def render_form(self, request, repo_group, form):
        current_org = request.current_organization

        org_repositories = self.get_organization_repositories(current_org, repo_group)

        usage_categories = RepositoryGroupCategoryChoices.get_as_detailed_list()
        potential_productivity_improvement_defaults = ProductivityImprovementChoices.get_defaults()
        org_projects = self.get_organization_projects(current_org, repo_group)

        return render(
            request,
            "mvp/settings/repository_groups_edit.html",
            {
                "repository_group": repo_group,
                "org_repositories": org_repositories,
                "usage_categories": usage_categories,
                "potential_productivity_improvement_defaults": potential_productivity_improvement_defaults,
                "org_projects": org_projects,
                # These are used for filtering inside the template.
                "org_repositories_search_json": json.dumps(
                    [{repo.full_name().lower(): repo.id} for repo in org_repositories]
                ),
                "org_projects_search_json": json.dumps(
                    [{(project.name.lower() + " " + project.key.lower()): project.id} for project in org_projects]
                ),
                "form": form,
            },
        )

    def redirect_to_view(self, request):
        return redirect(reverse_lazy("repository_groups"))

    @transaction.atomic
    def save_form(self, form, request):
        repo_group = form.save()
        repo_ids = self.get_repository_ids(request)
        project_ids = self.get_project_ids(request)

        # Update repositories in the group
        repos_to_remove = Repository.objects.filter(repository_group=repo_group).exclude(id__in=repo_ids)
        for repo in repos_to_remove:
            repo.repository_group.remove(repo_group)

        repos_to_add = Repository.objects.filter(id__in=repo_ids)
        for repo in repos_to_add:
            repo.repository_group.add(repo_group)

        # Update projects in the group
        projects_to_remove = JiraProject.objects.filter(repository_group=repo_group).exclude(id__in=project_ids)
        for project in projects_to_remove:
            project.repository_group.remove(repo_group)

        projects_to_add = JiraProject.objects.filter(id__in=project_ids)
        for project in projects_to_add:
            project.repository_group.add(repo_group)

        return repo_group

    def get_repository_ids(self, request):
        repo_ids = request.POST.getlist("repositories")
        return {self.decode_id(repo_id) for repo_id in repo_ids}

    def get_project_ids(self, request):
        project_ids = request.POST.getlist("projects")
        return set(project_ids)

    def get_organization_repositories(self, organization, top_group):
        repositories = Repository.objects.filter(organization=organization).prefetch_related("repository_group")

        # show current group's repositories first, then ungrouped repositories, then the rest by group
        return sorted(
            repositories,
            key=lambda repo: (
                0 if top_group in repo.repository_group.all() else 1 if repo.repository_group.count() == 0 else 2,
                sorted(g.name for g in repo.repository_group.all()),
                repo.owner.lower(),
                repo.full_name().lower(),
            ),
        )

    def get_organization_projects(self, organization, group):
        """Get jira projects sorted by selected for this group."""
        projects = JiraProject.objects.filter(organization=organization, is_selected=True).prefetch_related(
            "repository_group"
        )

        # Cache the repository groups once per project
        for project in projects:
            project._repo_groups = list(project.repository_group.all())

        return sorted(
            projects,
            key=lambda project: (
                (0 if group in project._repo_groups else 1 if project._repo_groups else 2),
                project.name.lower(),
            ),
        )
