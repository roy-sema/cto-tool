"""
URL configuration for cto_tool project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.defaults import bad_request as django_bad_request
from django.views.defaults import page_not_found, permission_denied
from django.views.defaults import server_error as django_server_error
from rest_framework.exceptions import bad_request as drf_bad_request
from rest_framework.exceptions import server_error as drf_server_error

from . import views

if not settings.DEBUG:
    admin.autodiscover()
    # https://docs.allauth.org/en/dev/common/admin.html
    admin.site.login = secure_admin_login(admin.site.login)


def custom_bad_request(request, exception, *args, **kwargs):
    if "/api/" in request.path:
        return drf_bad_request(request, exception, *args, **kwargs)
    return django_bad_request(request, exception, *args, **kwargs)


def custom_server_error(request, *args, **kwargs):
    if "/api/" in request.path:
        return drf_server_error(request, *args, **kwargs)
    return django_server_error(request, *args, **kwargs)


handler400 = "cto_tool.urls.custom_bad_request"
handler500 = "cto_tool.urls.custom_server_error"

urlpatterns = [
    path("admin-does-not-live-here/", admin.site.urls),
    path("compass/", include("compass.urls")),
    path("", include("mvp.urls")),
    path("health-check/", views.health_check, name="health_check"),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("api/", include("api.urls")),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]


if settings.DEBUG:
    urlpatterns += [
        path("403/", lambda request: permission_denied(request, None)),
        path("404/", lambda request: page_not_found(request, None)),
        path("500/", lambda request: django_server_error(request)),
        path("__debug__/", include("debug_toolbar.urls")),
        path("silk/", include("silk.urls", namespace="silk")),
    ]
