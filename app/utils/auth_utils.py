import os
import requests
import boto3
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from app.exceptions.auth_exceptions import *
from app.utils.logger_utils import logger
from jose import jwt, jwk
from jose.utils import base64url_decode

load_dotenv()

COGNITO_REGION = os.getenv("AWS_REGION", "us-east-1")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL")
APP_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_USERNAME = os.getenv("COGNITO_USERNAME")
COGNITO_PASSWORD = os.getenv("COGNITO_PASSWORD")

JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
cognito_client = boto3.client("cognito-idp", region_name=COGNITO_REGION)

def get_jwks():
    try:
        logger.info("Fetching JWKS from Cognito")
        response = requests.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        jwks = response.json()

        if "keys" not in jwks:
            logger.error("JWKS response missing 'keys'")
            raise JWKSException("Invalid JWKS response")

        return {k["kid"]: k for k in jwks["keys"]}
    except Exception as e:
        logger.error(f"JWKS fetch error: {str(e)}", exc_info=True)
        raise JWKSException(f"JWKS fetch failed: {str(e)}")

def verify_signature(id_token: str, jwks_keys: dict):
    headers = jwt.get_unverified_header(id_token)
    kid = headers.get("kid")
    if not kid or kid not in jwks_keys:
        raise InvalidTokenException("Invalid token key")

    key_data = jwks_keys[kid]
    key = jwk.construct(key_data)

    message, encoded_signature = id_token.rsplit('.', 1)
    decoded_signature = base64url_decode(encoded_signature.encode())

    if not key.verify(message.encode(), decoded_signature):
        raise InvalidTokenException("Signature verification failed")

    return jwt.decode(
        id_token,
        key,
        algorithms=["RS256"],
        audience=APP_CLIENT_ID,
    )

async def validate_id_token(id_token: str) -> dict:
    try:
        logger.info("Validating ID token")
        jwks_keys = get_jwks()
        payload = verify_signature(id_token, jwks_keys)

        if datetime.utcnow().timestamp() > payload["exp"]:
            logger.warning("Token expired")
            raise TokenExpiredException()

        logger.info(f"Token validated for email: {payload.get('email')}")
        return {"statusCode": 200, "data": payload}

    except InvalidTokenException as e:
        logger.warning(str(e))
        raise
    except ExpiredSignatureError:
        logger.warning("Token signature expired")
        raise TokenExpiredException()
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}", exc_info=True)
        raise InvalidTokenException(f"Token validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected token validation error: {str(e)}", exc_info=True)
        raise TokenValidationException(f"Token validation error: {str(e)}", 500)

async def authenticate_cognito_async():
    try:
        logger.info("Authenticating with Cognito")

        if not APP_CLIENT_ID or not COGNITO_USERNAME or not COGNITO_PASSWORD:
            raise Exception("Missing Cognito environment variables")

        auth_response = cognito_client.initiate_auth(
            ClientId=APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": COGNITO_USERNAME, "PASSWORD": COGNITO_PASSWORD},
        )

        id_token = auth_response["AuthenticationResult"]["IdToken"]
        logger.info("Cognito authentication successful")
        return {"idToken": id_token}

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning("Invalid Cognito credentials")
        raise Exception("Invalid Cognito credentials")
    except ClientError as e:
        logger.error(f"AWS error: {e.response['Error']['Message']}", exc_info=True)
        raise Exception(f"AWS error: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Cognito authentication failed: {str(e)}", exc_info=True)
        raise Exception(f"Cognito authentication failed: {str(e)}")
