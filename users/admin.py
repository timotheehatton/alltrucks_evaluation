from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect, get_object_or_404
from .models import Company, User, Score
from common.views.forms import CompanyUserForm
from common.views.forms import AdminUserForm
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.views import LogoutView


class MyAdminSite(admin.AdminSite):
    site_header = 'Alltrucks AMCAT Admin'
    site_title = 'Workshops'


    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('workshops/', self.admin_view(self.companies_view), name='workshops'),
            path('users/', self.admin_view(self.users_view), name='users'),
            path('create-company/', self.admin_view(self.create_company_view), name='create_company'),
            path('admins/', self.admin_view(self.admins_view), name='admins'),
            path('create-admin/', self.admin_view(self.create_admin_view), name='create_admin'),
            path('user/<int:user_id>/', self.admin_view(self.single_user_view), name='single_user'),
            path('logout/', LogoutView.as_view(), name='logout'),
        ]
        return custom_urls + urls


    def companies_view(self, request):
        companies = Company.objects.all()
        companies_with_emails = []
        for company in companies:
            manager_user = User.objects.filter(company=company, user_type='manager').first()
            email = manager_user.email if manager_user else 'N/A'
            companies_with_emails.append({
                'id': company.id,
                'name': company.name,
                'manager': f'{manager_user.first_name} {manager_user.last_name}' if manager_user else 'N/A',
                'email': email,
                'country': company.country
            })
        context = dict(
            self.each_context(request),
            companies=companies_with_emails,
        )
        return render(request, 'admin/workshops/index.html', context)


    def admins_view(self, request):
        admins = User.objects.filter(is_superuser=True).values()
        context = dict(
            self.each_context(request),
            admins=admins,
        )
        return render(request, 'admin/admins/index.html', context)
    

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
                manager_user = User.objects.create_user(
                    username=form.cleaned_data['manager_email'],
                    email=form.cleaned_data['manager_email'],
                    first_name=form.cleaned_data['manager_first_name'],
                    last_name=form.cleaned_data['manager_last_name'],
                    user_type='manager',
                    language=company.country,
                    company=company,
                    ct_number=form.cleaned_data['manager_ct_number']
                )
                manager_user.save()
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
                return redirect('admin:workshops')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            form = CompanyUserForm()
        return render(request, 'admin/workshops/create_company.html', {'form': form})


    def create_admin_view(self, request):
        if request.method == 'POST':
            admin_form = AdminUserForm(request.POST)
            if admin_form.is_valid():
                user = admin_form.save(commit=False)
                user.is_staff = True
                user.is_superuser = True
                user.save()
                return redirect('admin:admins')
            else:
                for field, errors in admin_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            admin_form = AdminUserForm()
        return render(request, 'admin/admins/create_admin.html', {'admin_form': admin_form})


admin_site = MyAdminSite(name='myadmin')