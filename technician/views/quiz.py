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


@technician_required
def index(request):
    questions = strapi_content.get_all_questions(parameters={'local': 'fr', 'populate': 'image'})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date = timezone.now()
            user_answers = data.get('answers', {})
            correct_answers = {item['id']: item['attributes']['anwser'] for item in questions['data']}
            all_categories = [item['attributes']['category'] for item in questions['data']]
            scores = {}

            for category in all_categories:
                scores[category] = 0

            for question_id, choices in user_answers.items():
                if correct_answers.get(int(question_id)) in choices['choice']:
                    scores[choices['category']] += 1
            
            print(scores)
            
            # Store the scores in the database
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

    categorized_questions = collections.defaultdict(list)

    for item in questions['data']:
        categorized_questions[item['attributes']['category']].append(item)

    selected_questions = []
    for _, items in categorized_questions.items():
        if len(items) >= 10:
            selected_questions.extend(random.sample(items, 10))
        else:
            selected_questions.extend(items)

    displayed_questions = [
        {
            'id': item['id'],
            'category': item['attributes']['category'],
            'question': item['attributes']['question'],
            'choice_1': item['attributes']['choice_1'],
            'choice_2': item['attributes']['choice_2'],
            'choice_3': item['attributes']['choice_3'],
            'choice_4': item['attributes']['choice_4'],
            'image': '/static/img/logo.png' if not item['attributes']['image']['data'] else f"http://localhost:1337{item['attributes']['image']['data']['attributes']['url']}",
        }
        for item in selected_questions
    ]

    return render(request, 'technician/quiz/index.html', {
        'questions': json.dumps(displayed_questions)
    })