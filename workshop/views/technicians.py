from django.shortcuts import render
from django.db.models import Sum, Max
from users.decorators import workshop_required
from users.models import User
from users.models import Score

@workshop_required
def index(request):
    company = request.user.company
    technicians = User.objects.filter(company=company, user_type='technician')

    for technician in technicians:
        scores = Score.objects.filter(user=technician)
        technician.total_score = scores.aggregate(total=Sum('score')).get('total', 0)
        latest_score = scores.aggregate(latest_date=Max('date')).get('latest_date')
        technician.latest_evaluation_date = latest_score if latest_score else None

    return render(request, 'workshop/technicians/index.html', {
        'technicians': technicians
    })