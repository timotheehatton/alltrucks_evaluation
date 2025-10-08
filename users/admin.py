import collections
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LogoutView
from django.db.models import ExpressionWrapper, IntegerField, Max, Q, Sum, When, Case
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.useful.email import email
from common.useful.strapi import strapi_content
from common.views.forms import AdminUserForm, CompanyUserForm
from .models import Company, Score, User


class MyAdminSite(admin.AdminSite):
    site_header = 'Alltrucks AMCAT Admin'
    site_title = 'Workshops'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.companies_view), name='workshops'),
            path('workshop/<int:company_id>/', self.admin_view(self.single_company_view), name='single_workshop'),
            path('workshop/<int:company_id>/delete/', self.admin_view(self.delete_company_view), name='delete_workshop'),
            path('create-workshop/', self.admin_view(self.create_company_view), name='create_company'),
            path('users/', self.admin_view(self.users_view), name='users'),
            path('user/<int:user_id>/', self.admin_view(self.single_user_view), name='single_user'),
            path('admins/', self.admin_view(self.admins_view), name='admins'),
            path('create-admin/', self.admin_view(self.create_admin_view), name='create_admin'),
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
                'first_name': manager_user.first_name if manager_user else 'N/A',
                'last_name': manager_user.last_name if manager_user else 'N/A',
                'email': email,
                'country': company.country
            })
        context = dict(
            self.each_context(request),
            companies=companies_with_emails,
        )
        return render(request, 'admin/workshops/index.html', context)

    def single_company_view(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)
        company_users = User.objects.filter(company=company)
        last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))

        scores_by_category = Score.objects.filter(
            user__in=company_users,
            date__in=(score['last_date'] for score in last_dates)
        ).values('user__first_name', 'user__last_name', 'user__id', 'question_type').annotate(
            total_score=Sum('score'),
            success_percentage=ExpressionWrapper(
                (Sum('score') * 100) / Case(
                    *[When(question_type=qt, then=val) for qt, val in settings.QUESTION_NUMBER.items()],
                    default=1
                ),
                output_field=IntegerField()
            )
        )

        technician_scores = collections.defaultdict(dict)
        for item in scores_by_category:
            technician_scores[
                (f"{item['user__first_name'].capitalize()} {item['user__last_name'].upper()}", item['user__id'])][
                item['question_type']] = item['success_percentage']

        global_scores = {}
        for score in scores_by_category:
            global_scores[score['question_type']] = score['success_percentage']

        managers = company_users.filter(user_type='manager').order_by('last_name', 'first_name')
        technicians = company_users.filter(user_type='technician').order_by('last_name', 'first_name')

        return render(request, 'admin/workshops/single_workshop.html', {
            'technician_scores': dict(technician_scores),
            'global_scores': global_scores,
            'current_user': company,
            'managers': managers,
            'technicians': technicians,
        })

    def admins_view(self, request):
        admins = User.objects.filter(is_superuser=True).values()
        context = dict(
            self.each_context(request),
            admins=admins,
        )
        return render(request, 'admin/admins/index.html', context)

    def single_user_view(self, request, user_id):
        technician = get_object_or_404(User, id=user_id)
        
        if request.method == 'POST':
            # Handle password change
            if 'new_password' in request.POST:
                new_password = request.POST.get('new_password')
                confirm_password = request.POST.get('confirm_password')
                
                if new_password and new_password == confirm_password:
                    technician.set_password(new_password)
                    # Ensure username is synced with email for authentication
                    technician.username = technician.email
                    technician.save()
                    messages.success(request, f'Password updated successfully for {technician.email}')
                else:
                    messages.error(request, 'Passwords do not match or are empty.')
            
            # Handle activation status change
            if 'update_activation' in request.POST:
                is_active = request.POST.get('is_active') == 'on'
                technician.is_active = is_active
                technician.save()
                if is_active:
                    messages.success(request, f'User {technician.email} has been activated.')
                else:
                    messages.warning(request, f'User {technician.email} has been deactivated.')
            
            return redirect('admin:single_user', user_id=user_id)
        
        page_content = strapi_content.get_content(
            pages=['trainings'],
            parameters={'locale': technician.language.lower()}
        )
        last_datetime = Score.objects.filter(user=technician).aggregate(date=Max('date'))['date']
        scores_by_category = Score.objects.filter(user=technician, date=last_datetime).values('question_type').annotate(
            success_percentage=ExpressionWrapper(
                (Sum('score') * 100) / Case(
                    *[When(question_type=qt, then=val) for qt, val in settings.QUESTION_NUMBER.items()],
                    default=1
                ),
                output_field=IntegerField()
            )
        )
        scores_by_category = [
            {
                'question_type': score['question_type'],
                'success_percentage': score['success_percentage'],
                'trainings': [item for item in page_content['trainings'] if
                              item['training_category'] == score['question_type']]
            }
            for score in scores_by_category
        ]

        context = {
            'scores_by_category': scores_by_category,
            'page_content': page_content,
            'current_user': technician
        }
        return render(request, 'admin/users/single_user.html', context)

    def users_view(self, request):
        search_query = request.GET.get('search', '')
        user_type_filter = request.GET.get('user_type', '')
        company_country_filter = request.GET.get('country', '')
        users = User.objects.select_related('company').prefetch_related('score_set').all()

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
        data = []
        for user in users:
            if not user.is_superuser:
                has_completed_test = user.score_set.exists()
                data.append({
                    'id': user.id,
                    'user_type': user.user_type,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'company_name': user.company.name,
                    'company_country': user.company.country,
                    'language': user.language,
                    'has_completed_test': has_completed_test,
                    'has_activated': user.is_active,
                })

        return render(request, 'admin/users/index.html', {'users': data})

    def send_activation_email(self, request, user, content):
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reversed_url = reverse('common:activate-account', kwargs={'uidb64': uid, 'token': token})
        activation_link = settings.SITE_DOMAIN.rstrip('/') + reversed_url
        email.send_email(
            to_email=user.email,
            subject=content['email']['title'],
            title=content['email']['title'],
            content=content['email']['content'],
            link=activation_link,
            link_label=content['email']['title']
        )

    def create_company_view(self, request):
        if request.method == 'POST':
            form = CompanyUserForm(request.POST)
            if form.is_valid():
                company = form.save()
                manager_email = form.cleaned_data['manager_email']

                if User.objects.filter(username=manager_email).exists():
                    messages.error(request, f'A user with email {manager_email} already exists.')
                    company.delete()
                    return render(request, 'admin/workshops/create_company.html', {'form': form})
                
                try:
                    manager_user = User.objects.create_user(
                        username=manager_email,
                        email=manager_email,
                        first_name=form.cleaned_data['manager_first_name'],
                        last_name=form.cleaned_data['manager_last_name'],
                        user_type='manager',
                        language=company.country,
                        company=company,
                        ct_number=form.cleaned_data['manager_ct_number'],
                        is_active=False
                    )
                    content = strapi_content.get_content(
                        pages=['email'],
                        parameters={'locale': company.country.lower()}
                    )
                    manager_user.save()
                    self.send_activation_email(request, manager_user, content)

                    technician_emails = []
                    i = 1
                    while f'technician_first_name_{i}' in request.POST:
                        technician_email = request.POST[f'technician_email_{i}']
                        if User.objects.filter(username=technician_email).exists():
                            messages.error(request, f'A user with email {technician_email} already exists.')
                            manager_user.delete()
                            company.delete()
                            return render(request, 'admin/workshops/create_company.html', {'form': form})
                        technician_emails.append((i, technician_email))
                        i += 1

                    for idx, technician_email in technician_emails:
                        technician_user = User.objects.create_user(
                            username=technician_email,
                            email=technician_email,
                            first_name=request.POST[f'technician_first_name_{idx}'],
                            last_name=request.POST[f'technician_last_name_{idx}'],
                            user_type='technician',
                            language=company.country,
                            company=company,
                            ct_number=request.POST[f'technician_ct_number_{idx}'],
                            is_active=False
                        )
                        technician_user.save()
                        self.send_activation_email(request, technician_user, content)

                    messages.success(request,
                                     'Company and users accounts successfully created, users will received an email to define their password.')
                    return redirect('admin:workshops')
                    
                except Exception as e:
                    messages.error(request, f'Error creating users: {str(e)}')
                    company.delete()
                    return render(request, 'admin/workshops/create_company.html', {'form': form})
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
                user.username = user.email
                user.is_staff = True
                user.is_superuser = True
                user.set_password(admin_form.cleaned_data['password'])
                user.save()
                return redirect('admin:admins')
            else:
                for field, errors in admin_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            admin_form = AdminUserForm()
        return render(request, 'admin/admins/create_admin.html', {'admin_form': admin_form})

    def delete_company_view(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)
        
        if request.method == 'POST':
            # Delete all users associated with the company (this will cascade delete scores)
            User.objects.filter(company=company).delete()
            # Delete the company
            company_name = company.name
            company.delete()
            messages.success(request, f'Workshop "{company_name}" and all associated users have been deleted.')
            return redirect('admin:workshops')
        
        # This shouldn't happen as we'll use JavaScript confirmation
        return redirect('admin:single_workshop', company_id=company_id)


admin_site = MyAdminSite(name='myadmin')
