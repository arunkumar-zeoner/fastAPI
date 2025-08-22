from fastapi import HTTPException
from typing import Optional, Dict, Any

class CustomHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=message)
        self.error_code = error_code
        self.details = details

# Specific exception types
class ValidationException(CustomHTTPException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )

class AuthenticationException(CustomHTTPException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=401,
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details
        )

class AuthorizationException(CustomHTTPException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=403,
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=details
        )

class NotFoundException(CustomHTTPException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=404,
            message=message,
            error_code="NOT_FOUND",
            details=details
        )

class InternalServerException(CustomHTTPException):
    def __init__(self, message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            message=message,
            error_code="INTERNAL_ERROR",
            details=details
        )