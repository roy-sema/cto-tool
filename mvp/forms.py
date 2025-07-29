import json

import markdown
from allauth.account.forms import ResetPasswordKeyForm
from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.forms import inlineformset_factory
from import_export.forms import ExportForm

from .mixins import DecodePublicIdMixin
from .models import (
    AITypeChoices,
    Author,
    AuthorGroup,
    ComplianceStandard,
    ComplianceStandardComponent,
    CustomUser,
    DataProvider,
    DataProviderConnection,
    DataProviderProject,
    Geography,
    Industry,
    JiraProject,
    MessageIntegration,
    ModuleChoices,
    Organization,
    ProductivityImprovementChoices,
    RepositoryGroup,
    RepositoryPullRequestStatusCheck,
    Rule,
    RuleCondition,
    SystemMessage,
    UserInvitation,
)


class PrettyJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, indent, sort_keys, **kwargs):
        super().__init__(*args, indent=2, sort_keys=True, **kwargs)


class ComplianceStandardForm(forms.ModelForm):
    class Meta:
        model = ComplianceStandard
        fields = "__all__"

    industries = forms.ModelMultipleChoiceField(
        queryset=Industry.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text=f"NOTE: Leave all unchecked for '{Industry.LABEL_NONE}'",
        required=False,
    )

    def clean_industries(self):
        industries = self.cleaned_data.get("industries")
        if industries is not None and industries.filter(name="To be determined").exists() and industries.count() > 1:
            raise ValidationError("'To be determined' cannot be used with other industries.")
        return industries


class ComplianceStandardComponentForm(forms.ModelForm):
    ai_types = forms.MultipleChoiceField(
        choices=AITypeChoices.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ComplianceStandardComponent
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(ComplianceStandardComponentForm, self).__init__(*args, **kwargs)
        rules = Rule.objects.all().order_by("name")

        self.fields["rules"].queryset = rules


class InviteUserForm(forms.ModelForm):
    """
    A form for creating new users when invited.
    Includes a repeated password and accept terms field.
    """

    accept_terms = forms.BooleanField(
        label="Accept the Terms & Conditions and Privacy Policy",
        required=True,
    )
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ["email", "first_name", "last_name", "consent_marketing_notifications"]

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        self.instance.set_password(self.cleaned_data["password1"])
        return super().save(commit)


class CustomUserCreationForm(InviteUserForm):
    """
    A form for creating new users. Includes all the required
    fields, plus a repeated password, accept terms field and
    additional fields to create the organization.
    """

    organization_name = forms.CharField(max_length=100, required=True)

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "first_name",
            "last_name",
            "organization_name",
            "consent_marketing_notifications",
        ]


class CustomUserChangeForm(forms.ModelForm):
    """
    A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    disabled password hash display field.
    """

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "password",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
        ]


