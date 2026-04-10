import openai
from django.conf import settings


class OpenAIService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=10.0,
        )

    def generate_response(self, system_prompt, user_message, model='gpt-4o-mini'):
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=1024,
                temperature=0.7,
            )
            return completion.choices[0].message.content, None
        except openai.APITimeoutError as e:
            return '', f'OpenAI API timeout: {e}'
        except openai.APIError as e:
            return '', f'OpenAI API error: {e}'
        except Exception as e:
            return '', f'Unexpected error: {type(e).__name__}: {e}'


ai_service = OpenAIService()
