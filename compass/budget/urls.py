from django.urls import path

from compass.budget.views import BudgetView

urlpatterns = [path("", BudgetView.as_view(), name="compass_api_budget")]
