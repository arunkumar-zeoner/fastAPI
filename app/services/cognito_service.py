import os
import boto3
import logging
from app.utils.response_utils import create_success_response, create_error_response

logger = logging.getLogger(__name__)

def get_cognito_client():
    return boto3.client("cognito-idp", region_name="us-east-1")

async def authenticate_cognito_async():
    client_id = os.getenv("COGNITO_CLIENT_ID")
    username = os.getenv("COGNITO_USERNAME")
    password = os.getenv("COGNITO_PASSWORD")

    if not all([client_id, username, password]):
        logger.error("Cognito credentials missing")
        return create_error_response("Cognito configuration error", status_code=500)

    client = get_cognito_client()

    try:
        auth_response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        id_token = auth_response.get("AuthenticationResult", {}).get("IdToken")
        if not id_token:
            return create_error_response("Authentication failed: No IdToken returned", status_code=500)

        return create_success_response(data={"idToken": id_token}, message="Authenticated successfully")

    except client.exceptions.NotAuthorizedException as e:
        logger.error("Cognito authentication failed: %s", e)
        return create_error_response("Invalid Cognito credentials", status_code=401)

    except Exception as e:
        logger.exception("Unexpected Cognito authentication error")
        return create_error_response(f"Cognito authentication failed: {str(e)}", status_code=500)
