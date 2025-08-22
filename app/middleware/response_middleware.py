# app/middleware/response_middleware.py
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
import time

from app.utils.response_utils import create_success_response

class ResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Only process successful responses (2xx)
            if 200 <= response.status_code < 300:
                # Check if response is already JSON and has our format
                if (hasattr(response, 'body') and 
                    response.headers.get('content-type') == 'application/json'):
                    try:
                        original_data = json.loads(response.body.decode())
                        
                        # If it's already our standardized format, don't modify
                        if 'success' in original_data:
                            return response
                            
                        # Convert to standardized format
                        standardized_response = create_success_response(
                            data=original_data,
                            status_code=response.status_code
                        )
                        return standardized_response
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # If not JSON, return as-is
                        return response
            
            return response
            
        except Exception as e:
            # Let exception handlers deal with errors
            raise e
        finally:
            process_time = time.time() - start_time
            print(f"Request completed in {process_time:.4f}s")