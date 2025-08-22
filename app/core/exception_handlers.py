from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from app.handlers.exception_handlers import (
    validation_exception_handler,
    custom_http_exception_handler,
    http_exception_handler,
    general_exception_handler,
    jwks_exception_handler,
    token_exception_handler
)
from app.exceptions.custom_exceptions import CustomHTTPException
from app.exceptions.auth_exceptions import (
    JWKSException,
    TokenExpiredException,
    InvalidTokenException,
    TokenDecodeException,
    MissingTokenClaimException
)

def register_exception_handlers(app):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(CustomHTTPException, custom_http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(JWKSException, jwks_exception_handler)
    app.add_exception_handler(TokenExpiredException, token_exception_handler)
    app.add_exception_handler(InvalidTokenException, token_exception_handler)
    app.add_exception_handler(TokenDecodeException, token_exception_handler)
    app.add_exception_handler(MissingTokenClaimException, token_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
