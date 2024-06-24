from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from .models import Company, User, Score
from common.views.forms import CompanyUserForm

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
                form.save()
                return redirect('admin:index')
        else:
            form = CompanyUserForm()

        context = dict(
            self.each_context(request),
            form=form,
        )
        return render(request, 'admin/workshops/create_company.html', context)

admin_site = MyAdminSite(name='myadmin')

# Register your models with this custom admin site
# admin_site.register(User)
admin_site.register(Company)
# admin_site.register(Score)