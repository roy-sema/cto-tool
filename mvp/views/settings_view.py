from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from sentry_sdk import capture_exception

from mvp.forms import AuthorGroupForm, OrganizationSettingsForm, OtherSettingsForm, RuleConditionFormSet, RuleForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Author, AuthorGroup, Geography, Rule
from mvp.services import OrganizationSegmentService
from mvp.utils import traceback_on_debug


class SettingsView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request):
        current_org = request.current_organization
        return self.render_form(request, OrganizationSettingsForm(instance=current_org))

    def post(self, request):
        current_org = request.current_organization

        # decode geo ids
        # TODO: we should probably move this inside the form, not here
        post_cleaned = request.POST.copy()
        geo_ids = map(lambda x: self.decode_id(x), post_cleaned.getlist("geographies"))
        post_cleaned.setlist("geographies", geo_ids)

        form = OrganizationSettingsForm(post_cleaned, instance=current_org)

        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved!")
            return redirect(reverse_lazy("settings"))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(
            request,
            "mvp/settings/organization.html",
            {"form": form, **self.get_context_data(request, form)},
        )

    def get_context_data(self, request, form):
        org_service = OrganizationSegmentService(request.current_organization)

        codacy_connected = org_service.is_codacy_connected()
        codacy_num_lines = org_service.get_codacy_num_lines() if codacy_connected else None

        if codacy_connected and "num_code_lines" in form.fields:
            form.fields["num_code_lines"].widget.attrs["placeholder"] = f"{codacy_num_lines} (pulled from Codacy)"

        return {
            "segment_description": org_service.segment_description(),
            "codacy_connected": codacy_connected,
            "codacy_num_lines": codacy_num_lines,
            "geographies": Geography.get_sorted_geographies(),
            "instance_geography_ids": form.instance.geographies.values_list("id", flat=True),
            "all_geographies_selected": form.instance.is_all_geographies(),
        }


class OtherSettingsView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request):
        current_org = request.current_organization
        return self.render_form(request, OtherSettingsForm(instance=current_org))

    def post(self, request):
        current_org = request.current_organization

        action = request.POST.get("action")

        if action == "delete_developer_group":
            return self.delete_developer_group(request)
        elif action == "delete_rule":
            return self.delete_rule(request)
        elif "name" in request.POST and "team_type" in request.POST:
            return self.create_author_group(request)
        elif "conditions-TOTAL_FORMS" in request.POST:
            return self.create_rule(request)
        else:
            post_cleaned = request.POST.copy()
            form = OtherSettingsForm(post_cleaned, instance=current_org)

            if form.is_valid():
                form.save()
                messages.success(request, "Other settings saved!")
                return redirect(reverse_lazy("other_settings"))
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")

            return self.render_form(request, form)

    def render_form(self, request, form):
        current_org = request.current_organization
        author_groups = current_org.authorgroup_set.prefetch_related("author_set", "rules").order_by("name")
        ungrouped_authors = Author.objects.filter(
            organization=current_org, linked_author__isnull=True, group__isnull=True
        ).order_by("name")
        author_group_form = AuthorGroupForm(request=request)

        authors = (
            Author.objects.filter(organization=current_org, linked_author__isnull=True)
            .prefetch_related("author_set")
            .order_by("name")
        )

        rules = current_org.rule_set.prefetch_related("conditions", "repositorygroup_set", "authorgroup_set").order_by(
            "name"
        )
        rule_form = RuleForm(request=request)
        rule_formset = RuleConditionFormSet()

        return render(
            request,
            "mvp/settings/other_settings.html",
            {
                "form": form,
                "author_groups": author_groups,
                "ungrouped_authors": ungrouped_authors,
                "author_group_form": author_group_form,
                "authors": authors,
                "rules": rules,
                "rule_form": rule_form,
                "rule_formset": rule_formset,
                **self.get_context_data(request, form),
            },
        )

    def get_context_data(self, request, form):
        org_service = OrganizationSegmentService(request.current_organization)

        codacy_connected = org_service.is_codacy_connected()
        codacy_num_lines = org_service.get_codacy_num_lines() if codacy_connected else None

        if codacy_connected and "num_code_lines" in form.fields:
            form.fields["num_code_lines"].widget.attrs["placeholder"] = f"{codacy_num_lines} (pulled from Codacy)"

        return {
            "segment_description": org_service.segment_description(),
            "codacy_connected": codacy_connected,
            "codacy_num_lines": codacy_num_lines,
        }

    def create_author_group(self, request):
        form = AuthorGroupForm(request.POST, request=request)
        try:
            if form.is_valid():
                form.save()
                messages.success(request, "Developer group created!")
                return redirect(reverse_lazy("other_settings") + "#developer-groups")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        except IntegrityError:
            messages.error(request, "Group names should be unique")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Unexpected error, please try again")

        return self.render_form(request, OtherSettingsForm(instance=request.current_organization))

    def delete_developer_group(self, request):
        pk = self.decode_id(request.POST.get("group_id"))
        current_org = request.current_organization
        try:
            author_group = current_org.authorgroup_set.get(id=pk)
            author_group.delete()
            messages.success(request, "Developer group deleted!")
        except AuthorGroup.DoesNotExist:
            messages.error(request, "Developer group not found")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Developer group could not be deleted")

        return redirect(reverse_lazy("other_settings") + "#developer-groups")

    def create_rule(self, request):
        form = RuleForm(request.POST, request=request)
        formset = RuleConditionFormSet(request.POST, instance=form.instance)
        try:
            if form.is_valid() and formset.is_valid():
                with transaction.atomic():
                    form.save()
                    formset.save()
                messages.success(request, "Rule created!")
                return redirect(reverse_lazy("other_settings") + "#genai-radar-rules")
            else:
                if formset.non_form_errors():
                    messages.error(request, "Rule conditions are invalid")
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        except IntegrityError:
            messages.error(request, "Rule name should be unique")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Unexpected error, please try again")

        return self.render_form(request, OtherSettingsForm(instance=request.current_organization))

    def delete_rule(self, request):
        pk = self.decode_id(request.POST.get("rule_id"))
        current_org = request.current_organization
        try:
            rule = current_org.rule_set.get(id=pk)
            rule.delete()
            messages.success(request, "Rule deleted!")
        except Rule.DoesNotExist:
            messages.error(request, "Rule not found")
        except Exception as e:
            traceback_on_debug()
            capture_exception(e)
            messages.error(request, "Rule could not be deleted")

        return redirect(reverse_lazy("other_settings") + "#genai-radar-rules")
