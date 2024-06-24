from django.shortcuts import render
from django.db.models import Sum
from users.models import User
from users.models import Score  # Adjust this import according to your app's structure
from users.decorators import workshop_required


@workshop_required
def index(request):
    company = request.user.company
    technicians = User.objects.filter(company=company, user_type='technician')

    technician_scores = {tech: {} for tech in technicians}
    global_scores = {}

    scores = Score.objects.filter(user__in=technicians).values('user', 'question_type').annotate(total_score=Sum('score'))
    for score in scores:
        tech = User.objects.get(id=score['user'])
        question_type = score['question_type']
        score_value = score['total_score']

        if question_type not in technician_scores[tech]:
            technician_scores[tech][question_type] = score_value
        else:
            technician_scores[tech][question_type] += score_value
        if question_type in global_scores:
            global_scores[question_type] += score_value
        else:
            global_scores[question_type] = score_value

    return render(request, 'workshop/stats/index.html', {
        'technician_scores': technician_scores,
        'global_scores': global_scores
    })