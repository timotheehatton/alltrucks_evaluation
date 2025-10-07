from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse
from common.useful.strapi import strapi_content


def get_content(request):
    return strapi_content.get_content(
        pages=['menu', 'account'],
        parameters={'locale': request.user.language.lower()}
    )

def changePassword(request):
    page_content = get_content(request)
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, page_content['account']['change_password_success'])
            return redirect(reverse(f'{request.user.user_type}:account'))
        else:
            messages.error(request, page_content['account']['change_password_error'])
    else:
        form = PasswordChangeForm(request.user)
    return render(
        request,
        f'{request.user.user_type}/account/index.html',
        {
            'password_form': form,
            'page_content': page_content,
        }
    )