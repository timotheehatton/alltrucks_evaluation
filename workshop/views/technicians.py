from django.shortcuts import render
from django.db.models import Max, Sum, F, ExpressionWrapper, IntegerField
from users.decorators import workshop_required
from users.models import User
from users.models import Score
from common.content.strapi import strapi_content


def get_content(request):
    return strapi_content.get_content(
        pages=['menu'],
        parameters={'locale': request.user.language.lower()}
    )


@workshop_required
def index(request):
    page_content = get_content(request)
    user = request.user
    company_users = User.objects.filter(company=user.company)

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

    return render(request, 'workshop/technicians/index.html', {
        'technicians': technicians,
        'page_content': page_content
    })