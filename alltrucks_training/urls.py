from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from users.views import user_login
from users.admin import admin_site


urlpatterns = [
    path('admin/', admin_site.urls),
    path("technician/", include("technician.urls", namespace='technician')),
    path("workshop/", include("workshop.urls", namespace='workshop')),
    path("common/", include("common.urls", namespace='common')),
    path('login/', user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]