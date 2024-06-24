from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            login_url = reverse('login')
            if not request.path.startswith(login_url) and not request.path.startswith('/admin/login'):
                return redirect(settings.LOGIN_URL)

        response = self.get_response(request)
        return response