from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from users.decorators import workshop_required
from users.models import User
from users.models import Score
from django.db.models import Sum, ExpressionWrapper, IntegerField
from common.content.strapi import strapi_content


def get_content(request):
    return strapi_content.get_content(
        pages=['user-statistic', 'menu', 'category'],
        parameters={'locale': request.user.language.lower()}
    )


@workshop_required
def index(request, id):
    page_content = get_content(request)
    technician = get_object_or_404(User, id=id, company=request.user.company, user_type='technician')
    scores = Score.objects.filter(user=technician).values('question_type').annotate(total_score=ExpressionWrapper((Sum('score') * 100) / 20, output_field=IntegerField()))
    total_score = sum(item['total_score'] for item in scores)

    return render(request, 'workshop/details/index.html', {
        'technician': technician,
        'scores_by_category': scores,
        'total_score': total_score,
        'page_content': page_content
    })