from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from common.useful.strapi import strapi_content

User = get_user_model()


# def get_content(request):
#     lang = {'locale': request.LANGUAGE_CODE.lower()} if request.LANGUAGE_CODE.lower() in settings.AVAILABLE_LANGUAGES else {}
#     return strapi_content.get_content(
#         pages=['reset-password'],
#         parameters=lang
#     )


def resetPassword(request, uidb64, token):
    print('here', uidb64, token)
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        # page_content = get_content(request)
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
            # 'page_content': page_content
        })
    else:
        messages.error(request, 'The reset link is invalid!')
        return render(request, 'common/activate_account.html')