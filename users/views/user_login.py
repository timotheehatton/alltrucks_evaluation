from django.conf import settings
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from common.useful.strapi import strapi_content


def get_content(request):
    lang = {'locale': request.LANGUAGE_CODE.lower()} if request.LANGUAGE_CODE.lower() in settings.AVAILABLE_LANGUAGES else {'locale': 'fr'}
    return strapi_content.get_content(
        pages=['login'],
        parameters=lang
    )


def user_login(request):
    page_content = get_content(request)
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                if user.user_type == 'technician':
                    return redirect('technician:stats')
                elif user.user_type == 'manager':
                    return redirect('manager:stats')
        except:
            pass
        return render(request, 'users/login/index.html', {
            'error': page_content['login']['login_error'],
            'page_content': page_content
        })
    else:
        return render(request, 'users/login/index.html', {
            'page_content': page_content
        })