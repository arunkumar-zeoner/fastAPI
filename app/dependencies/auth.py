from fastapi import Header, Request, HTTPException
from typing import Dict, Any
from app.utils.auth_utils import validate_id_token
from app.exceptions.custom_exceptions import AuthenticationException, AuthorizationException
from app.utils.logger_utils import logger

class VerifyToken:
    async def __call__(self, authorization: str = Header(...)) -> Dict[str, Any]:
        if not authorization:
            logger.warning("Authorization header missing")
            raise AuthenticationException("Authorization header missing")

        try:
            token_type, token = authorization.split()
            if token_type.lower() != "bearer":
                logger.warning(f"Invalid token type: {token_type}")
                raise AuthenticationException("Invalid token type. Use 'Bearer'")
        except ValueError:
            logger.warning("Malformed Authorization header")
            raise AuthenticationException("Invalid Authorization header format. Expected: 'Bearer <token>'")

        claims_response = await validate_id_token(token)
        if claims_response.get("statusCode") != 200:
            logger.error(f"Token validation failed: {claims_response.get('message')}")
            raise AuthenticationException(claims_response.get("message", "Invalid token"))

        claims = claims_response.get("data", {})
        if not claims.get("email"):
            logger.warning("Token missing email claim")
            raise AuthenticationException("Token missing email claim")

        return claims

class VerifyTokenWithEmail:
    async def __call__(self, request: Request, authorization: str = Header(...)) -> Dict[str, Any]:
        logger.info("Starting token and email verification")

        token_verifier = VerifyToken()
        claims = await token_verifier(authorization)

        try:
            body = await request.json()
            request_email = body.get("email")
        except Exception as e:
            logger.error(f"Failed to parse request body: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail="Invalid request body")

        if not request_email:
            logger.warning("Email missing in request body")
            raise HTTPException(status_code=400, detail="Email required in request body")

        token_email = claims.get("email")
        if token_email != request_email:
            logger.warning(f"Email mismatch: token email ({token_email}) vs request email ({request_email})")
            raise AuthorizationException("Email mismatch: token email and request email")

        logger.info(f"Email verified successfully: {token_email}")
        return claims
