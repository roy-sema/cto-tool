from django.urls import path

from compass.roadmap.views import RoadmapFiltersView, RoadmapView

urlpatterns = [
    path("", RoadmapView.as_view(), name="compass_api_roadmap"),
    path("filters/", RoadmapFiltersView.as_view(), name="compass_api_roadmap_filters"),
]
