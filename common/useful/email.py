import os
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class Email:
    def __init__(self):
        self.sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

    @staticmethod
    def load_template():
        file_path = os.path.join(settings.STATIC_ROOT, 'mail/template.html')
        with open(file_path, 'r') as file:
            return file.read()

    def send_email(self, to_email, subject, content, title, link):
        template = self.load_template()
        html_content = template.replace('{{ content }}', content).replace('{{ title }}', title).replace('{{ link }}', link)

        message = Mail(
            from_email="info@alltrucks-amcat.com",
            to_emails=to_email,
            subject=subject,
            plain_text_content=content,
            html_content=html_content
        )
        message.reply_to = "info@alltrucks-amcat.com"

        try:
            response = self.sg.send(message)
            if response.status_code in (200, 201, 202):
                return True
            else:
                print(f"Failed to send email: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

email = Email()