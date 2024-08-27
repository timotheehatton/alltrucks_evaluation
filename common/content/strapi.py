import requests

class Content:
    def __init__(self):
        self.api_url = "http://localhost:1337/api"

    def get_content(self, pages, parameters, image=False):
        content = {}
        if image:
            response = requests.get(f"{self.api_url}/{pages[0]}", params=parameters)
            response.raise_for_status()
            return response.json()
        for page in pages:
            response = requests.get(f"{self.api_url}/{page}", params=parameters)
            response.raise_for_status()
            content.update(response.json()['data']['attributes'])
        return content

strapi_content = Content()
