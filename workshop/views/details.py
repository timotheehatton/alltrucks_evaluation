from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from users.decorators import workshop_required
from users.models import User
from users.models import Score
from django.db.models import Sum, Max, ExpressionWrapper, IntegerField
from common.content.strapi import strapi_content


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'menu', 'category', 'trainings'],
        parameters={'locale': request.user.language.lower()}
    )


@workshop_required
def index(request, id):
    page_content = get_content(request)
    technician = get_object_or_404(User, id=id)
    last_datetime = Score.objects.filter(user=technician).aggregate(date=Max('date'))['date']
    scores_by_category = Score.objects.filter(user=technician, date=last_datetime).values('question_type').annotate(
        success_percentage=ExpressionWrapper((Sum('score') * 100) / 20, output_field=IntegerField())
    )
    scores_by_category = [
        {
            'question_type': page_content['category'][score['question_type']],
            'success_percentage': score['success_percentage'],
            'trainings': [item for item in page_content['trainings'] if item['training_category'] == score['question_type']]
        }
        for score in scores_by_category
    ]

    return render(request, 'workshop/details/index.html', {
        'scores_by_category': scores_by_category,
        'current_user': technician,
        'page_content': page_content
    })