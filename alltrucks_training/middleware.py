from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/':
            if not request.user.is_authenticated:
                return redirect(settings.LOGIN_URL)
            else:
                if request.user.user_type == 'technician':
                    return redirect(reverse('technician:stats'))
                elif request.user.user_type == 'manager':
                    return redirect(reverse('manager:stats'))
                
        
        response = self.get_response(request)
        return response