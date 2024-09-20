from django.http import HttpResponse
from reportlab.pdfgen import canvas
from django.shortcuts import render
from users.decorators import technician_required
from users.models import Score
from django.db.models import Max, Sum, ExpressionWrapper, IntegerField
from common.content.strapi import strapi_content
import os
from io import BytesIO
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import fitz  # PyMuPDF
from django.conf import settings


@technician_required
def download_pdf(request):
    user = request.user
    last_datetime = Score.objects.filter(user=user).aggregate(date=Max('date'))['date']
    template_path = os.path.join(settings.BASE_DIR, 'static/pdf/diploma.pdf')
    output = BytesIO()
    document = fitz.open(template_path)

    pdf = {
        'name': (f"{user.first_name} {user.last_name}", 22, 'center', 'helvetica'),
        'date': (f"{last_datetime.strftime('%Y/%m/%d')}", 12, 'right', 'helvetica'),
        'location': (f"{user.company.name.capitalize()}, {user.company.city.capitalize()}, {user.company.country.upper()}", 14, 'center', 'helvetica'),
        'content': ("You have performed your expertise evaluation and the Alltrucks team would like to thanks you for that. Please find here ender information regarding your expertise.", 12, 'center', 'helvetica-oblique')
    }

    for key, value in pdf.items():
        text, fontsize, position, font = value
        placeholder = document[0].search_for(key)[0]
        document[0].draw_rect(placeholder, color=(1, 1, 1), fill=(1, 1, 1))
        x0, _, x1, y1 = placeholder
        max_width = (x1 + 450) - x0
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            if fitz.get_text_length(current_line + word, fontname=font, fontsize=fontsize) < max_width:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())
        text_y = y1
        for line in lines:
            text_width = fitz.get_text_length(line, fontname=font, fontsize=fontsize)
            if position == 'center':
                text_x = (x0 + x1) / 2 - text_width / 2
            elif position == 'right':
                text_x = x1 - text_width
            else:
                text_x = x0
            document[0].insert_text(
                (text_x, text_y),
                line,
                fontsize=fontsize,
                color=(0, 0, 0)
            )
            text_y += fontsize * 1.2
    document.save(output)
    document.close()
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_diploma.pdf"'
    
    return response


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

    return render(request, 'technician/stats/index.html', {
        'scores_by_category': scores_by_category,
        'page_content': page_content,
    })