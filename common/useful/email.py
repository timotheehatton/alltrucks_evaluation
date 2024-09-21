import requests

from django.conf import settings


class Email:
    def __init__(self):
        self.url = "https://great-life-10c877bc60.strapiapp.com/api/email"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer 172499ae3dc77f911ee77252c1aafccbd4aaa28060393f68c227adc4e943bae165a31c3d92827031b856cce17d61018cbf7be99570abb8ee467ab61510550fa89f44073fe87e3e4206f861e6bdd1dc05cb85c8bc6bb8d4fb16693c324916b9ba97e2de88e644397f972a53a23391f0ab5d60e45f830742ea540e660cd6488aec"  # Optional if needed
        }

    def send_email(self, to_email, subject, message):
        payload = {
            "to": to_email,
            "subject": subject,
            "text": message
        }
        response = requests.post(self.url, json=payload, headers=self.headers)
        
        if response.status_code == 200:
            print("Email sent successfully!")
        else:
            print(f"Failed to send email: {response.status_code}, {response.text}")

email = Email()