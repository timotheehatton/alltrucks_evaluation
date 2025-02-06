from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse


def changePassword(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            # TODO: Translation -> GOOD
            messages.success(request, 'Your password was successfully updated!')
            return redirect(reverse(f'{request.user.user_type}:account'))
        else:
            # TODO: Translation -> GOOD
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, f'{request.user.user_type}/account/index.html', {'password_form': form})