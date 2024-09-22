from django.urls import path

from .views import account, details, stats, technicians

app_name = 'workshop'

urlpatterns = [
    path("stats", stats.index, name="stats"),
    path("technicians", technicians.index, name="technicians"),
    path("account", account.index, name="account"),
    path('technician/<int:id>/', details.index, name='details'),
]