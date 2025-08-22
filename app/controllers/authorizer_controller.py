from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.users_secure_model import UserSecure
from app.utils.auth_utils import authenticate_cognito_async
from fastapi import HTTPException
from app.utils.logger_utils import logger

async def validate_openemr_token_async(token: str, db: AsyncSession) -> bool:
    try:
        stmt = select(UserSecure).where(UserSecure.current_session_id == token)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        return user is not None
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")

async def authorize_user_async(token: str, site: str, db: AsyncSession):
    try:
        if not token or not site:
            raise HTTPException(status_code=400, detail="Missing OpenEMR token or site")

        is_valid = await validate_openemr_token_async(token, db)
        if not is_valid:
            logger.warning(f"Invalid OpenEMR token")
            raise HTTPException(status_code=401, detail="Invalid OpenEMR token")

        # This should return raw data, not formatted response
        cognito_tokens = await authenticate_cognito_async()
        return cognito_tokens

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Authorization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authorization failed: {str(e)}")