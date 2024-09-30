from django.db.models import ExpressionWrapper, F, IntegerField, Max, Sum
from django.shortcuts import render

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

    last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))
    if last_dates:
        technicians = Score.objects.filter(
            user__in=company_users,
            date__in=(score['last_date'] for score in last_dates)
        ).values(
            'user__id', 'user__first_name', 'user__last_name', 'date'
        ).annotate(
            id=F('user__id'),
            first_name=F('user__first_name'),
            last_name=F('user__last_name'),
            score=ExpressionWrapper((Sum('score') * 100) / (20 * 8), output_field=IntegerField())
        )
    else:
        technicians = company_users.values('first_name', 'last_name', 'id')

    return render(request, 'manager/technicians/index.html', {
        'technicians': technicians,
        'page_content': page_content
    })