from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            "status": "error",
            "message": "An error occurred.",
            "data": None
        }

        # Check if it's a validation error
        if response.status_code == 400:
            custom_response_data["message"] = "Validation failed."
            custom_response_data["data"] = response.data
        elif response.status_code == 401:
            custom_response_data["message"] = "Authentication credentials were not provided or are invalid."
        elif response.status_code == 403:
            custom_response_data["message"] = "You do not have permission to perform this action."
        elif response.status_code == 404:
            custom_response_data["message"] = "The requested resource was not found."
        else:
            # For other errors, try to extract a generic detail message if present
            if isinstance(response.data, dict) and "detail" in response.data:
                custom_response_data["message"] = str(response.data["detail"])
            elif isinstance(response.data, list):
                custom_response_data["message"] = str(response.data[0])

        response.data = custom_response_data

    return response
