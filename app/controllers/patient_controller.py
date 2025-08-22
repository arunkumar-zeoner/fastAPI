from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, date
from sqlalchemy.future import select
from app.models.patient_data_model import PatientData
from app.exceptions.custom_exceptions import NotFoundException
from app.services.patients.patient_details_service import (
    get_patients_data_optimized,
    get_single_patient_data_optimized
)
from app.utils.logger_utils import logger

async def get_patient_details(payload: dict, db: AsyncSession):

    logger.info(f"payload: {payload}")
    site = payload.get("site")
    pid = payload.get("pid")
    page = payload.get("page", 1)
    page_size = payload.get("page_size", 10)

    # Validate parameters
    if not site:
        raise ValueError("Site parameter is required")
    
    if page < 1:
        raise ValueError("Page must be >= 1")
        
    if page_size < 1 or page_size > 100:
        raise ValueError("Page size must be between 1 and 100")

    # Create event context for the service functions
    event = {
        "body": payload,
        "queryStringParameters": payload
    }
    context = {}

    try:
        if pid:
            # Individual patient request
            logger.info(f"Processing individual patient request for site: {site}, pid: {pid}")
            
            # Validate pid
            # try:
            #     pid = int(pid)
            #     if pid <= 0:
            #         raise ValueError("Patient ID must be a positive integer")
            # except ValueError:
            #     raise ValueError("Patient ID must be a valid integer")

            # Get single patient data
            result = await get_single_patient_data_optimized(db, event, context, pid)
            
            if not result:
                raise NotFoundException(status_code=404, detail=f"Patient with ID {pid} not found")

            return {
                'patients': [result],
                'meta': {
                    'total_patients': 1,
                    'current_page': 1,
                    'total_pages': 1,
                    'patients_in_response': 1,
                    'individual_patient': True
                },
                'performance': {
                    'optimized': True,
                    'individual_patient': True
                }
            }
        else:
            # Batch request
            logger.info(f"Processing batch request for site: {site}, page: {page}, page_size: {page_size}")
            
            # Get batch patient data
            result = await get_patients_data_optimized(db, event, context, page, page_size)
            
            if not result['patients']:
                return {
                    'patients': [],
                    'pagination': result['pagination'],
                    'message': 'No patients found',
                    'performance': {
                        'optimized': True
                    }
                }

            return {
                'patients': result['patients'],
                'pagination': result['pagination'],
                'meta': {
                    'total_patients': result['pagination']['total'],
                    'current_page': page,
                    'total_pages': result['pagination']['total_pages'],
                    'patients_in_response': len(result['patients'])
                },
                'performance': {
                    'optimized': True,
                    'batch_processed': True
                }
            }

    except Exception as e:
        logger.error(f"Error in get_patient_details: {str(e)}")
        raise
