from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode

User = get_user_model()

def activateAccount(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                user.is_active = True
                user.save()
                login(request, user)
                if user.user_type == 'manager':
                    return redirect('workshop:technicians')
                else:
                    return redirect('technician:stats')
        else:
            form = SetPasswordForm(user)
        return render(request, 'common/activate_account.html', {'form': form})
    else:
        messages.error(request, 'Activation link is invalid!')
        return render(request, 'common/activation_invalid.html')