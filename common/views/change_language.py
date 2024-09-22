from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import LanguageForm


def changeLanguage(request):
    if request.method == 'POST':
        form = LanguageForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your language was successfully updated!')
            return redirect(reverse(f'{request.user.user_type}:account'))
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = LanguageForm(instance=request.user)

    return render(request, f'{request.user.user_type}/account/index.html', {'language_form': form})