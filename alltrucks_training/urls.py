from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from users.admin import admin_site
from users.views import user_login

urlpatterns = [
    path('admin/', admin_site.urls),
    path("technician/", include("technician.urls", namespace='technician')),
    path("manager/", include("manager.urls", namespace='manager')),
    path("common/", include("common.urls", namespace='common')),
    path('login/', user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]