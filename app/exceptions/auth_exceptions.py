from fastapi import HTTPException

class JWKSException(HTTPException):
    """Exception for JWKS related errors"""
    def __init__(self, message: str):
        super().__init__(status_code=500, detail=message)

class TokenValidationException(HTTPException):
    """Base exception for token validation errors"""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=message)

class TokenExpiredException(TokenValidationException):
    """Exception for expired tokens"""
    def __init__(self, message: str = "Token expired"):
        super().__init__(message=message, status_code=401)

class InvalidTokenException(TokenValidationException):
    """Exception for invalid tokens"""
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message=message, status_code=401)

class TokenDecodeException(TokenValidationException):
    """Exception for token decoding errors"""
    def __init__(self, message: str = "Token decode error"):
        super().__init__(message=message, status_code=401)

class MissingTokenClaimException(TokenValidationException):
    """Exception for missing token claims"""
    def __init__(self, claim_name: str):
        super().__init__(message=f"Token missing required claim: {claim_name}", status_code=401)