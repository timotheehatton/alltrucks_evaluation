from django.http import HttpResponse
from reportlab.pdfgen import canvas
from django.shortcuts import render
from users.decorators import workshop_required
from users.models import Score, User
from django.db.models import Max, Sum, ExpressionWrapper, IntegerField
from common.content.strapi import strapi_content
import collections


@workshop_required
def download_pdf(request):
    user = request.user
    company_users = User.objects.filter(company=user.company)
    last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))

    scores_sum = Score.objects.filter(
        user__in=company_users,
        date__in=[score['last_date'] for score in last_dates]
    ).aggregate(total_score=Sum('score'))['total_score']

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_scores.pdf"'
    p = canvas.Canvas(response)
    p.drawString(100, 800, "Company Scores")
    p.drawString(100, 780, f"Company: {user.company.name}")
    p.drawString(100, 760, f"Total Score: {scores_sum or 0}")
    p.showPage()
    p.save()

    return response


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'category', 'menu'],
        parameters={'locale': request.user.language.lower()}
    )


@workshop_required
def index(request):
    page_content = get_content(request)
    user = request.user
    company_users = User.objects.filter(company=user.company)
    last_dates = Score.objects.filter(user__in=company_users).values('user').annotate(last_date=Max('date'))

    scores_by_category = Score.objects.filter(
        user__in=company_users,
        date__in=(score['last_date'] for score in last_dates)
    ).values('user__first_name', 'user__last_name', 'question_type').annotate(
        total_score=Sum('score'),
        success_percentage=ExpressionWrapper((Sum('score') * 100) / 20, output_field=IntegerField())
    )

    technician_scores = collections.defaultdict(dict)
    for item in scores_by_category:
        technician_scores[f"{item['user__first_name']} {item['user__last_name']}"][item['question_type']] = item['success_percentage']

    global_scores = {}
    for score in scores_by_category:
        global_scores[page_content['category'][score['question_type']]] = score['success_percentage']

    return render(request, 'workshop/stats/index.html', {
        'technician_scores': dict(technician_scores),
        'global_scores': global_scores,
        'page_content': page_content,
    })