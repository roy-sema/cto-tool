from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from mvp.forms import AuthorGroupForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Author, AuthorGroup
from mvp.services import GroupsAICodeService
from mvp.tasks import ExportGBOMTask


class DeveloperGroupEditView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
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
            author_group = AuthorGroup.objects.get(id=pk, organization=current_org)
        except AuthorGroup.DoesNotExist:
            return self.redirect_to_view(request)

        form = AuthorGroupForm(data=request.POST, instance=author_group, request=request)

        try:
            if form.is_valid():
                saved_group = self.save_form(form, request)
                ExportGBOMTask().delete_precomputed_gbom(current_org)
                GroupsAICodeService(current_org).update_author_groups(override_group=saved_group)
                messages.success(request, "Developer group updated!")
                return self.redirect_to_view(request)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        except IntegrityError:
            messages.error(request, "Group names should be unique")

        return self.render_form(request, author_group, form)

    def render_page(self, request, author_group_id):
        current_org = request.current_organization
        try:
            author_group = AuthorGroup.objects.prefetch_related("author_set", "rules").get(
                id=author_group_id, organization=current_org
            )
        except AuthorGroup.DoesNotExist:
            return self.redirect_to_view(request)

        form = AuthorGroupForm(instance=author_group, request=request)
        return self.render_form(request, author_group, form)

    def render_form(self, request, author_group, form):
        current_org = request.current_organization

        org_authors = self.get_organization_authors(current_org, author_group)

        return render(
            request,
            "mvp/settings/author_groups_edit.html",
            {
                "author_group": author_group,
                "org_authors": org_authors,
                "form": form,
            },
        )

    def redirect_to_view(self, request):
        return redirect(reverse_lazy("other_settings") + "#developer-groups")

    @transaction.atomic
    def save_form(self, form, request):
        author_group = form.save()
        author_ids = self.get_author_ids(request)

        # Update authors in the group
        Author.objects.filter(group=author_group).update(group=None)
        Author.objects.filter(id__in=author_ids).update(group=author_group)

        return author_group

    def get_author_ids(self, request):
        author_ids = request.POST.getlist("authors")
        return {self.decode_id(author_id) for author_id in author_ids}

    def get_organization_authors(self, organization, top_group):
        authors = (
            Author.objects.filter(organization=organization)
            .filter(linked_author__isnull=True)
            .prefetch_related("group")
        )

        # show current group's authors first, then ungrouped authors, then the rest by group
        return sorted(
            authors,
            key=lambda author: (
                0 if author.group == top_group else 1 if author.group is None else 2,
                author.group.name if author.group else "",
                author.name,
            ),
        )
