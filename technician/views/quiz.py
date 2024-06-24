from django.shortcuts import render
from users.decorators import technician_required


@technician_required
def index(request):
    return render(request, 'technician/quiz/index.html')