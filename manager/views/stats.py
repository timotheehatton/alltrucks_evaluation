import collections

from django.db.models import ExpressionWrapper, IntegerField, Max, Sum
from django.http import HttpResponse
from django.shortcuts import render
from reportlab.pdfgen import canvas

from common.useful.strapi import strapi_content
from users.decorators import manager_required
from users.models import Score, User


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'category', 'menu'],
        parameters={'locale': request.user.language.lower()}
    )


@manager_required
def index(request):
    page_content = get_content(request)
    user = request.user
    company_users = User.objects.filter(company=user.company)
    last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))

    scores_by_category = Score.objects.filter(
        user__in=company_users,
        date__in=(score['last_date'] for score in last_dates)
    ).values('user__first_name', 'user__last_name', 'user__id', 'question_type').annotate(
        total_score=Sum('score'),
        success_percentage=ExpressionWrapper((Sum('score') * 100) / 20, output_field=IntegerField())
    )

    technician_scores = collections.defaultdict(dict)
    for item in scores_by_category:
        technician_scores[
            (f"{item['user__first_name'].capitalize()} {item['user__last_name'].upper()}",
             item['user__id'])
        ][item['question_type']] = item['success_percentage']

    global_scores = {}
    for score in scores_by_category:
        global_scores[page_content['category'][score['question_type']]] = score['success_percentage']

    return render(request, 'manager/stats/index.html', {
        'technician_scores': dict(technician_scores),
        'global_scores': global_scores,
        'page_content': page_content,
    })