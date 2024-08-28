import random
import requests
import collections
import json

from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import render
from users.decorators import technician_required

from common.content.strapi import strapi_content
from users.models import Score


def get_content(request):
    return strapi_content.get_content(
        pages=['test', 'menu', 'category', 'questions'],
        parameters={'locale': request.user.language.lower(), 'populate': 'image', 'size': 'large'}
    )


def handle_quiz(request, page_content):
    try:
        data = json.loads(request.body)
        date = timezone.now()
        user_answers = data.get('answers', {})
        correct_answers = {item['id']: item['anwser'] for item in page_content['questions']}
        all_categories = [item['category'] for item in page_content['questions']]
        scores = {category: 0 for category in all_categories}

        for question_id, choices in user_answers.items():
            if correct_answers.get(int(question_id)) in choices['choice']:
                scores[choices['category']] += 1

        for category, category_score in scores.items():
            Score.objects.create(
                user=request.user,
                date=date,
                question_type=category,
                score=category_score
            )
        return JsonResponse({"success": True, "message": "Quiz successfully corrected."})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})



@technician_required
def index(request):
    page_content = get_content(request)

    if request.method == 'POST':
        return handle_quiz(request, page_content)

    categorized_questions = collections.defaultdict(list)
    for item in page_content['questions']:
        categorized_questions[item['category']].append(item)

    selected_questions = []
    for _, items in categorized_questions.items():
        if len(items) >= 10:
            selected_questions.extend(random.sample(items, 10))
        else:
            selected_questions.extend(items)

    displayed_questions = [
        {
            'id': item['id'],
            'category_displayed': page_content['category'][item['category']],
            'category': item['category'],
            'question': item['question'],
            'choice_1': item['choice_1'],
            'choice_2': item['choice_2'],
            'choice_3': item['choice_3'],
            'choice_4': item['choice_4'],
            'choice_5': item['choice_5'],
            'image': None if not item['image']['data'] else f"http://localhost:1337{item['image']['data']['attributes']['url']}",
        } for item in selected_questions
    ]

    return render(request, 'technician/quiz/index.html', {
        'questions': json.dumps(displayed_questions),
        'page_content': page_content
    })