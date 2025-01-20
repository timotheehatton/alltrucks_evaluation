from django.db.models import ExpressionWrapper, F, IntegerField, Max, Sum
from django.shortcuts import render
from django.conf import settings

from common.useful.strapi import strapi_content
from users.decorators import manager_required
from users.models import Score, User


def get_content(request):
    return strapi_content.get_content(
        pages=['menu', 'workshop-technician'],
        parameters={'locale': request.user.language.lower()}
    )


@manager_required
def index(request):
    page_content = get_content(request)
    user = request.user
    company_users = User.objects.filter(company=user.company, user_type='technician')
    technicians = list(company_users.values('first_name', 'last_name', 'id'))
    last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))
    if last_dates:
        technicians_score = Score.objects.filter(
            user__in=company_users,
            date__in=(score['last_date'] for score in last_dates)
        ).values(
            'user__id', 'user__first_name', 'user__last_name', 'date'
        ).annotate(
            id=F('user__id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            score=ExpressionWrapper(
                (Sum('score') * 100) / (settings.QUESTION_NUMBER * 8),
                output_field=IntegerField()
            )
        )
        technicians_dict = {technician['id']: technician for technician in technicians}
        for technician_score in technicians_score:
            technician_id = technician_score['id']

            if technician_id in technicians_dict:
                technicians_dict[technician_id].update({
                    'date': technician_score['date'],
                    'score': technician_score['score'],
                })
            else:
                technicians_dict[technician_id] = {
                    'id': technician_id,
                    'first_name': technician_score['first_name'],
                    'last_name': technician_score['last_name'],
                    'date': technician_score['date'],
                    'score': technician_score['score'],
                }
        technicians = list(technicians_dict.values())

    return render(request, 'manager/technicians/index.html', {
        'technicians': technicians,
        'page_content': page_content
    })