class UserInvitationForm(forms.ModelForm):
    class Meta:
        model = UserInvitation
        fields = ["organization", "first_name", "last_name", "email", "role"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.user = self.request.user if self.request else None
        self.is_staff = self.user and self.user.is_staff
        super(UserInvitationForm, self).__init__(*args, **kwargs)

        if self.is_staff:
            self.fields["new_organization_name"] = forms.CharField(
                required=False,
                max_length=100,
                widget=forms.TextInput(
                    attrs={
                        "placeholder": "Fill this to create a new organization",
                    }
                ),
            )

        if self.user:
            self.fields["organization"] = forms.ModelChoiceField(
                queryset=Organization.objects.order_by("name").all(),
                required=False,
            )

    def clean(self):
        cleaned_data = super().clean()

        if not self.user or not self.user.is_staff:
            return cleaned_data

        organization = cleaned_data.get("organization")
        new_organization_name = cleaned_data.get("new_organization_name")

        if organization and new_organization_name:
            raise ValidationError("Please select an existing organization or provide a name for a new one, not both.")

        if not organization and not new_organization_name:
            raise ValidationError("Please select an existing organization or provide a name for a new one.")

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        organization_name = self.cleaned_data.get("new_organization_name", None)

        if not self.is_staff:
            self.instance.organization = self.request.current_organization
        elif organization_name:
            organization = self.create_new_organization(organization_name)
            organization.copy_preset_rules()
            self.instance.organization = organization

        return super(UserInvitationForm, self).save(commit=commit)

    def create_new_organization(self, name):
        org = Organization(name=name)
        org.set_default_flags()
        org.set_default_limits()
        org.save()

        return org


class BulkInviteForm(forms.Form):
    emails = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Enter email addresses separated by comma"}),
        required=True,
    )
    role = forms.ChoiceField(choices=[], required=True)

    def __init__(self, *args, **kwargs):
        super(BulkInviteForm, self).__init__(*args, **kwargs)

        self.fields["role"].choices = [(group.id, group.name) for group in Group.objects.all()]

    def clean_emails(self):
        emails = self.cleaned_data.get("emails")
        emails = emails.replace(" ", "").split(",")

        invalid_emails = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_emails.append(email)

        # Check for invalid emails
        if invalid_emails:
            invalid_emails_str = ", ".join(invalid_emails)
            if len(invalid_emails) > 1:
                message = f"{invalid_emails_str} are not valid email addresses"
            message = f"{invalid_emails_str} is not a valid email address"
            raise ValidationError(message)

        # Check for existing invitations
        existing_invitations = list(UserInvitation.objects.filter(email__in=emails).values_list("email", flat=True))
        if existing_invitations:
            existing_invitations_str = ", ".join(existing_invitations)
            if len(existing_invitations) > 1:
                message = f"{existing_invitations_str} are already invited. Please remove them from the list."
            message = f"{existing_invitations_str} is already invited. Please remove it from the list."
            raise ValidationError(message)

        # Check for existing users
        existing_users = list(CustomUser.objects.filter(email__in=emails).values_list("email", flat=True))
        if existing_users:
            existing_users_str = ", ".join(existing_users)
            if len(existing_users) > 1:
                message = f"{existing_users_str} are already registered as users. Please remove them from the list."
            message = f"{existing_users_str} is already registered as a user. Please remove it from the list."
            raise ValidationError(message)

        return emails


class OrganizationBaseForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        industry_id = cleaned_data.get("industry")

        if industry_id == "":
            cleaned_data["industry"] = None
        else:
            try:
                cleaned_data["industry"] = Industry.objects.get(id=industry_id)
            except Industry.DoesNotExist:
                raise forms.ValidationError("Selected industry does not exist")

        return cleaned_data


class OrganizationAdminForm(OrganizationBaseForm):
    def __init__(self, *args, **kwargs):
        super(OrganizationBaseForm, self).__init__(*args, **kwargs)
        industries = Industry.objects.all().order_by("name")

        choices = [("", Industry.LABEL_NONE)] + [(industry.id, industry.name) for industry in industries]
        choices = sorted(choices, key=lambda r: r[1])

        self.fields["industry"] = forms.ChoiceField(choices=choices, required=False, label="Industry")

        self.fields["geographies"].required = False

    class Meta:
        model = Organization
        fields = "__all__"


class DataProviderProjectAdminForm(forms.ModelForm):
    meta = forms.JSONField(encoder=PrettyJSONEncoder)

    class Meta:
        model = DataProviderProject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meta"].widget = forms.Textarea(attrs={"cols": 80, "rows": 20})


