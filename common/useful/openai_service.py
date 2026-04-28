import openai
from django.conf import settings


class OpenAIService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0,
        )

    def generate_response(self, system_prompt, user_message, model='gpt-4o-mini'):
        """Returns (text, error, metadata).

        metadata is a dict with optional keys:
          - search_queries: list[str] of queries the model issued to file_search
          - citations: list[dict] of {file_id, filename, index, type} entries
        """
        vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
        try:
            if vector_store_id:
                response = self.client.responses.create(
                    model=model,
                    instructions=system_prompt,
                    input=user_message,
                    tools=[{
                        'type': 'file_search',
                        'vector_store_ids': [vector_store_id],
                        'max_num_results': 5,
                        'ranking_options': {
                            'score_threshold': 0.85,
                        },
                    }],
                    max_output_tokens=1024,
                    temperature=0.7,
                )
                return (
                    response.output_text,
                    None,
                    self._extract_metadata(response),
                )

            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message},
                ],
                max_tokens=1024,
                temperature=0.7,
            )
            return completion.choices[0].message.content, None, {}
        except openai.APITimeoutError as e:
            return '', f'OpenAI API timeout: {e}', {}
        except openai.APIError as e:
            return '', f'OpenAI API error: {e}', {}
        except Exception as e:
            return '', f'Unexpected error: {type(e).__name__}: {e}', {}

    @staticmethod
    def _extract_metadata(response):
        search_queries = []
        citations = []
        seen = set()
        for item in getattr(response, 'output', []) or []:
            if item.type == 'file_search_call':
                queries = getattr(item, 'queries', None) or []
                search_queries.extend(queries)
            elif item.type == 'message':
                for content in getattr(item, 'content', []) or []:
                    for ann in getattr(content, 'annotations', []) or []:
                        if getattr(ann, 'type', None) != 'file_citation':
                            continue
                        key = (getattr(ann, 'file_id', ''), getattr(ann, 'index', None))
                        if key in seen:
                            continue
                        seen.add(key)
                        citations.append({
                            'file_id': getattr(ann, 'file_id', ''),
                            'filename': getattr(ann, 'filename', ''),
                            'index': getattr(ann, 'index', None),
                        })
        return {'search_queries': search_queries, 'citations': citations}


ai_service = OpenAIService()