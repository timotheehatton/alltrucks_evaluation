from django.http import HttpResponse
from reportlab.pdfgen import canvas
from django.shortcuts import render
from users.decorators import technician_required
from users.models import Score
from django.db.models import Max, Sum, ExpressionWrapper, IntegerField
from common.content.strapi import strapi_content


@technician_required
def download_pdf(request):
    user = request.user
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_scores.pdf"'
    p = canvas.Canvas(response)
    p.drawString(100, 800, "User Scores")
    p.drawString(100, 780, f"Name: {user.first_name} {user.last_name}")
    y = 750
    for score in Score.objects.filter(user=user):
        p.drawString(100, y, f"Category: {score.question_type}, Score: {score.score}")
        y -= 20
    p.showPage()
    p.save()

    return response


@technician_required
def index(request):
    page_content = strapi_content.get_content(pages=['user-statistic', 'category', 'menu'], parameters={'locale': request.user.language.lower()})
    last_datetime = Score.objects.filter(user=request.user).aggregate(date=Max('date'))['date']
    scores_by_category = Score.objects.filter(user=request.user, date=last_datetime).values('question_type').annotate(
        total_score=Sum('score'),
        success_percentage=ExpressionWrapper((Sum('score') * 100.0) / 20.0, output_field=IntegerField())
    )
    scores_by_category = [
        {
            'question_type': page_content[score['question_type']],
            'total_score': score['total_score'],
            'success_percentage': score['success_percentage']
        }
        for score in scores_by_category
    ]

    return render(request, 'technician/stats/index.html', {
        'scores_by_category': scores_by_category,
        'page_content': page_content,
    })