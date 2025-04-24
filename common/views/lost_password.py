from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from common.useful.email import email
from users.models import User


def lostPassword(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email_address = form.cleaned_data['email']
            user = User.objects.filter(email=email_address).first()
            if user:
                # Get email content
                # content = strapi_content.get_content(
                #     pages=['reset-password-email'],
                #     parameters={}
                # ).reset_password_email

                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))

                reset_link = f"{request.scheme}://{request.get_host()}/common/reset/{uid}/{token}/"
                # TODO: Translation -> GOOD
                email.send_email(
                    to_email=user.email,
                    subject='Reset your password',
                    title='Password Reset Request',
                    content='Please click the link below to reset your password:',
                    link=reset_link,
                    link_label='Reset password'
                )
                # TODO: Translation -> GOOD
                messages.success(request, 'A link to reset your password has been sent to your email.')
            else:
                # TODO: Translation -> GOOD
                messages.error(request, 'There is no user with that email address.')
        else:
            # TODO: Translation -> GOOD
            messages.error(request, 'Please enter a valid email address.')
    else:
        form = PasswordResetForm()
    return render(request, 'common/lost_password.html', {'form': form})