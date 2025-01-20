from django.db.models import ExpressionWrapper, IntegerField, Max, Sum
from django.shortcuts import render
from django.conf import settings

from common.useful.strapi import strapi_content
from users.decorators import technician_required
from users.models import Score


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'category', 'menu', 'trainings'],
        parameters={'locale': request.user.language.lower()}
    )


@technician_required
def index(request):
    page_content = get_content(request)
    last_datetime = Score.objects.filter(user=request.user).aggregate(date=Max('date'))['date']
    scores_by_category = Score.objects.filter(user=request.user, date=last_datetime).values('question_type').annotate(
        success_percentage=ExpressionWrapper((Sum('score') * 100) / settings.QUESTION_NUMBER, output_field=IntegerField())
    )
    scores_by_category = [
        {
            'question_type': page_content['category'][score['question_type']],
            'success_percentage': score['success_percentage'],
            'trainings': sorted([item for item in page_content['trainings'] if item['training_category'] == score['question_type']], key=lambda x: x['maximum_score'])
        }
        for score in scores_by_category
    ]

    return render(request, 'technician/stats/index.html', {
        'scores_by_category': scores_by_category,
        'page_content': page_content,
    })