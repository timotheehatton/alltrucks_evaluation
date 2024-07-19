import random
import requests
import collections
import json

from django.http import JsonResponse
from django.shortcuts import render
from users.decorators import technician_required

from common.content.strapi import strapi_content


@technician_required
def index(request):
    questions = strapi_content.get_all_questions(parameters={'local': 'fr', 'populate': 'image'})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_answers = data.get('answers', {})
            print('user_answers', user_answers)

            correct_answers = {item['id']: item['attributes']['anwser'] for item in questions['data']}
            print('correct_answers', correct_answers)
        
            score = 0
            for question_id, choices in user_answers.items():
                if correct_answers.get(int(question_id)) in choices:
                    score += 1
            print('score', score)

            return JsonResponse({"success": True, "message": "Quiz successfully corrected.", "score": score})
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
            'image': item['attributes']['image']['data']['attributes']['url'] if item['attributes']['image'] else None,
        }
        for item in selected_questions
    ]

    return render(request, 'technician/quiz/index.html', {
        'questions': json.dumps(displayed_questions)
    })