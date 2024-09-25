import requests
import os
from django.conf import settings

class Email:
    def __init__(self):
        self.url = f'{settings.STRAPI_URL}/api/email'
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.STRAPI_EMAIL_TOKEN}"
        }

    def load_template(self):
        file_path = os.path.join(settings.STATIC_ROOT, 'mail/template.html')
        with open(file_path, 'r') as file:
            return file.read()

    def send_email(self, to_email, subject, content, title, link):
        template = self.load_template()
        html_content = template.replace('{{ content }}', content).replace('{{ title }}', title).replace('{{ link }}', link)
        payload = {
            "to": to_email,
            "subject": subject,
            "html": html_content,
            "text": content,
        }
        response = requests.post(self.url, json=payload, headers=self.headers)
        if response.status_code == 200:
            return True
        else:
            print(f"Failed to send email: {response.status_code}, {response.text}")
            return False

email = Email()