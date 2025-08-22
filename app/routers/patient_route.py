from fastapi import APIRouter, Body, Depends, Request, Query, HTTPException
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.utils.response_utils import create_success_response, create_error_response
from app.controllers.patient_controller import get_patient_details
from app.dependencies.auth import VerifyTokenWithEmail
from app.utils.logger_utils import logger
from app.schemas.patient_schema import PatientRequest, PatientDetailsResponse

router = APIRouter()

@router.post("/patient-details", response_model=PatientDetailsResponse)
async def patient_details_post(
    request: Request,
    payload: PatientRequest,
    claims: Dict[str, Any] = Depends(VerifyTokenWithEmail()),
    db: AsyncSession = Depends(get_db)
):

    try:
        result = await get_patient_details(payload=payload.dict(), db=db)
        logger.info(f"Patient details fetched successfully for email: {claims.get('email')}")
        return create_success_response(result, "Patient details fetched successfully")
    except ValueError as ve:
        logger.warning(f"Validation error: {str(ve)}")
        return create_error_response(str(ve), 400)
    except Exception as e:
        logger.error(f"Error fetching patient details: {str(e)}", exc_info=True)
        return create_error_response("Internal server error", 500)