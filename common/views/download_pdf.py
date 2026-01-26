import base64
import fitz
import json
import os
from PIL import Image
from django.conf import settings
from django.db.models import Case, ExpressionWrapper, IntegerField, Max, Sum, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from io import BytesIO

from common.useful.strapi import strapi_content
from users.models import Score, User


def get_content(request):
    return strapi_content.get_content(
        pages=['global-pdf', 'user-statistic', 'category', 'trainings'],
        parameters={'locale': request.user.language.lower()}
    )

def downloadPdf(request, user_id):
    user = get_object_or_404(User, id=user_id)
    last_datetime = Score.objects.filter(user=user).aggregate(date=Max('date'))['date']
    template_path = os.path.join(settings.STATIC_ROOT, 'pdf/diploma.pdf')
    output = BytesIO()
    document = fitz.open(template_path)
    page_content = get_content(request)
    pdf = {
        'name': (f"{user.first_name.capitalize()} {user.last_name.upper()}", 22, 'center', 'helvetica'),
        'date': (f"{last_datetime.strftime('%Y/%m/%d')}", 12, 'right', 'helvetica'),
        'location': (
            f"{user.company.name.capitalize()}, {user.company.city.capitalize()}, {user.company.country.upper()}",
            14,
            'center',
            'helvetica'
        ),
        'content': (
            page_content['global_pdf']['diploma_content'],
            12,
            'center',
            'helvetica-oblique'
        )
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
        max_dimension = 1500
        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG', optimize=True)
        img_byte_arr = img_byte_arr.getvalue()
        page = document[0]
        rect = page.rect
        image_width = rect.width / 1.2
        image_height = rect.height / 1.2

        center_x = (rect.width - image_width) / 2
        center_y = ((rect.height - image_height) / 2) + 10

        image_rect = fitz.Rect(center_x, center_y, center_x + image_width, center_y + image_height)
        page.insert_image(image_rect, stream=img_byte_arr)

    # Page 2: Training Recommendations
    scores_by_category = Score.objects.filter(user=user, date=last_datetime).values('question_type').annotate(
        success_percentage=ExpressionWrapper(
            (Sum('score') * 100) / Case(
                *[When(question_type=qt, then=val) for qt, val in settings.QUESTION_NUMBER.items()],
                default=1
            ),
            output_field=IntegerField()
        )
    )
    scores_by_category = [
        {
            'question_type': page_content['category'].get(score['question_type'], score['question_type']),
            'success_percentage': score['success_percentage'],
            'trainings': sorted(
                [item for item in page_content['trainings'] if item['training_category'] == score['question_type']],
                key=lambda x: x['maximum_score'])
        }
        for score in scores_by_category
    ]

    if scores_by_category:
        page1_rect = document[0].rect
        page2 = document.new_page(width=page1_rect.width, height=page1_rect.height)

        margin_x = 50
        gutter = 30
        col_width = (page1_rect.width - 2 * margin_x - gutter) / 2
        bar_height = 4
        bar_radius = 0.5

        # Colors
        cyan = (1/255, 181/255, 226/255)       # #01B5E2
        grey_bg = (240/255, 240/255, 240/255)  # #F0F0F0
        orange = (255/255, 152/255, 0/255)     # #FF9800
        grey_text = (117/255, 117/255, 117/255) # #757575
        dark_text = (51/255, 51/255, 51/255)   # #333333
        card_bg = (250/255, 250/255, 250/255)  # #FAFAFA
        card_border = (224/255, 224/255, 224/255) # #E0E0E0

        # Title
        title = page_content.get('user_statistic', {}).get('training_title', 'Training Recommendations')
        recommendation_label = page_content.get('user_statistic', {}).get('training_recommendation', 'Training recommendation')
        y_start = 60
        page2.insert_text((margin_x, y_start), title, fontsize=20, fontname='helvetica-bold', color=dark_text)
        y_start += 40

        mid = len(scores_by_category) // 2 + len(scores_by_category) % 2
        columns = [scores_by_category[:mid], scores_by_category[mid:]]

        for col_index, col_scores in enumerate(columns):
            col_x = margin_x + col_index * (col_width + gutter)
            y = y_start

            for score in col_scores:
                category_name = score['question_type']
                percentage = score['success_percentage']
                trainings = score['trainings']

                # Category name (left) and percentage (right)
                page2.insert_text((col_x, y), category_name, fontsize=10, fontname='helvetica-bold', color=dark_text)
                pct_text = f"{percentage}%"
                pct_width = fitz.get_text_length(pct_text, fontname='helvetica-bold', fontsize=10)
                page2.insert_text((col_x + col_width - pct_width, y), pct_text, fontsize=10, fontname='helvetica-bold', color=cyan)
                y += 10

                # Progress bar background (grey)
                bar_rect = fitz.Rect(col_x, y, col_x + col_width, y + bar_height)
                page2.draw_rect(bar_rect, color=grey_bg, fill=grey_bg, radius=bar_radius)

                # Progress bar fill (cyan)
                fill_width = col_width * (percentage / 100)
                if fill_width > 0:
                    fill_rect = fitz.Rect(col_x, y, col_x + fill_width, y + bar_height)
                    page2.draw_rect(fill_rect, color=cyan, fill=cyan, radius=bar_radius)

                y += bar_height + 8

                # Training recommendation
                recommended_training = None
                for training in trainings:
                    if percentage < training['maximum_score']:
                        recommended_training = training
                        break

                if recommended_training:
                    card_padding = 12
                    card_top = y
                    card_height = 42
                    # Card background and border
                    card_rect = fitz.Rect(col_x, card_top, col_x + col_width, card_top + card_height)
                    page2.draw_rect(card_rect, color=card_border, fill=card_bg, radius=0.1)
                    # Label
                    page2.insert_text(
                        (col_x + card_padding, card_top + 16), f"ℹ {recommendation_label}",
                        fontsize=8, fontname='helvetica-bold', color=orange
                    )
                    # Training text
                    training_text = f"{recommended_training['training_number']} - {recommended_training['training_title']}"
                    page2.insert_text(
                        (col_x + card_padding, card_top + 32), training_text,
                        fontsize=8, fontname='helvetica', color=grey_text
                    )
                    y += card_height + 5
                y += 40

    document.save(output)
    document.close()
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_diploma.pdf"'
    return response
