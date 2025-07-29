from django.conf import settings

from mvp.models import SystemMessage


def active_system_messages(request):
    # Because we use SQL for cache, the number of queries will be the same, so skip caching
    messages = SystemMessage.objects.active()
    return {"active_system_messages": messages}


def global_settings(request):
    """
    Define here settings that need to be available in every view.
    """
    return {
        "APP_NAME": settings.APP_NAME,
    }


def show_initiatives_menu(request):
    if not request.user.is_authenticated:
        return {"show_initiatives_menu": False}

    if not hasattr(request, "current_organization") or request.current_organization is None:
        return {"show_initiatives_menu": False}

    org_name = request.current_organization.name

    if settings.DEBUG:
        feature_enabled = True
    else:
        feature_enabled = org_name == "Sema-All"

    return {"show_initiatives_menu": feature_enabled}
