from django.urls import path

from . import views

app_name = "production_tracker" 

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("create/", views.ProductionCreateView.as_view(), name="create"),
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    # path("<int:pk>/update/", views.ProductionUpdateView.as_view(), name="update"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("productions/", views.ProductionsListView.as_view(), name="productions"),  # Add this line
    path("dailies/", views.ProductionsListView.as_view(), name="dailies"),  # Add this line
]