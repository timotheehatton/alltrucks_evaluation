from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from users.decorators import technician_required
from common.views.forms import LanguageForm
from common.content.strapi import strapi_content


@technician_required
def index(request):
    page_content = strapi_content.get_content(page='account', parameters={'local': 'fr'})

    password_form = PasswordChangeForm(request.user)
    language_form = LanguageForm(instance=request.user)
    return render(request, 'workshop/account/index.html', {
        'password_form': password_form,
        'language_form': language_form,
        'page_content': page_content['data']['attributes']
    })