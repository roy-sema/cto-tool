from django.urls import path

from compass.team.views import TeamView

urlpatterns = [path("", TeamView.as_view(), name="compass_api_team")]
