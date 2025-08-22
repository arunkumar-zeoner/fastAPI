from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.users_secure_model import UserSecure

async def validate_openemr_token_async(token: str, db: AsyncSession) -> bool:
    stmt = select(UserSecure).where(UserSecure.current_session_id == token)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user is not None
