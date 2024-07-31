from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect, get_object_or_404
from .models import Company, User, Score
from common.views.forms import CompanyUserForm
from django.contrib import messages
from django.db.models import Q


class MyAdminSite(admin.AdminSite):
    site_header = 'Alltrucks AMCAT Admin'
    site_title = 'Workshops'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('workshops/', self.admin_view(self.companies_view), name='workshops'),
            path('users/', self.admin_view(self.users_view), name='users'),
            path('create-company/', self.admin_view(self.create_company_view), name='create_company'),
            path('user/<int:user_id>/', self.admin_view(self.single_user_view), name='single_user'),  
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
    

    def single_user_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        context = {
            'user': user,
        }
        return render(request, 'admin/users/single_user.html', context)


    def users_view(self, request):
        search_query = request.GET.get('search', '')
        user_type_filter = request.GET.get('user_type', '')
        company_country_filter = request.GET.get('country', '')

        users = User.objects.select_related('company').all()
        if search_query != '':
            users = users.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(company__name__icontains=search_query)
            )
        
        if user_type_filter and user_type_filter != 'ALL':
            users = users.filter(user_type=user_type_filter)

        if company_country_filter and company_country_filter != 'ALL':
            users = users.filter(company__country=company_country_filter)
        
        data = [{
            'id': user.id,
            'user_type': user.user_type,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'company_name': user.company.name if user.company else 'N/A',
            'company_country': user.company.country if user.company else 'N/A',
        } for user in users if user.is_superuser != True]

        return render(request, 'admin/users/index.html', {'users': data})


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
                        messages.error(request, f"{field}: {error}")
        else:
            form = CompanyUserForm()

        return render(request, 'admin/workshops/create_company.html', {'form': form})


admin_site = MyAdminSite(name='myadmin')