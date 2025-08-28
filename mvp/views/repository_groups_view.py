from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from sentry_sdk import capture_exception

from mvp.forms import RepositoryGroupForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import (
    ProductivityImprovementChoices,
    Repository,
    RepositoryGroup,
    RepositoryGroupCategoryChoices,
)
from mvp.utils import traceback_on_debug


class RepositoryGroupsView(
    LoginRequiredMixin,
    DecodePublicIdMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "mvp.can_edit_settings"

    def get(self, request):
        return self.render_page(request)

    def post(self, request):
        action = request.POST.get("action")

        if action == "delete_repository_group":
            return self.delete_repository_group(request)

        return self.create_repository_group(request)

    def render_page(self, request):
        form = RepositoryGroupForm(request=request)
        return self.render_form(request, form)

    def render_form(self, request, form):
        current_org = request.current_organization
        repository_groups = current_org.repositorygroup_set.prefetch_related(
            "repositories", "rules", "jira_projects"
        ).order_by("name")
        usage_categories = RepositoryGroupCategoryChoices.get_as_detailed_list()
        ungrouped_repos = (
            Repository.objects.filter(organization=current_org, repository_group__isnull=True)
            .order_by("owner", "name")
            .distinct()
        )
        potential_productivity_improvement_defaults = ProductivityImprovementChoices.get_defaults()

        return render(
            request,
            "mvp/settings/repository_groups.html",
            {
                "repository_groups": repository_groups,
                "form": form,
                "usage_categories": usage_categories,
                "ungrouped_repos": ungrouped_repos,
                "potential_productivity_improvement_defaults": (potential_productivity_improvement_defaults),
                "organization_wide_rules": (current_org.rule_set.filter(apply_organization=True)),
            },
        )

    def redirect_to_edit(self, request, repo_group_id):
        return redirect(reverse_lazy("repository_group_edit", kwargs={"pk_encoded": repo_group_id}))

    def redirect_to_view(self, request):
        return redirect(reverse_lazy("repository_groups"))

    def create_repository_group(self, request):
        form = RepositoryGroupForm(request.POST, request=request)
        try:
            if form.is_valid():
                instance = form.save()
                messages.success(request, "Repository group created!")
                public_id = instance.public_id()
                return self.redirect_to_edit(request, public_id)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        except IntegrityError:
            messages.error(request, "Group names should be unique")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Unexpected error, please try again")

        return self.render_form(request, form)

    def delete_repository_group(self, request):
        pk = self.decode_id(request.POST.get("group_id"))
        current_org = request.current_organization
        try:
            repository_group = current_org.repositorygroup_set.get(id=pk)
            repository_group.delete()
            messages.success(request, "Repository group deleted!")
        except RepositoryGroup.DoesNotExist:
            messages.error(request, "Repository group not found")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Repository group could not be deleted")

        return self.redirect_to_view(request)
