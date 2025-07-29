import posthog
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    request.reset_cookies = True

    posthog.capture(user.email, event="login_staff" if user.is_staff else "login_user")
