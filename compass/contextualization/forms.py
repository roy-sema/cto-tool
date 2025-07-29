from django import forms

from .models import MessageFilter, RepositoryGroup


class MessageFilterForm(forms.ModelForm):
    class Meta:
        model = MessageFilter
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # only show repository groups that belong to the same organization
        repo_groups_field = self.fields["repository_groups"]
        if hasattr(self.instance, "organization"):
            repo_groups_field.queryset = RepositoryGroup.objects.filter(organization=self.instance.organization)
        else:
            repo_groups_field.queryset = RepositoryGroup.objects.none()
            repo_groups_field.widget.attrs["disabled"] = "disabled"
            repo_groups_field.help_text = "select an organization and save to enable this field"
