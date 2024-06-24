from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CompanyUserForm
from users.models import User

@login_required
def createCompany(request):
    if request.method == 'POST':
        form = CompanyUserForm(request.POST)
        if form.is_valid():
            # Create the company
            company = form.save()

            # Create the workshop user
            workshop_user = User.objects.create_user(
                username=form.cleaned_data['workshop_email'],
                email=form.cleaned_data['workshop_email'],
                first_name=form.cleaned_data['workshop_first_name'],
                last_name=form.cleaned_data['workshop_last_name'],
                user_type='workshop',
                company=company,
                ct_number=form.cleaned_data['workshop_ct_number']
            )
            workshop_user.save()

            # Create the technician users
            technician_index = 1
            while f'technician_first_name_{technician_index}' in request.POST:
                technician_user = User.objects.create_user(
                    username=request.POST[f'technician_email_{technician_index}'],
                    email=request.POST[f'technician_email_{technician_index}'],
                    password=request.POST[f'technician_password_{technician_index}'],
                    first_name=request.POST[f'technician_first_name_{technician_index}'],
                    last_name=request.POST[f'technician_last_name_{technician_index}'],
                    user_type='technician',
                    company=company,
                    ct_number=request.POST[f'technician_ct_number_{technician_index}']
                )
                technician_user.save()
                technician_index += 1

            return redirect('admin:index')
    else:
        form = CompanyUserForm()

    return render(request, 'admin/workshops/create_company.html', {'form': form})