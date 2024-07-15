from django.http import HttpResponse
from reportlab.pdfgen import canvas
from django.shortcuts import render
from django.db.models import Sum
from users.decorators import technician_required
from users.models import Score


@technician_required
def index(request):
    user = request.user
    scores_by_category = Score.objects.filter(user=user).values('question_type').annotate(total_score=Sum('score'))

    return render(request, 'technician/stats/index.html', {
        'scores_by_category': scores_by_category
    })


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