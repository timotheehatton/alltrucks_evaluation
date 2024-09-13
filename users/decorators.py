from django.http import HttpResponseForbidden
from functools import wraps

def technician_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("You are not authorized to view this page")
        if request.user.user_type != 'technician':
            return HttpResponseForbidden("You are not authorized to view this page")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def workshop_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("You are not authorized to view this page")
        if request.user.user_type != 'manager':
            return HttpResponseForbidden("You are not authorized to view this page")
        return view_func(request, *args, **kwargs)
    return _wrapped_view