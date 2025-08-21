import structlog
import traceback
from django.http import JsonResponse
from django.conf import settings
from rest_framework import status
from rest_framework.views import exception_handler as drf_exception_handler

logger = structlog.get_logger(__name__)


class GlobalExceptionMiddleware:
    """
    Global exception handling middleware for Django.
    Catches unhandled exceptions and returns structured JSON responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """
        Process unhandled exceptions and return structured error responses.
        """
        # Log the exception with structured logging
        logger.error(
            "Unhandled exception occurred",
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            path=request.path,
            method=request.method,
            user=getattr(request, 'user', None),
            exc_info=True
        )

        # Prepare error response
        error_response = {
            'error': {
                'type': 'internal_server_error',
                'message': 'An internal server error occurred',
                'timestamp': None,
            }
        }

        # Add timestamp
        from datetime import datetime
        error_response['error']['timestamp'] = datetime.utcnow().isoformat()

        # In development, include more details
        if settings.DEBUG:
            error_response['error']['debug'] = {
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc().split('\n')
            }

        return JsonResponse(
            error_response,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content_type='application/json'
        )


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    Provides structured error responses with logging.
    """
    # Get the standard error response
    response = drf_exception_handler(exc, context)
    
    if response is not None:
        # Log the exception
        request = context.get('request')
        view = context.get('view')
        
        logger.warning(
            "API exception occurred",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            status_code=response.status_code,
            path=getattr(request, 'path', None),
            method=getattr(request, 'method', None),
            view_name=getattr(view, '__class__', {}).get('__name__', None),
            user=getattr(request, 'user', None)
        )

        # Restructure the error response
        custom_response_data = {
            'error': {
                'type': 'api_error',
                'message': 'API request failed',
                'status_code': response.status_code,
                'timestamp': None,
                'details': response.data
            }
        }

        # Add timestamp
        from datetime import datetime
        custom_response_data['error']['timestamp'] = datetime.utcnow().isoformat()

        response.data = custom_response_data

    return response
