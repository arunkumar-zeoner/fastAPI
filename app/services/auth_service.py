import os
import logging
import boto3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.users_secure_model import UserSecure
from app.utils.response_utils import create_error_response, create_success_response

logger = logging.getLogger(__name__)

cognito_client = boto3.client("cognito-idp", region_name="us-east-1")


async def validate_openemr_token_async(token: str, db: AsyncSession) -> bool:
    """Check if the OpenEMR token exists in DB."""
    stmt = select(UserSecure).where(UserSecure.current_session_id == token)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user is not None


async def authenticate_cognito_async():
    """Authenticate with AWS Cognito and return ID token wrapped in success/error response."""
    try:
        client_id = os.getenv("COGNITO_CLIENT_ID")
        username = os.getenv("COGNITO_USERNAME")
        password = os.getenv("COGNITO_PASSWORD")

        if not all([client_id, username, password]):
            logger.error("Cognito credentials missing in environment variables")
            return create_error_response("Cognito configuration error", status_code=500)

        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        id_token = auth_response["AuthenticationResult"]["IdToken"]
        return create_success_response(data={"idToken": id_token}, message="Cognito authentication successful")

    except cognito_client.exceptions.NotAuthorizedException:
        logger.error("Cognito authentication failed: invalid credentials")
        return create_error_response("Invalid Cognito credentials", status_code=401)

    except Exception as e:
        logger.exception("Error during Cognito authentication")
        return create_error_response("Cognito authentication failed", status_code=500, data={"error": str(e)})
