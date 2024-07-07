from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from .models import Company, User, Score
from common.views.forms import CompanyUserForm
from django.contrib import messages


class MyAdminSite(admin.AdminSite):
    site_header = 'Alltrucks AMCAT Admin'
    site_title = 'Workshops'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.companies_view), name='index'),
            path('create-company/', self.admin_view(self.create_company_view), name='create_company'),
        ]
        return custom_urls + urls

    def companies_view(self, request):
        companies = Company.objects.all()
        companies_with_emails = []

        for company in companies:
            workshop_user = User.objects.filter(company=company, user_type='workshop').first()
            email = workshop_user.email if workshop_user else 'N/A'
            companies_with_emails.append({
                'id': company.id,
                'name': company.name,
                'manager': f'{workshop_user.first_name} {workshop_user.last_name}' if workshop_user else 'N/A',
                'email': email,
                'country': company.country
            })

        context = dict(
            self.each_context(request),
            companies=companies_with_emails,
        )
        return render(request, 'admin/workshops/index.html', context)

    def create_company_view(self, request):
        if request.method == 'POST':
            form = CompanyUserForm(request.POST)
            if form.is_valid():
                company = form.save()
                workshop_user = User.objects.create_user(
                    username=form.cleaned_data['workshop_email'],
                    email=form.cleaned_data['workshop_email'],
                    first_name=form.cleaned_data['workshop_first_name'],
                    last_name=form.cleaned_data['workshop_last_name'],
                    user_type='workshop',
                    language=company.country,
                    company=company,
                    ct_number=form.cleaned_data['workshop_ct_number']
                )
                workshop_user.save()

                i = 1
                while f'technician_first_name_{i}' in request.POST:
                    print(request.POST[f'technician_email_{i}'])
                    technician_user = User.objects.create_user(
                        username=request.POST[f'technician_email_{i}'],
                        email=request.POST[f'technician_email_{i}'],
                        first_name=request.POST[f'technician_first_name_{i}'],
                        last_name=request.POST[f'technician_last_name_{i}'],
                        user_type='technician',
                        company=company,
                        ct_number=request.POST[f'technician_ct_number_{i}']
                    )
                    technician_user.save()
                    i += 1

                return redirect('admin:index')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        print(f"{field}: {error}")
                        messages.error(request, f"{field}: {error}")
        else:
            form = CompanyUserForm()

        return render(request, 'admin/workshops/create_company.html', {'form': form})


admin_site = MyAdminSite(name='myadmin')