class OrganizationBasePublicForm(DecodePublicIdMixin, OrganizationBaseForm):
    def __init__(self, *args, **kwargs):
        super(OrganizationBasePublicForm, self).__init__(*args, **kwargs)
        industries = Industry.objects.all().order_by("name")

        choices = [("", Industry.LABEL_NONE)] + [(industry.public_id(), industry.name) for industry in industries]
        choices = sorted(choices, key=lambda r: r[1])

        self.fields["industry"] = forms.ChoiceField(choices=choices, required=False, label="Industry")

        if self.instance.industry:
            self.initial["industry"] = self.instance.industry.public_id()

    def clean_geographies(self):
        geographies = self.cleaned_data.get("geographies")
        # if all geographies are selected, set it to the "All" geography instance
        if len(geographies) == Geography.objects.count() - 1:
            geographies = Geography.objects.filter(name="All")

        return geographies

    def clean_industry(self):
        industry = self.cleaned_data.get("industry")
        return self.decode_id(industry) if industry else ""


class OrganizationSettingsForm(OrganizationBasePublicForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "geographies",
            "require_mfa",
        ]

    def __init__(self, *args, **kwargs):
        super(OrganizationSettingsForm, self).__init__(*args, **kwargs)

        unrequired_fields = ["geographies"]

        for field_name in unrequired_fields:
            self.fields[field_name].required = False

    def clean_geographies(self):
        geographies = self.cleaned_data.get("geographies")
        # if all geographies are selected, set it to the "All" geography instance
        if len(geographies) == Geography.objects.count() - 1:
            geographies = Geography.objects.filter(name="All")

        return geographies


class OtherSettingsForm(OrganizationBasePublicForm):
    class Meta:
        model = Organization
        fields = [
            "industry",
            "is_software_company",
            "status_check_enabled",
            "status_check_mark_as_failed",
            "avg_developer_cost",
            "num_developers",
            "num_code_lines",
            "all_time_developers",
            "first_commit_date",
            "tools_genai_monthly_cost",
        ]


class ConnectAzureDevOpsForm(forms.ModelForm):
    base_url = forms.CharField(max_length=255, required=True, label="Base URL")
    personal_access_token = forms.CharField(max_length=255, required=True, label="Personal access token")

    class Meta:
        model = DataProviderConnection
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data:
            self.fields["base_url"].initial = self.instance.data.get("base_url")
            self.fields["personal_access_token"].initial = self.instance.data.get("personal_access_token")

        self.fields["base_url"].widget.attrs.update({"placeholder": "https://dev.azure.com/your_organization/"})

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = {
            "base_url": self.cleaned_data.get("base_url"),
            "personal_access_token": self.cleaned_data.get("personal_access_token"),
        }
        if commit:
            instance.save()
        return instance


class ConnectCodacyForm(forms.ModelForm):
    api_token = forms.CharField(max_length=255, required=True, label="API Token")

    class Meta:
        model = DataProviderConnection
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data:
            self.fields["api_token"].initial = self.instance.data.get("api_token")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = {
            "api_token": self.cleaned_data.get("api_token"),
        }
        if commit:
            instance.save()
        return instance


class ConnectIRadarForm(forms.ModelForm):
    username = forms.CharField(max_length=255, required=True, label="Username")
    password = forms.CharField(
        max_length=255,
        required=True,
        label="Password",
        widget=forms.PasswordInput(),
    )

    class Meta:
        model = DataProviderConnection
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data:
            self.fields["username"].initial = self.instance.data.get("username")
            self.fields["password"].initial = self.instance.data.get("password")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = {
            "username": self.cleaned_data.get("username"),
            "password": self.cleaned_data.get("password"),
        }
        if commit:
            instance.save()
        return instance


class ConnectSnykForm(forms.ModelForm):
    api_token = forms.CharField(max_length=255, required=True, label="API Token")
    org_id = forms.CharField(max_length=255, required=True, label="Organization ID")

    class Meta:
        model = DataProviderConnection
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data:
            self.fields["api_token"].initial = self.instance.data.get("api_token")
            self.fields["org_id"].initial = self.instance.data.get("org_id")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = {
            "api_token": self.cleaned_data.get("api_token"),
            "org_id": self.cleaned_data.get("org_id"),
        }
        if commit:
            instance.save()
        return instance


