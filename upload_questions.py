import csv
import requests

# Define the Strapi API endpoint and authentication token
API_URL = 'http://localhost:1337/api/questions'
TOKEN = 'f024eb01f0e529d8483f072c62eb839e1e2dec9c4c52fbc5f42a5fd19e8bc7907dd4de144cdbb9d15da44d9b01f5ce411c12fa9dc4629953561333c87c5713c012aef14817c3a3a81b8710c72aefcb817cade90a06496baf6529ab7b3fbb0bd4d500080055797e1b4c1531ea0a3ffe02cacd2da3fcb0b0b0c5940ae30e7e20b3'

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

def upload_question(question_data):
    response = requests.post(API_URL, headers=headers, json=question_data)
    if response.status_code == 200 or response.status_code == 201:
        print(f"success")
    else:
        print(f"Status Code: {response.status_code}, Error: {response.text}")

# Read the CSV file and upload each question
with open('uploaded_questions.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        question_data = {
            'data': {
                'question': row['question'],
                'category': row['category'],
                'choice_1': row['choice_1'],
                'choice_2': row['choice_2'],
                'choice_3': row['choice_3'],
                'choice_4': row['choice_4'],
                'choice_5': row['choice_5'],
                'anwser': row['anwser']
            }
        }
        upload_question(question_data)
        break