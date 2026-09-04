from rest_framework.renderers import JSONRenderer

class CustomJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        status_code = renderer_context['response'].status_code if renderer_context else 200
        
        # If the response is an error (4xx or 5xx), the exception handler handles it
        if status_code >= 400:
            return super().render(data, accepted_media_type, renderer_context)
            
        # Extract custom message if passed in Response(data, headers={'message': '...'})
        message = "Request processed successfully."
        if renderer_context and hasattr(renderer_context.get('response'), 'message'):
            message = renderer_context['response'].message

        # Standardize the successful response envelope
        response_data = {
            "status": "success",
            "message": message,
            "data": data
        }

        # Handle paginated data correctly
        if isinstance(data, dict) and 'results' in data:
            response_data['data'] = data['results']
            response_data['count'] = data.get('count')
            response_data['next'] = data.get('next')
            response_data['previous'] = data.get('previous')

        return super().render(response_data, accepted_media_type, renderer_context)
