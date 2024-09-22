from django.urls import path

from .views import account, quiz, stats

app_name = 'technician'

urlpatterns = [
    path("stats", stats.index, name="stats"),
    path("quiz", quiz.index, name="quiz"),
    path("account", account.index, name="account"),
]