class ConnectMSTeamsForm(forms.ModelForm):
    webhook_url = forms.CharField(max_length=500, required=True, label="Base URL")

    class Meta:
        model = MessageIntegration
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.data:
            self.fields["webhook_url"].initial = self.instance.data.get("webhook_url")

        self.fields["webhook_url"].widget.attrs.update(
            {"placeholder": "https://url.westus.logic.azure.com:443/workflows/..."}
        )

    def clean_webhook_url(self):
        url = self.cleaned_data.get("webhook_url")
        validator = URLValidator()
        try:
            validator(url)
        except ValidationError:
            raise forms.ValidationError("Invalid URL format.")
        return url

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = {"webhook_url": self.cleaned_data.get("webhook_url")}
        if commit:
            instance.save()
        return instance


class DataProviderForm(forms.ModelForm):
    modules = forms.MultipleChoiceField(choices=ModuleChoices.choices)

    class Meta:
        model = DataProvider
        fields = "__all__"


class FeedbackForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={"placeholder": "Type here your feedback or questions..."}),
        required=True,
    )


class RequestAccessForm(forms.Form):
    email = forms.EmailField(required=True)


class RepositoryGroupForm(forms.ModelForm):
    rules = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.SelectMultiple,
        required=False,
    )

    class Meta:
        model = RepositoryGroup
        fields = [
            "name",
            "usage_category",
            "rules",
            "time_spent_coding_percentage",
            "potential_productivity_improvement_label",
            "potential_productivity_improvement_percentage",
            "max_genai_code_usage_percentage",
            "num_developers",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(RepositoryGroupForm, self).__init__(*args, **kwargs)
        current_org = self.request.current_organization
        self.fields["rules"].queryset = current_org.rule_set_non_global()
        self.fields["time_spent_coding_percentage"].label = "Estimated time coding"

        self.fields["potential_productivity_improvement_label"].choices = ProductivityImprovementChoices.choices
        self.fields["potential_productivity_improvement_label"].label = "Potential productivity improvement"
        self.fields["potential_productivity_improvement_label"].required = False

        self.fields["potential_productivity_improvement_percentage"].required = False

        self.fields["max_genai_code_usage_percentage"].label = "Min GenAI code usage for full gain"

    def clean_potential_productivity_improvement_percentage(self):
        # If the label is set to "Unselected", the value should be 0
        label = self.cleaned_data.get("potential_productivity_improvement_label")
        value = self.cleaned_data.get("potential_productivity_improvement_percentage")
        if label == ProductivityImprovementChoices.UNSELECTED:
            value = 0
        return value

    def save(self, commit=True):
        self.instance.organization = self.request.current_organization
        return super(RepositoryGroupForm, self).save(commit=commit)


class AuthorGroupForm(forms.ModelForm):
    rules = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.SelectMultiple,
        required=False,
    )

    class Meta:
        model = AuthorGroup
        fields = ["name", "team_type", "developer_type", "rules"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(AuthorGroupForm, self).__init__(*args, **kwargs)
        current_org = self.request.current_organization
        self.fields["rules"].queryset = current_org.rule_set_non_global()

        for field_name in ["team_type", "developer_type"]:
            self.fields[field_name].widget.attrs.update({"placeholder": self.fields[field_name].help_text})

    def save(self, commit=True):
        self.instance.organization = self.request.current_organization
        return super(AuthorGroupForm, self).save(commit=commit)


class RuleForm(forms.ModelForm):
    class Meta:
        model = Rule
        fields = ["name", "description", "condition_mode", "risk", "apply_organization"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(RuleForm, self).__init__(*args, **kwargs)
        self.conditions = RuleConditionFormSet(self.data or None, instance=self.instance)

    def clean(self):
        self.instance.organization = self.request.current_organization
        return super().clean()


class RuleConditionForm(forms.ModelForm):
    public_id = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = RuleCondition
        fields = ["code_type", "operator", "percentage"]

    def __init__(self, *args, **kwargs):
        super(RuleConditionForm, self).__init__(*args, **kwargs)
        self.fields["percentage"].widget.attrs.update({"min": "0", "max": "100"})
        if self.instance and self.instance.pk:
            self.fields["public_id"].initial = self.instance.public_id()


RuleConditionFormSet = inlineformset_factory(
    Rule,
    RuleCondition,
    form=RuleConditionForm,
    extra=1,
    min_num=1,
    max_num=10,
    validate_min=True,
    validate_max=True,
)


class MarkdownWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        rendered_message = markdown.markdown(value, extensions=["tables"]) if value is not None else "-"
        return f'<div style="white-space:pre; border: 1px solid #353535; border-radius:4px; padding:8px; overflow-x:auto;">{rendered_message}</div>'


class RepositoryPullRequestStatusCheckForm(forms.ModelForm):
    message_rendered = forms.CharField(
        label="Message (Rendered)",
        required=False,
        widget=MarkdownWidget(),
        help_text="NOTE: This does not 100% reflect how it'd look in the PR page.",
    )

    class Meta:
        fields = [
            "pull_request",
            "status_check_id",
            "status",
            "message",
            "message_rendered",
            "external_data",
        ]
        model = RepositoryPullRequestStatusCheck

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["message_rendered"].initial = self.instance.message


class AttestationExportForm(ExportForm):
    """Customized ExportForm for attestation to allow filtering by organization"""

    organization = forms.ModelChoiceField(queryset=Organization.objects.all(), required=False)


class SystemMessageForm(forms.ModelForm):
    class Meta:
        model = SystemMessage
        fields = "__all__"
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4, "cols": 40}),
        }


