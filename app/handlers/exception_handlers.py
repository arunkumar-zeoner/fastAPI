# app/handlers/exception_handlers.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging
from typing import Union

from app.exceptions.custom_exceptions import CustomHTTPException
from app.exceptions.auth_exceptions import (
    JWKSException,
    TokenExpiredException,
    InvalidTokenException,
    TokenDecodeException,
    MissingTokenClaimException
)

logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: Union[RequestValidationError, ValidationError]):
    """Handle validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "statusCode": 422,
            "message": "Validation error",
            "success": False,
            "errors": errors
        }
    )

async def custom_http_exception_handler(request: Request, exc: CustomHTTPException):
    """Handle custom HTTP exceptions"""
    content = {
        "statusCode": exc.status_code,
        "message": exc.detail,
        "success": False
    }
    
    if hasattr(exc, 'error_code'):
        content["errorCode"] = exc.error_code
    
    return JSONResponse(status_code=exc.status_code, content=content)

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle standard HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": exc.status_code,
            "message": exc.detail,
            "success": False
        }
    )

async def jwks_exception_handler(request: Request, exc: JWKSException):
    """Handle JWKS related exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": exc.status_code,
            "message": exc.detail,
            "success": False,
            "errorCode": "JWKS_ERROR"
        }
    )

async def token_exception_handler(request: Request, exc: Union[TokenExpiredException, InvalidTokenException, TokenDecodeException, MissingTokenClaimException]):
    """Handle token validation exceptions"""
    error_code = "TOKEN_ERROR"
    if isinstance(exc, TokenExpiredException):
        error_code = "TOKEN_EXPIRED"
    elif isinstance(exc, InvalidTokenException):
        error_code = "INVALID_TOKEN"
    elif isinstance(exc, TokenDecodeException):
        error_code = "TOKEN_DECODE_ERROR"
    elif isinstance(exc, MissingTokenClaimException):
        error_code = "MISSING_CLAIM"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": exc.status_code,
            "message": exc.detail,
            "success": False,
            "errorCode": error_code
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "statusCode": 500,
            "message": "Internal server error",
            "success": False
        }
    )