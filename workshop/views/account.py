from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from users.decorators import workshop_required
from common.views.forms import LanguageForm
from common.useful.strapi import strapi_content


def get_content(request):
    return strapi_content.get_content(
        pages=['account', 'menu'],
        parameters={'locale': request.user.language.lower()}
    )


@workshop_required
def index(request):
    password_form = PasswordChangeForm(request.user)
    language_form = LanguageForm(instance=request.user)
    return render(request, 'workshop/account/index.html', {
        'password_form': password_form,
        'language_form': language_form,
        'page_content': get_content(request),
    })