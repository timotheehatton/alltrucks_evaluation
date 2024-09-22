from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse

from common.useful.strapi import strapi_content
from common.views.forms import LanguageForm
from users.decorators import technician_required
from users.models import User


def get_content(request):
    return strapi_content.get_content(
        pages=['account', 'menu'],
        parameters={'locale': request.user.language.lower()}
    )


@technician_required
def index(request):
    manager = User.objects.filter(company=request.user.company, user_type='manager').first()
    password_form = PasswordChangeForm(request.user)
    language_form = LanguageForm(instance=request.user)
    return render(request, 'workshop/account/index.html', {
        'password_form': password_form,
        'language_form': language_form,
        'page_content': get_content(request),
        'manager': manager
    })