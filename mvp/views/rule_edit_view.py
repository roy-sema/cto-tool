import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from mvp.forms import RuleConditionFormSet, RuleForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Rule, RuleCondition


class RuleEditView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request, pk_encoded):
        if not pk_encoded:
            return self.redirect_to_view()

        pk = self.decode_id(pk_encoded)
        return self.render_page(request, pk)

    def post(self, request, pk_encoded):
        if not pk_encoded:
            return self.redirect_to_view()

        pk = self.decode_id(pk_encoded)
        current_org = request.current_organization

        try:
            rule = Rule.objects.get(id=pk, organization=current_org)
        except Rule.DoesNotExist:
            return self.redirect_to_view()

        data = self.clean_post_data(request.POST)
        form = RuleForm(data=data, instance=rule, request=request)
        formset = RuleConditionFormSet(data=data, instance=rule)

        try:
            if form.is_valid() and formset.is_valid():
                self.save_forms(form, formset, data)
                messages.success(request, "Rule updated!")
                return self.redirect_to_view()
            else:
                if formset.non_form_errors():
                    messages.error(request, "Rule conditions are invalid")
        except IntegrityError as e:
            messages.error(request, "Rule name should be unique")

        return self.render_form(request, rule, form, formset)

    def render_page(self, request, rule_id):
        current_org = request.current_organization
        try:
            rule = Rule.objects.get(id=rule_id, organization=current_org)
        except Rule.DoesNotExist:
            return self.redirect_to_view()

        form = RuleForm(instance=rule)
        formset = RuleConditionFormSet(instance=form.instance)
        return self.render_form(request, rule, form, formset)

    def render_form(self, request, rule, form, formset):
        return render(
            request,
            "mvp/settings/rules_edit.html",
            {
                "rule": rule,
                "form": form,
                "formset": formset,
            },
        )

    def redirect_to_view(self):
        return redirect(reverse_lazy("other_settings"))

    @transaction.atomic
    def save_forms(self, rule_form, conditions_form, post_data):
        # HACK: There's some kind of issue with conditions_form.deleted_forms being empty, so we hack it
        # https://stackoverflow.com/questions/75732686/form-marked-for-deletion-but-empty-formset-deleted-forms
        delete_ids = []
        for key, value in post_data.items():
            if key.endswith("-DELETE") and value == "on":
                match = re.match(r"conditions-(\d+)-DELETE", key)
                index = match.group(1)
                delete_ids.append(post_data[f"conditions-{index}-id"])

        RuleCondition.objects.filter(id__in=delete_ids, rule=rule_form.instance).delete()

        conditions_form.save()
        rule_form.save()

    def clean_post_data(self, data):
        cleaned_data = data.copy()
        for key, value in data.items():
            if key.endswith("-public_id"):
                id_key = key.replace("-public_id", "-id")
                cleaned_data[id_key] = self.decode_id(value)

        return cleaned_data
