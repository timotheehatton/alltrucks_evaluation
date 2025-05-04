from django.conf import settings
from django.db.models import ExpressionWrapper, IntegerField, Max, Sum, When, Case
from django.shortcuts import get_object_or_404, render

from common.useful.strapi import strapi_content
from users.decorators import manager_required
from users.models import Score, User


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'menu', 'category', 'trainings'],
        parameters={'locale': request.user.language.lower()}
    )


@manager_required
def index(request, id):
    page_content = get_content(request)
    technician = get_object_or_404(User, id=id)
    last_datetime = Score.objects.filter(user=technician).aggregate(date=Max('date'))['date']
    scores_by_category = Score.objects.filter(
        user=technician,
        date=last_datetime
    ).values('question_type').annotate(
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
            'question_type': page_content['category'][score['question_type']],
            'success_percentage': score['success_percentage'],
            'trainings': [item for item in page_content['trainings'] if
                          item['training_category'] == score['question_type']]
        }
        for score in scores_by_category
    ]

    return render(request, 'manager/details/index.html', {
        'scores_by_category': scores_by_category,
        'current_user': technician,
        'page_content': page_content
    })
