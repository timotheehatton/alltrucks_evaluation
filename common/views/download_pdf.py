import base64
import fitz
import json
import os
from PIL import Image
from django.conf import settings
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from io import BytesIO

from common.useful.strapi import strapi_content
from users.models import Score, User


def downloadPdf(request, user_id):
    user = get_object_or_404(User, id=user_id)
    last_datetime = Score.objects.filter(user=user).aggregate(date=Max('date'))['date']
    template_path = os.path.join(settings.STATIC_ROOT, 'pdf/diploma.pdf')
    output = BytesIO()
    document = fitz.open(template_path)
    # TODO: Translation -> GOOD
    pdf = {
        'name': (f"{user.first_name.capitalize()} {user.last_name.upper()}", 22, 'center', 'helvetica'),
        'date': (f"{last_datetime.strftime('%Y/%m/%d')}", 12, 'right', 'helvetica'),
        'location': (
            f"{user.company.name.capitalize()}, {user.company.city.capitalize()}, {user.company.country.upper()}", 14,
            'center', 'helvetica'),
        'content': (
            "Vous avez effectué votre évaluation d'expertise et l'équipe Alltrucks tient à vous en remercier. Veuillez trouver ici les informations concernant votre expertise",
            12, 'center', 'helvetica-oblique')
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

    data = json.loads(request.body)
    image_data = data.get('chart_image_base64')
    if image_data:
        image_data = image_data.replace('data:image/png;base64,', '')
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        page = document[0]
        rect = page.rect
        image_width = rect.width / 1.5
        image_height = rect.height / 1.5

        center_x = (rect.width - image_width) / 2
        center_y = ((rect.height - image_height) / 2) + 10

        image_rect = fitz.Rect(center_x, center_y, center_x + image_width, center_y + image_height)
        page.insert_image(image_rect, stream=img_byte_arr)

    document.save(output)
    document.close()
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_diploma.pdf"'
    return response
