from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from users.decorators import workshop_required
from users.models import User
from users.models import Score

@workshop_required
def index(request, id):
    technician = get_object_or_404(User, id=id, company=request.user.company, user_type='technician')
    scores = Score.objects.filter(user=technician).values('question_type').annotate(total_score=Sum('score'))
    total_score = sum(item['total_score'] for item in scores)

    return render(request, 'workshop/details/index.html', {
        'technician': technician,
        'scores': scores,
        'total_score': total_score
    })