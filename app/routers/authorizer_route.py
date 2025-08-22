from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.controllers.authorizer_controller import authorize_user_async
from app.schemas.authorize_validation import AuthorizeRequest
from app.utils.response_utils import create_success_response, create_error_response
from app.utils.logger_utils import logger

router = APIRouter(tags=["Authorizer"])

@router.post("/authorize")
async def authorize(
    request: AuthorizeRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        token = request.request.userAttributes.custom_token
        site = request.request.userAttributes.site

        logger.info(f"Token received: {token}..., site: {site}")

        result_data = await authorize_user_async(token=token, site=site, db=db)
        
        return create_success_response(
            data=result_data,
            message="Authorization successful"
        )

    except KeyError as e:
        logger.error(f"Missing field in request: {e}")
        return create_error_response(
            message=f"Missing field: {e}",
            status_code=400
        )

    except HTTPException as he:
        return create_error_response(
            message=he.detail,
            status_code=he.status_code
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_error_response(
            message=f"Unexpected error: {str(e)}",
            status_code=500
        )