import requests
from django.conf import settings


class Content:
    def __init__(self):
        self.api_url = f'{settings.STRAPI_URL}/api'


    def get_content(self, pages, parameters):
        content = {}
        for page in pages:
            response = requests.get(f"{self.api_url}/{page}", params=parameters)
            response.raise_for_status()
            if type(response.json()['data']) == list:
                content[page.replace('-', '_')] = [{**item['attributes'], 'id': item['id']} for item in response.json()['data']]
            else:
                content[page.replace('-', '_')] = response.json()['data']['attributes']
    
        return content

strapi_content = Content()
