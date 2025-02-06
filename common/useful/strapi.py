import requests
from django.conf import settings
from django.core.cache import cache

class Content:
    def __init__(self):
        self.api_url = f'{settings.STRAPI_URL}/api'

    def _generate_cache_key(self, page, parameters):
        params_key = "_".join(f"{key}={value}" for key, value in parameters.items())
        return f"content_{page}_{params_key}"

    def get_content(self, pages, parameters={}):
        content = {}
        for page in pages:
            cache_key = self._generate_cache_key(page, parameters)
            page_content = cache.get(cache_key)
            if not page_content:

                response = requests.get(f"{self.api_url}/{page}", params=parameters)
                if response.status_code == 200:
                    data = response.json()['data']
                elif response.status_code == 404:
                    parameters['locale'] = "fr"
                    response = requests.get(f"{self.api_url}/{page}", params=parameters)
                    response.raise_for_status()
                    data = response.json()['data']
                else:
                    return False

                if isinstance(data, list):
                    page_content = [{**item['attributes'], 'id': item['id']} for item in data]
                else:
                    page_content = data['attributes']
                cache.set(cache_key, page_content, 60 * int(settings.CONTENT_CACHE_DURATION))
            content[page.replace('-', '_')] = page_content
        return content

strapi_content = Content()