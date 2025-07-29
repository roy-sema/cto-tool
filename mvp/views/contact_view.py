from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import generic

from mvp.forms import FeedbackForm
from mvp.services import EmailService


class ContactView(LoginRequiredMixin, generic.CreateView):
    form_class = FeedbackForm
    template_name = "mvp/contact/main.html"

    def get(self, request):
        form = FeedbackForm()

        message = request.GET.get("message")
        if message:
            form.fields["message"].initial = message

        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = self.form_class(request.POST)

        if form.is_valid():
            current_org = request.current_organization
            user = request.user
            self.send_support_mail(current_org, user, form.cleaned_data["message"])

            messages.success(request, "Your message has been sent!")
            return redirect("contact")

        return render(request, self.template_name, {"form": form})

    def send_support_mail(self, organization, user, message):
        EmailService.send_email(
            f"{settings.APP_NAME} Contact",
            f"Contact from '{user.get_full_name()} <{user.email}>' at organization '{organization.name}':\n\n{message}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.SUPPORT_EMAIL],
        )
