import collections
import csv
import re

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LogoutView
from django.db.models import ExpressionWrapper, IntegerField, Max, Q, Sum, When, Case
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.useful.email import email
from common.useful.strapi import strapi_content
from common.views.forms import AdminUserForm, CompanyUserForm
from mail_parser.models import (
    AutoResponderConfig,
    InboundWebhook,
    KnowledgeBaseCase,
    KnowledgeBaseFile,
    OutboundEmail,
)
from mail_parser.services.knowledge_base import (
    delete_case_from_openai,
    upload_case_to_openai,
)
from .models import Company, Score, User


def _format_response_time(seconds):
    """Return (value_str, unit_str) chosen so the KPI tile reads naturally."""
    if seconds <= 0:
        return '—', ''
    if seconds < 1:
        return f'{seconds * 1000:.0f}', 'ms'
    if seconds < 60:
        return f'{seconds:.0f}', 's'
    if seconds < 3600:
        return f'{seconds / 60:.1f}', 'min'
    return f'{seconds / 3600:.1f}', 'h'


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
            path('user/<int:user_id>/delete/', self.admin_view(self.delete_user_view), name='delete_user'),
            path('admins/', self.admin_view(self.admins_view), name='admins'),
            path('admin/<int:admin_id>/send-reset-password/', self.admin_view(self.send_admin_reset_password_view), name='send_admin_reset_password'),
            path('create-admin/', self.admin_view(self.create_admin_view), name='create_admin'),
            path('download-content/', self.admin_view(self.download_strapi_content_view), name='download_content'),
            path('webhooks/', self.admin_view(self.webhooks_view), name='webhooks'),
            path('webhooks/<int:webhook_id>/', self.admin_view(self.webhook_detail_view), name='webhook_detail'),
            path('webhooks/<int:webhook_id>/generate/', self.admin_view(self.webhook_generate_view), name='webhook_generate'),
            path('auto-responder-config/', self.admin_view(self.auto_responder_config_view), name='auto_responder_config'),
            path('knowledge-base/', self.admin_view(self.kb_page_view), name='knowledge_base'),
            path('knowledge-base/cases/', self.admin_view(self.kb_cases_json_view), name='kb_cases_json'),
            path('knowledge-base/cases/create/', self.admin_view(self.kb_case_create_view), name='kb_case_create'),
            path('knowledge-base/cases/<int:case_id>/', self.admin_view(self.kb_case_detail_view), name='kb_case_detail'),
            path('knowledge-base/cases/<int:case_id>/edit/', self.admin_view(self.kb_case_edit_view), name='kb_case_edit'),
            path('knowledge-base/cases/<int:case_id>/delete/', self.admin_view(self.kb_case_delete_view), name='kb_case_delete'),
            path('stats/', self.admin_view(self.amcat_stats_view), name='amcat_stats'),
            path('training-stats/', self.admin_view(self.training_stats_view), name='training_stats'),
            path('logout/', LogoutView.as_view(), name='logout'),
        ]
        return custom_urls + urls

    def companies_view(self, request):
        search_query = request.GET.get('search', '')
        country_filter = request.GET.get('country', '')

        companies = Company.objects.all()

        if country_filter and country_filter != 'ALL':
            companies = companies.filter(country=country_filter)

        if search_query != '':
            companies = companies.filter(
                Q(name__icontains=search_query) |
                Q(city__icontains=search_query) |
                Q(cu_number__icontains=search_query)
            )

        companies_with_emails = []
        for company in companies:
            manager_user = User.objects.filter(company=company, user_type='manager').first()
            email = manager_user.email if manager_user else 'N/A'
            companies_with_emails.append({
                'id': company.id,
                'name': company.name,
                'city': company.city,
                'country': company.country,
                'cu_number': company.cu_number,
                'first_name': manager_user.first_name if manager_user else 'N/A',
                'last_name': manager_user.last_name if manager_user else 'N/A',
                'email': email,
            })
        context = dict(
            self.each_context(request),
            companies=companies_with_emails,
        )
        return render(request, 'admin/workshops/index.html', context)

    def single_company_view(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)

        if request.method == 'POST':
            if 'update_workshop_info' in request.POST:
                company_name = request.POST.get('company_name')
                city = request.POST.get('city')
                cu_number = request.POST.get('cu_number')
                country = request.POST.get('country')

                company.name = company_name
                company.city = city
                company.cu_number = cu_number
                company.country = country
                company.save()
                messages.success(request, f'Workshop information updated successfully.')
                return redirect('admin:single_workshop', company_id=company_id)

            if 'add_user_to_workshop' in request.POST:
                user_type = request.POST.get('user_type')
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                email = request.POST.get('email', '').lower().strip()
                ct_number = request.POST.get('ct_number')

                if User.objects.filter(email=email).exists():
                    messages.error(request, f'A user with email {email} already exists.')
                else:
                    try:
                        new_user = User.objects.create_user(
                            username=email,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            user_type=user_type,
                            language=company.country,
                            company=company,
                            ct_number=ct_number,
                            is_active=False
                        )
                        content = strapi_content.get_content(
                            pages=['email'],
                            parameters={'locale': company.country.lower()}
                        )
                        new_user.save()
                        self.send_activation_email(request, new_user, content)
                        messages.success(request, f'{user_type.capitalize()} "{first_name} {last_name}" has been added successfully.')
                    except Exception as e:
                        messages.error(request, f'Error creating user: {str(e)}')

                return redirect('admin:single_workshop', company_id=company_id)

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

        workshop_users = []
        for user in company_users.order_by('user_type', 'last_name', 'first_name'):
            user_data = user
            if user.user_type == 'technician':
                user_data.has_completed_test = Score.objects.filter(user=user).exists()
            else:
                user_data.has_completed_test = False
            workshop_users.append(user_data)

        return render(request, 'admin/workshops/single_workshop.html', {
            'technician_scores': dict(technician_scores),
            'global_scores': global_scores,
            'current_user': company,
            'managers': managers,
            'technicians': technicians,
            'workshop_users': workshop_users,
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
            # Handle user info update
            if 'update_user_info' in request.POST:
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                email = request.POST.get('email', '').lower().strip()
                ct_number = request.POST.get('ct_number')
                language = request.POST.get('language')

                if User.objects.filter(email=email).exclude(id=user_id).exists():
                    messages.error(request, f'A user with email {email} already exists.')
                else:
                    technician.first_name = first_name
                    technician.last_name = last_name
                    technician.email = email
                    technician.username = email
                    technician.ct_number = ct_number
                    technician.language = language
                    technician.save()
                    messages.success(request, f'User information updated successfully.')

            # Handle password change
            if 'new_password' in request.POST:
                new_password = request.POST.get('new_password')
                confirm_password = request.POST.get('confirm_password')

                if new_password and new_password == confirm_password:
                    technician.set_password(new_password)
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

        # Generate activation link for manual sharing
        token = default_token_generator.make_token(technician)
        uid = urlsafe_base64_encode(force_bytes(technician.pk))
        reversed_url = reverse('common:activate-account', kwargs={'uidb64': uid, 'token': token})
        activation_link = settings.SITE_DOMAIN.rstrip('/') + reversed_url

        context = {
            'scores_by_category': scores_by_category,
            'page_content': page_content,
            'current_user': technician,
            'activation_link': activation_link
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
            # TODO: translation
            link_label=content['email']['title']
        )

    def create_company_view(self, request):
        if request.method == 'POST':
            form = CompanyUserForm(request.POST)
            if form.is_valid():
                company = form.save()
                manager_email = form.cleaned_data['manager_email'].lower().strip()

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
                        technician_email = request.POST[f'technician_email_{i}'].lower().strip()
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
                user.email = user.email.lower().strip()
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

    def send_admin_reset_password_view(self, request, admin_id):
        admin_user = get_object_or_404(User, id=admin_id, is_superuser=True)

        if request.method == 'POST':
            try:
                token = default_token_generator.make_token(admin_user)
                uid = urlsafe_base64_encode(force_bytes(admin_user.pk))
                reset_link = f"{request.scheme}://{request.get_host()}/common/reset/{uid}/{token}/"

                email.send_email(
                    to_email=admin_user.email,
                    subject='Reset your password - Alltrucks AMCAT',
                    title='Password Reset',
                    content='You have requested to reset your password. Click the link below to set a new password.',
                    link=reset_link,
                    link_label='Reset Password'
                )
                messages.success(request, f'Password reset email sent to {admin_user.email}')
            except Exception as e:
                messages.error(request, f'Error sending email: {str(e)}')

        return redirect('admin:admins')

    def delete_company_view(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)

        if request.method == 'POST':
            User.objects.filter(company=company).delete()
            company_name = company.name
            company.delete()
            messages.success(request, f'Workshop "{company_name}" and all associated users have been deleted.')
            return redirect('admin:workshops')

        return redirect('admin:single_workshop', company_id=company_id)

    def delete_user_view(self, request, user_id):
        user_to_delete = get_object_or_404(User, id=user_id)
        company_id = user_to_delete.company.id

        if request.method == 'POST':
            user_name = f"{user_to_delete.first_name} {user_to_delete.last_name}"
            user_type = user_to_delete.user_type
            user_to_delete.delete()
            messages.success(request, f'{user_type.capitalize()} "{user_name}" has been deleted successfully.')
            return redirect('admin:single_workshop', company_id=company_id)

        return redirect('admin:single_workshop', company_id=company_id)

    def _fetch_all_strapi_content(self, content_type, language):
        """Fetch all paginated data from Strapi API"""
        api_url = f'{settings.STRAPI_URL}/api/{content_type}'
        headers = {'Authorization': f'Bearer {settings.STRAPI_EMAIL_TOKEN}'}
        all_data = []
        page = 1
        page_size = 100

        while True:
            params = {
                'locale': language,
                'pagination[page]': page,
                'pagination[pageSize]': page_size
            }

            response = requests.get(api_url, params=params, headers=headers)
            response.raise_for_status()

            result = response.json()
            data = result.get('data', [])

            if not data:
                break

            all_data.extend(data)

            # Check if there are more pages
            pagination = result.get('meta', {}).get('pagination', {})
            if page >= pagination.get('pageCount', 1):
                break

            page += 1

        return all_data

    def download_strapi_content_view(self, request):
        if request.method == 'POST':
            content_type = request.POST.get('content_type')
            language = request.POST.get('language')

            # Validate inputs
            if not content_type or not language:
                messages.error(request, 'Please select both content type and language')
                return render(request, 'admin/content/download.html', dict(self.each_context(request)))

            if content_type not in ['trainings', 'questions']:
                messages.error(request, 'Invalid content type')
                return render(request, 'admin/content/download.html', dict(self.each_context(request)))

            if language not in ['es', 'fr', 'pl', 'de', 'it']:
                messages.error(request, 'Invalid language')
                return render(request, 'admin/content/download.html', dict(self.each_context(request)))

            # Fetch ALL content from Strapi with pagination
            try:
                data = self._fetch_all_strapi_content(content_type, language)

                if not data:
                    messages.error(request, f'No content found for {content_type} in language {language}')
                    return render(request, 'admin/content/download.html', dict(self.each_context(request)))

                # Create CSV response
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{content_type}_{language}.csv"'

                writer = csv.writer(response)

                # Write headers (use keys from first item)
                headers = self._flatten_dict_keys(data[0])
                writer.writerow(headers)

                # Write data rows
                for item in data:
                    flattened = self._flatten_dict(item)
                    writer.writerow([flattened.get(key, '') for key in headers])

                return response

            except Exception as e:
                messages.error(request, f'Error fetching content: {str(e)}')
                return render(request, 'admin/content/download.html', dict(self.each_context(request)))

        context = dict(self.each_context(request))
        return render(request, 'admin/content/download.html', context)

    def webhooks_view(self, request):
        search_query = request.GET.get('search', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        status_filter = request.GET.get('status', '')

        webhooks = InboundWebhook.objects.all()

        if search_query:
            webhooks = webhooks.filter(
                Q(sender__icontains=search_query) |
                Q(recipient__icontains=search_query) |
                Q(subject__icontains=search_query)
            )
        if date_from:
            webhooks = webhooks.filter(received_at__date__gte=date_from)
        if date_to:
            webhooks = webhooks.filter(received_at__date__lte=date_to)
        if status_filter and status_filter != 'ALL':
            webhooks = webhooks.filter(status=status_filter)

        return render(request, 'admin/mail_parser/webhooks.html', {
            'webhooks': webhooks[:200],
        })

    def webhook_generate_view(self, request, webhook_id):
        if request.method != 'POST':
            return redirect('admin:webhook_detail', webhook_id=webhook_id)

        webhook = get_object_or_404(InboundWebhook, id=webhook_id)

        from mail_parser.signals import generate_ai_response
        success, error = generate_ai_response(webhook)

        if success:
            messages.success(request, 'AI response generated successfully.')
        else:
            messages.error(request, f'AI generation failed: {error}')

        return redirect('admin:webhook_detail', webhook_id=webhook_id)

    def webhook_detail_view(self, request, webhook_id):
        webhook = get_object_or_404(InboundWebhook, id=webhook_id)

        email_preview = None
        if webhook.ai_response:
            email_preview = self._build_email_preview(webhook)

        config = AutoResponderConfig.load()

        from mail_parser.signals import build_ai_user_message, is_documentation_only_request
        from mail_parser.system_prompt import get_system_prompt
        ai_user_message = build_ai_user_message(webhook)
        documentation_only = is_documentation_only_request(webhook)
        system_prompt = get_system_prompt()

        citations = []
        for c in (webhook.ai_citations or []):
            content = ''
            filename = c.get('filename') or ''
            m = re.search(r'case_0*(\d+)', filename)
            if m:
                case = KnowledgeBaseCase.objects.filter(case_number=int(m.group(1))).first()
                if case:
                    content = case.to_markdown()
            citations.append({**c, 'content': content})

        outbound_emails = list(webhook.outbound_emails.all().order_by('-created_at'))

        return render(request, 'admin/mail_parser/webhook_detail.html', {
            'webhook': webhook,
            'email_preview': email_preview,
            'config': config,
            'system_prompt': system_prompt,
            'ai_user_message': ai_user_message,
            'documentation_only': documentation_only,
            'citations_with_content': citations,
            'outbound_emails': outbound_emails,
        })

    @staticmethod
    def _build_email_preview(webhook):
        from mail_parser.signals import build_email_html

        no_link = 'javascript:void(0)'
        star_urls = {f'star_{i}_url': no_link for i in range(1, 6)}

        try:
            preview = build_email_html(webhook, star_urls=star_urls)
        except FileNotFoundError:
            return None

        # Disable star links in preview
        preview = preview.replace(
            'text-decoration: none; font-size: 36px;',
            'text-decoration: none; font-size: 36px; pointer-events: none; cursor: default;',
        )

        return preview

    def auto_responder_config_view(self, request):
        config = AutoResponderConfig.load()
        if request.method == 'POST':
            config.is_enabled = 'is_enabled' in request.POST
            config.openai_model = request.POST.get('openai_model', config.openai_model)
            config.is_email_enabled = 'is_email_enabled' in request.POST
            config.send_to_user = 'send_to_user' in request.POST
            config.test_emails = request.POST.get('test_emails', '')
            config.from_email = request.POST.get('from_email', config.from_email)
            config.save()
            messages.success(request, 'Auto-responder configuration updated.')
            return redirect('admin:auto_responder_config')
        return render(request, 'admin/mail_parser/auto_responder_config.html', {
            'config': config,
        })

    # =========================================================================
    # Knowledge Base — per-case CRUD
    # =========================================================================

    KB_LIST_FIELDS = (
        'id', 'case_number', 'manufacturer', 'series', 'subject',
        'country', 'system', 'synced_at', 'openai_file_id',
    )
    KB_FORM_FIELDS = (
        'manufacturer', 'series', 'subject', 'country', 'system',
        'request_type', 'engine', 'registration_date', 'vin', 'mileage',
        'axle_configuration', 'abs_configuration', 'installed_system',
        'resolution_summary', 'issue', 'resolution',
    )

    def kb_page_view(self, request):
        total = KnowledgeBaseCase.objects.count()
        synced = KnowledgeBaseCase.objects.exclude(openai_file_id='').count()
        return render(request, 'admin/mail_parser/knowledge_base.html', {
            'vector_store_id': getattr(settings, 'OPENAI_VECTOR_STORE_ID', '') or '',
            'total_cases': total,
            'synced_cases': synced,
        })

    def kb_cases_json_view(self, request):
        from django.http import JsonResponse
        try:
            offset = max(0, int(request.GET.get('offset', 0)))
        except ValueError:
            offset = 0
        try:
            limit = max(1, min(500, int(request.GET.get('limit', 100))))
        except ValueError:
            limit = 100
        search = (request.GET.get('search') or '').strip()

        qs = KnowledgeBaseCase.objects.all()
        if search:
            filters = (
                Q(subject__icontains=search) |
                Q(manufacturer__icontains=search) |
                Q(series__icontains=search) |
                Q(country__iexact=search) |
                Q(system__icontains=search)
            )
            if search.isdigit():
                filters |= Q(case_number=int(search))
            qs = qs.filter(filters)

        total = qs.count()
        rows = list(qs.order_by('case_number')[offset:offset + limit].values(*self.KB_LIST_FIELDS))
        for row in rows:
            row['synced_at'] = row['synced_at'].isoformat() if row['synced_at'] else None
            row['synced'] = bool(row['openai_file_id'])
        return JsonResponse({
            'cases': rows,
            'total': total,
            'has_more': offset + len(rows) < total,
            'next_offset': offset + len(rows),
        })

    def _kb_extract_form(self, request):
        data = {f: (request.POST.get(f) or '').strip() for f in self.KB_FORM_FIELDS}
        # request_type comes from one or more checkboxes; join with " / "
        rt_values = [v.strip() for v in request.POST.getlist('request_type') if v.strip()]
        if rt_values:
            data['request_type'] = ' / '.join(rt_values)
        else:
            data['request_type'] = 'Fehlersuche am Fahrzeug'
        return data

    def kb_case_create_view(self, request):
        from django.http import JsonResponse
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        data = self._kb_extract_form(request)
        if not data.get('subject'):
            return JsonResponse({'error': 'Subject is required.'}, status=400)
        if len(data.get('resolution', '')) < 50:
            return JsonResponse({'error': 'Resolution must be at least 50 characters.'}, status=400)

        next_no = (KnowledgeBaseCase.objects.aggregate(m=Max('case_number'))['m'] or 0) + 1
        case = KnowledgeBaseCase.objects.create(case_number=next_no, **data)

        ok, err = upload_case_to_openai(case)
        case.refresh_from_db()
        return JsonResponse({
            'case': self._kb_serialize(case),
            'sync_ok': ok,
            'sync_error': err,
        })

    def kb_case_detail_view(self, request, case_id):
        from django.http import JsonResponse
        case = get_object_or_404(KnowledgeBaseCase, id=case_id)
        return JsonResponse({'case': self._kb_serialize(case, include_full=True)})

    def kb_case_edit_view(self, request, case_id):
        from django.http import JsonResponse
        case = get_object_or_404(KnowledgeBaseCase, id=case_id)
        if request.method == 'GET':
            return JsonResponse({'case': self._kb_serialize(case, include_full=True)})
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        data = self._kb_extract_form(request)
        for field, value in data.items():
            setattr(case, field, value)
        case.save()

        ok, err = upload_case_to_openai(case)
        case.refresh_from_db()
        return JsonResponse({
            'case': self._kb_serialize(case, include_full=True),
            'sync_ok': ok,
            'sync_error': err,
        })

    def kb_case_delete_view(self, request, case_id):
        from django.http import JsonResponse
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        case = get_object_or_404(KnowledgeBaseCase, id=case_id)
        had_openai_file = bool(case.openai_file_id)
        case_number = case.case_number
        delete_case_from_openai(case)
        case.delete()
        return JsonResponse({
            'ok': True,
            'case_number': case_number,
            'openai_removed': had_openai_file,
        })

    # =========================================================================
    # Stats — global dashboard
    # =========================================================================

    def amcat_stats_view(self, request):
        from collections import Counter
        from datetime import timedelta
        from django.db.models import Avg, Count
        from django.db.models.functions import TruncDate
        from django.utils import timezone

        webhooks = InboundWebhook.objects.all()
        total = webhooks.count()
        with_citations = webhooks.exclude(ai_citations=[]).count()
        with_rating = webhooks.exclude(user_rating__isnull=True)
        avg_rating = with_rating.aggregate(a=Avg('user_rating'))['a'] or 0

        # Distribution par catégorie
        by_category = list(
            webhooks.values('category').annotate(c=Count('id')).order_by('-c')
        )

        # Distribution par langue (chaîne vide = "non détectée")
        by_language = list(
            webhooks.values('language').annotate(c=Count('id')).order_by('-c')
        )
        # Replace empty string with explicit label
        for row in by_language:
            if not row['language']:
                row['language'] = 'unknown'

        # Distribution de la nature de demande (hotline only)
        nature_counter = Counter()
        for nature in webhooks.filter(category='hotline').values_list('request_nature', flat=True):
            if not nature:
                nature_counter['(non précisée)'] += 1
                continue
            for item in nature:
                nature_counter[item] += 1

        # Volume par jour (derniers 30 jours)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_qs = (
            webhooks.filter(received_at__gte=thirty_days_ago)
            .annotate(d=TruncDate('received_at'))
            .values('d')
            .annotate(c=Count('id'))
            .order_by('d')
        )
        daily_volume = [
            {'date': row['d'].isoformat(), 'count': row['c']}
            for row in daily_qs
        ]

        # Top cas cités (toutes générations confondues)
        cited_counter = Counter()
        for citations in webhooks.exclude(ai_citations=[]).values_list('ai_citations', flat=True):
            for c in (citations or []):
                fn = c.get('filename', '')
                if fn:
                    cited_counter[fn] += 1
        top_cases = []
        for fn, n in cited_counter.most_common(10):
            label = fn
            content = ''
            m = re.search(r'case_0*(\d+)', fn)
            if m:
                kb_case = KnowledgeBaseCase.objects.filter(case_number=int(m.group(1))).first()
                if kb_case:
                    label = f'#{kb_case.case_number} · {kb_case.manufacturer or "—"} · {kb_case.subject[:50]}'
                    content = kb_case.to_markdown()
            top_cases.append({'label': label, 'count': n, 'content': content})

        # Note moyenne par jour (derniers 30 jours)
        rating_qs = (
            with_rating.filter(user_rated_at__gte=thirty_days_ago)
            .annotate(d=TruncDate('user_rated_at'))
            .values('d')
            .annotate(avg=Avg('user_rating'), c=Count('id'))
            .order_by('d')
        )
        rating_over_time = [
            {'date': row['d'].isoformat(), 'avg': float(row['avg']), 'count': row['c']}
            for row in rating_qs
        ]

        # Temps de réponse moyen — uniquement les webhooks où au moins un email
        # (admin ou end-user) a été envoyé avec succès. Source primaire :
        # OutboundEmail (un par destinataire). On retombe sur le legacy
        # email_sent_at pour les webhooks d'avant l'instrumentation.
        from django.db.models import Min as _Min
        outbound_first = dict(
            OutboundEmail.objects
            .filter(status__in=OutboundEmail.SUCCESS_STATUSES, sent_at__isnull=False)
            .values('webhook_id')
            .annotate(first=_Min('sent_at'))
            .values_list('webhook_id', 'first')
        )
        legacy_sent = dict(
            webhooks.exclude(email_sent_at__isnull=True)
            .values_list('id', 'email_sent_at')
        )
        first_send_by_webhook = {}
        for wid, t in outbound_first.items():
            first_send_by_webhook[wid] = t
        for wid, t in legacy_sent.items():
            cur = first_send_by_webhook.get(wid)
            if cur is None or t < cur:
                first_send_by_webhook[wid] = t

        received_by_webhook = dict(
            webhooks.filter(id__in=first_send_by_webhook.keys())
            .values_list('id', 'received_at')
        )
        deltas = [
            (first_send_by_webhook[wid] - received_by_webhook[wid]).total_seconds()
            for wid in first_send_by_webhook
            if wid in received_by_webhook
        ]
        avg_response_seconds = sum(deltas) / len(deltas) if deltas else 0
        avg_response_label, avg_response_unit = _format_response_time(avg_response_seconds)
        responded_count = len(deltas)

        context = {
            'total': total,
            'with_citations': with_citations,
            'citation_rate': round(100 * with_citations / total, 1) if total else 0,
            'rated_count': with_rating.count(),
            'avg_rating': round(avg_rating, 2),
            'languages_count': sum(1 for r in by_language if r['language'] not in ('unknown', '')),
            'by_category': by_category,
            'by_language': by_language,
            'nature_breakdown': sorted(
                ({'label': k, 'count': v} for k, v in nature_counter.items()),
                key=lambda x: -x['count'],
            ),
            'daily_volume': daily_volume,
            'top_cases': top_cases,
            'rating_over_time': rating_over_time,
            'avg_response_label': avg_response_label,
            'avg_response_unit': avg_response_unit,
            'responded_count': responded_count,
        }
        return render(request, 'admin/mail_parser/stats.html', context)

    # =========================================================================
    # Training stats — workshops / managers / technicians breakdown by country
    # =========================================================================

    def training_stats_view(self, request):
        from collections import Counter, defaultdict
        from datetime import timedelta
        from django.db.models import Avg, Count, Q
        from django.db.models.functions import TruncMonth
        from django.utils import timezone

        TOTAL_QUESTIONS = sum(settings.QUESTION_NUMBER.values())  # 100
        countries = ['FR', 'ES', 'PL', 'DE', 'IT']
        category_max = settings.QUESTION_NUMBER  # {'diagnostic': 15, ...}

        # Exclude internal/staff users (alltrucks employees, support test
        # accounts, etc.) so they don't skew the activation/test/score stats.
        external_users = User.objects.exclude(email__icontains='alltrucks')

        # Aggregate KPIs
        total_workshops = Company.objects.count()
        managers = external_users.filter(user_type='manager')
        technicians = external_users.filter(user_type='technician')
        total_managers = managers.count()
        total_technicians = technicians.count()
        active_users = external_users.filter(
            user_type__in=['manager', 'technician'], is_active=True
        ).count()
        total_users = total_managers + total_technicians
        activation_rate = round(100 * active_users / total_users, 1) if total_users else 0

        # Technicians who completed at least one test = exist in Score table
        techs_who_tested_ids = set(
            Score.objects.filter(user__user_type='technician')
            .values_list('user_id', flat=True)
            .distinct()
        )
        test_rate = (
            round(100 * len(techs_who_tested_ids) / total_technicians, 1)
            if total_technicians else 0
        )

        # By-country table — workshops, managers (active/total), technicians (active/total),
        # technicians who took the test, average score percentage.
        by_country = []
        for country in countries:
            workshops_in_country = Company.objects.filter(country=country)
            workshop_ids = list(workshops_in_country.values_list('id', flat=True))

            country_managers = managers.filter(company_id__in=workshop_ids)
            country_techs = technicians.filter(company_id__in=workshop_ids)

            country_tech_ids = list(country_techs.values_list('id', flat=True))
            tested_in_country = sum(1 for t in country_tech_ids if t in techs_who_tested_ids)

            # Average score (sum of all category scores by tech) / total possible
            # Take the LAST attempt per technician — group by (user, date) so multiple
            # retakes don't bias the average.
            score_rows = Score.objects.filter(user_id__in=country_tech_ids)
            if score_rows.exists():
                # Build {user_id: {date: total_score}} then take the latest date per user
                user_attempts = {}
                for s in score_rows.values('user_id', 'date', 'score'):
                    key = (s['user_id'], s['date'])
                    user_attempts[key] = user_attempts.get(key, 0) + s['score']
                latest_per_user = {}
                for (uid, date), total in user_attempts.items():
                    cur = latest_per_user.get(uid)
                    if cur is None or date > cur[0]:
                        latest_per_user[uid] = (date, total)
                if latest_per_user:
                    avg_score_pct = round(
                        100 * sum(t[1] for t in latest_per_user.values())
                        / (TOTAL_QUESTIONS * len(latest_per_user)),
                        1,
                    )
                else:
                    avg_score_pct = None
            else:
                avg_score_pct = None

            by_country.append({
                'country': country,
                'workshops': workshops_in_country.count(),
                'managers_total': country_managers.count(),
                'managers_active': country_managers.filter(is_active=True).count(),
                'techs_total': country_techs.count(),
                'techs_active': country_techs.filter(is_active=True).count(),
                'tested': tested_in_country,
                'tested_pct': round(100 * tested_in_country / country_techs.count(), 1)
                              if country_techs.count() else 0,
                'avg_score_pct': avg_score_pct,
            })

        # Sort the chart payload by score so the leaderboard reads naturally.
        ranking = sorted(
            (c for c in by_country if c['avg_score_pct'] is not None),
            key=lambda c: -c['avg_score_pct'],
        )

        # ---- Tests over time (last 12 months, monthly) ------------------------
        twelve_months_ago = timezone.now() - timedelta(days=365)
        external_tech_ids = list(technicians.values_list('id', flat=True))
        # One "evaluation" = one (user, date) pair (Score has 8 rows per test).
        eval_pairs = (
            Score.objects.filter(
                user_id__in=external_tech_ids,
                date__gte=twelve_months_ago,
            )
            .values('user_id', 'date')
            .distinct()
        )
        evals_per_month = Counter()
        for row in eval_pairs:
            month_key = row['date'].replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            evals_per_month[month_key] += 1
        evals_over_time = [
            {'month': m.strftime('%Y-%m'), 'count': evals_per_month[m]}
            for m in sorted(evals_per_month)
        ]

        # ---- Average score per category (latest attempt per technician) ------
        # Re-walk the scores once and gather per-category sums, picking only the
        # latest (user, date) attempt per user so retakes don't double-count.
        all_scores = list(
            Score.objects.filter(user_id__in=external_tech_ids)
            .values('user_id', 'date', 'question_type', 'score')
        )
        latest_attempt = {}  # user_id -> latest date
        for s in all_scores:
            cur = latest_attempt.get(s['user_id'])
            if cur is None or s['date'] > cur:
                latest_attempt[s['user_id']] = s['date']

        cat_sum = defaultdict(int)
        cat_taken = defaultdict(int)
        per_user_total = defaultdict(int)
        for s in all_scores:
            if s['date'] != latest_attempt.get(s['user_id']):
                continue
            cat_sum[s['question_type']] += s['score']
            cat_taken[s['question_type']] += 1
            per_user_total[s['user_id']] += s['score']

        category_breakdown = []
        for cat, max_q in category_max.items():
            n = cat_taken.get(cat, 0)
            avg_pct = round(100 * cat_sum[cat] / (max_q * n), 1) if n else 0
            category_breakdown.append({
                'category': cat.replace('_', ' ').title(),
                'avg_pct': avg_pct,
                'n': n,
            })
        category_breakdown.sort(key=lambda x: -x['avg_pct'])

        # ---- Score distribution histogram (latest attempt per tech) -----------
        buckets = {'0-25': 0, '25-50': 0, '50-75': 0, '75-100': 0}
        for total in per_user_total.values():
            pct = 100 * total / TOTAL_QUESTIONS
            if pct < 25: buckets['0-25'] += 1
            elif pct < 50: buckets['25-50'] += 1
            elif pct < 75: buckets['50-75'] += 1
            else: buckets['75-100'] += 1
        score_distribution = [
            {'bucket': k, 'count': v} for k, v in buckets.items()
        ]

        # ---- Top workshops leaderboard ---------------------------------------
        # Average score per workshop = mean of its technicians' latest totals.
        workshop_totals = defaultdict(list)
        tech_to_company = dict(
            technicians.values_list('id', 'company_id')
        )
        for uid, total in per_user_total.items():
            cid = tech_to_company.get(uid)
            if cid is not None:
                workshop_totals[cid].append(total)
        workshops_by_id = {
            c.id: c for c in Company.objects.filter(id__in=workshop_totals.keys())
        }
        top_workshops = []
        for cid, totals in workshop_totals.items():
            company = workshops_by_id.get(cid)
            if not company or not totals:
                continue
            avg_pct = round(100 * sum(totals) / (TOTAL_QUESTIONS * len(totals)), 1)
            top_workshops.append({
                'name': company.name,
                'country': company.country,
                'city': company.city,
                'techs_tested': len(totals),
                'avg_pct': avg_pct,
            })
        top_workshops.sort(key=lambda x: (-x['avg_pct'], -x['techs_tested']))
        top_workshops = top_workshops[:10]

        # ---- Overall average score (single number) ---------------------------
        overall_avg_pct = (
            round(100 * sum(per_user_total.values()) / (TOTAL_QUESTIONS * len(per_user_total)), 1)
            if per_user_total else 0
        )

        context = {
            'total_workshops': total_workshops,
            'total_managers': total_managers,
            'total_technicians': total_technicians,
            'activation_rate': activation_rate,
            'active_users': active_users,
            'total_users': total_users,
            'test_rate': test_rate,
            'tested_count': len(techs_who_tested_ids),
            'total_questions': TOTAL_QUESTIONS,
            'overall_avg_pct': overall_avg_pct,
            'by_country': by_country,
            'ranking': ranking,
            'evals_over_time': evals_over_time,
            'category_breakdown': category_breakdown,
            'score_distribution': score_distribution,
            'top_workshops': top_workshops,
        }
        return render(request, 'admin/training_stats.html', context)

    def _kb_serialize(self, case, include_full=False):
        out = {
            'id': case.id,
            'case_number': case.case_number,
            'manufacturer': case.manufacturer,
            'series': case.series,
            'subject': case.subject,
            'country': case.country,
            'system': case.system,
            'synced_at': case.synced_at.isoformat() if case.synced_at else None,
            'synced': bool(case.openai_file_id),
        }
        if include_full:
            for f in self.KB_FORM_FIELDS:
                out[f] = getattr(case, f)
            out['markdown'] = case.to_markdown()
            out['filename'] = case.filename
            out['openai_file_id'] = case.openai_file_id
            out['sync_error'] = case.sync_error
        return out

    def _flatten_dict(self, d, parent_key='', sep='_'):
        """Flatten nested dictionary for CSV export"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ', '.join(str(i) for i in v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _flatten_dict_keys(self, d, parent_key='', sep='_'):
        """Get flattened keys from a nested dictionary"""
        keys = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                keys.extend(self._flatten_dict_keys(v, new_key, sep=sep))
            else:
                keys.append(new_key)
        return keys


admin_site = MyAdminSite(name='myadmin')