class CustomResetPasswordKeyForm(ResetPasswordKeyForm):
    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if self.user.check_password_history(password):
            raise ValidationError("You cannot reuse a previous password.")

        return password


class AuthorGroupAdminForm(forms.ModelForm):
    class Meta:
        model = AuthorGroup
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # only show rules that belong to the same organization
        rules_field = self.fields["rules"]
        if hasattr(self.instance, "organization"):
            rules_field.queryset = Rule.objects.filter(organization=self.instance.organization)
        else:
            rules_field.queryset = Rule.objects.none()
            rules_field.widget.attrs["disabled"] = "disabled"
            rules_field.help_text = "missing organization field"


class AuthorAdminForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # only show groups that belong to the same organization
        group_field = self.fields["group"]
        if hasattr(self.instance, "organization"):
            group_field.queryset = AuthorGroup.objects.filter(organization=self.instance.organization)
        else:
            group_field.queryset = RepositoryGroup.objects.none()
            group_field.widget.attrs["disabled"] = "disabled"
            group_field.help_text = "missing organization field"


class JiraProjectAdminForm(forms.ModelForm):
    class Meta:
        model = JiraProject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # only show groups that belong to the same organization
        repository_group_field = self.fields["repository_group"]
        if hasattr(self.instance, "organization"):
            repository_group_field.queryset = RepositoryGroup.objects.filter(organization=self.instance.organization)
        else:
            repository_group_field.queryset = RepositoryGroup.objects.none()
            repository_group_field.widget.attrs["disabled"] = "disabled"
            repository_group_field.help_text = "missing organization field"


class RepositoryGroupAdminForm(forms.ModelForm):
    class Meta:
        model = AuthorGroup
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # only show rules that belong to the same organization
        rules_field = self.fields["rules"]
        if hasattr(self.instance, "organization"):
            rules_field.queryset = Rule.objects.filter(organization=self.instance.organization)
        else:
            rules_field.queryset = Rule.objects.none()
            rules_field.widget.attrs["disabled"] = "disabled"
            rules_field.help_text = "missing organization field"
