from django.contrib import messages
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from common.useful.strapi import strapi_content

from common.useful.email import email
from users.models import User

def get_content(request):
    lang = {'locale': request.LANGUAGE_CODE.lower()} if request.LANGUAGE_CODE.lower() in settings.AVAILABLE_LANGUAGES else {}
    return strapi_content.get_content(
        pages=['login'],
        parameters=lang
    )


def lostPassword(request):
    page_content = get_content(request)
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email_address = form.cleaned_data['email']
            user = User.objects.filter(email=email_address).first()
            if user:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))

                reset_link = f"{request.scheme}://{request.get_host()}/common/reset/{uid}/{token}/"
                email.send_email(
                    to_email=user.email,
                    subject=page_content['login']['lostpassword_email_subject'],
                    title=page_content['login']['lostpassword_email_title'],
                    content=page_content['login']['lostpassword_email_content'],
                    link=reset_link,
                    link_label=page_content['login']['lostpassword_email_link_label']
                )
                messages.success(request, page_content['login']['lostpassword_email_sent_success'])
            else:
                messages.error(request, page_content['login']['lostpassword_email_error_no_user'])
        else:
            messages.error(request, page_content['login']['lostpassword_email_error_email_invalid'])
    else:
        form = PasswordResetForm()
    return render(
        request,
        'common/lost_password.html',
        {
            'form': form,
            'page_content': page_content
        }
    )
