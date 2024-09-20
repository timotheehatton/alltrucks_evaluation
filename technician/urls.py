from django.urls import path

from .views import stats
from .views import account
from .views import quiz

app_name = 'technician'

urlpatterns = [
    path("stats", stats.index, name="stats"),
    path("quiz", quiz.index, name="quiz"),
    path("account", account.index, name="account"),
]