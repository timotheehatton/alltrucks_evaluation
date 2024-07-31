import requests

class Content:
    def __init__(self):
        self.api_url = "http://localhost:1337/api"

    def get_content(self, page, parameters):
        response = requests.get(f"{self.api_url}/{page}", params=parameters)
        response.raise_for_status()
        return response.json()

strapi_content = Content()
