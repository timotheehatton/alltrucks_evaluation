from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.http import Http404
from common.useful.strapi import strapi_content

User = get_user_model()

def get_content(user):
    return strapi_content.get_content(
        pages=['activate-account'],
        parameters={'locale': user.language.lower()}
    )


def resetPassword(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        page_content = get_content(user)
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                return redirect('login')
            else:
                for _, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
        else:
            form = SetPasswordForm(user)
        return render(request, 'common/activate_account.html', {
            'form': form,
            'page_content': page_content,
        })
    else:
        raise Http404("Account activation not found")