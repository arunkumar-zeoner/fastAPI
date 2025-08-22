# app/utils/response_utils.py
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, Optional

def serialize_value(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

def convert_serializable(obj):
    if isinstance(obj, dict):
        return {k: convert_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_serializable(i) for i in obj]
    else:
        return serialize_value(obj)
    
class SuccessResponse(BaseModel):
    statusCode: int
    message: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    statusCode: int
    message: str
    success: bool = False
    errorCode: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

def create_success_response(
    data: Optional[Dict[str, Any]] = None, 
    message: str = "Success", 
    status_code: int = 200
) -> JSONResponse:
    if data:
        data = convert_serializable(data)
    
    content = SuccessResponse(
        statusCode=status_code,
        message=message,
        data=data
    ).model_dump(exclude_none=True)
    
    return JSONResponse(status_code=status_code, content=content)

def create_error_response(
    message: str, 
    status_code: int = 400, 
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response"""
    content = ErrorResponse(
        statusCode=status_code,
        message=message,
        errorCode=error_code,
        details=details
    ).model_dump(exclude_none=True)
    
    return JSONResponse(status_code=status_code, content=content)