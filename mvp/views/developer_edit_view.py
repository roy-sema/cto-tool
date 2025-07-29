from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from rest_framework.reverse import reverse_lazy

from mvp.mixins import DecodePublicIdMixin
from mvp.models import Author
from mvp.services import GroupsAICodeService
from mvp.tasks import ExportGBOMTask
from mvp.utils import start_new_thread


class DeveloperEditView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
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
        organization = request.current_organization
        developers = request.POST.getlist("developers", [])
        main_author = get_object_or_404(Author, pk=pk, organization=organization)
        self.link_developers(organization, main_author, developers)
        ExportGBOMTask().delete_precomputed_gbom(organization)
        self.update_authors_and_groups(organization, main_author)
        messages.success(request, "Developer alias updated!")

        return self.redirect_to_view(request)

    def render_page(self, request, pk):
        current_org = request.current_organization
        author = get_object_or_404(
            Author.objects.prefetch_related("author_set"),
            organization=current_org,
            pk=pk,
        )

        other_authors = (
            Author.objects.filter(organization=current_org, author__isnull=True)
            .prefetch_related("linked_author")
            .exclude(id=author.id)
        )

        other_authors = sorted(
            other_authors,
            key=lambda dev: (
                dev.linked_author != author,
                dev.linked_author is not None,
                dev.name,
            ),
        )

        return render(
            request,
            "mvp/settings/developers_edit.html",
            {"author": author, "other_authors": other_authors},
        )

    def redirect_to_view(self, request, pk=None):
        if pk is None:
            return redirect(reverse_lazy("other_settings") + "#merge-developers")
        else:
            path_name = "developer_edit"
            kwargs = {"pk_encoded": get_object_or_404(Author, pk=pk).public_id()}
            return redirect(reverse_lazy(path_name, kwargs=kwargs))

    def link_developers(self, organization, main_author, developers):
        developer_ids = [self.decode_id(dev) for dev in developers]
        developers = Author.objects.filter(pk__in=developer_ids, organization=organization)

        removed_developers = main_author.author_set.exclude(pk__in=developers)
        added_developers = developers.exclude(pk__in=main_author.author_set.all())
        self.save_linked_developers(main_author, removed_developers, added_developers)

    @transaction.atomic
    def save_linked_developers(self, main_author, removed_developers, added_developers):
        removed_developers.update(linked_author=None, split=True)
        # linked authors can't be in a group
        added_developers.update(linked_author=main_author, group=None)

    @start_new_thread
    def update_authors_and_groups(self, organization, override_author):
        GroupsAICodeService(organization).update_authors(override_author)
        GroupsAICodeService(organization).update_author_groups()
