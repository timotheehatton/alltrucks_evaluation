import random
import requests
import collections

from django.shortcuts import render
from users.decorators import technician_required

from common.content.strapi import strapi_content


@technician_required
def index(request):
    questions = strapi_content.get_all_questions(parameters={'local': 'fr', 'populate': 'image'})
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
            'question': item['attributes']['question'],
            'choice_1': item['attributes']['choice_1'],
            'choice_2': item['attributes']['choice_2'],
            'choice_3': item['attributes']['choice_3'],
            'choice_4': item['attributes']['choice_4'],
            'image': item['attributes']['image']['data']['attributes']['url'],
        }
        for item in selected_questions
    ]

    return render(request, 'technician/quiz/index.html', {
        'questions': displayed_questions
    })