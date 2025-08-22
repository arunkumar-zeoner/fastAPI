from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime, date

class PatientRequest(BaseModel):
    site: str = Field(..., description="Site identifier")
    pid: Optional[int] = Field(None, description="Individual patient ID")
    page: Optional[int] = Field(1, ge=1, description="Page number for pagination")
    page_size: Optional[int] = Field(10, ge=1, le=100, description="Number of patients per page")
    program_id: Optional[str] = Field(None, description="Program filter")

    @field_validator("pid", mode="before")
    def empty_string_to_none(cls, v):
        """Convert empty string or None to None and cast to int if possible"""
        if v == "" or v is None:
            return None
        return int(v)
    
class VitalReading(BaseModel):
    time: Optional[str] = None
    value: Any

class EnrollmentInfo(BaseModel):
    enrollment_id: int
    patient_id: str
    status: str
    current_step: str
    progress_percentage: float
    start_date: Optional[str]
    end_date: Optional[str]
    last_updated: Optional[str]
    total_programs: int
    completed_programs: int
    fname: Optional[str]
    lname: Optional[str]
    DOB: Optional[str]

class ProgramDetail(BaseModel):
    program_id: str
    program_name: str
    program_code: str
    status: str
    is_active: bool
    sequence: Optional[int]

class ProgressSummary(BaseModel):
    total_programs: int
    completed_programs: int
    progress_percentage: float
    calculated_percentage: float

class EnrollmentData(BaseModel):
    patient_id: int
    enrollment_info: Optional[EnrollmentInfo]
    programs: List[ProgramDetail]
    progress_summary: ProgressSummary

class VitalsData(BaseModel):
    latest: Dict[str, Any] = {}
    averages: Dict[str, Any] = {}
    form_vitals: Dict[str, Any] = {}

class PatientResponse(BaseModel):
    pid: int
    id: int
    fname: Optional[str]
    lname: Optional[str]
    mname: Optional[str]
    DOB: Optional[str]
    sex: Optional[str]
    phone_cell: Optional[str]
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    email: Optional[str]
    
    # Enhanced fields from Lambda code
    enrollment: Dict[str, Any] = {}
    heartAge: Optional[Dict[str, Any]] = None
    
    # Vitals data
    get_vitalsheight: Optional[float] = None
    height: Optional[str] = None
    height_data_time: Optional[str] = None
    avg_height: Optional[str] = None
    
    weight: Optional[str] = None
    weight_data_time: Optional[str] = None
    weight1: Optional[float] = None
    avg_weight: Optional[str] = None
    
    bmi: Optional[float] = None
    
    blood_pressure: Optional[str] = None
    blood_pressure_time: Optional[str] = None
    avg_bp: Optional[str] = None
    
    glucose_data: Optional[str] = None
    glucose_data_time: Optional[str] = None
    avg_glucose: Optional[str] = None
    
    ketone_data: Optional[str] = None
    ketone_data_time: Optional[str] = None
    avg_ketone: Optional[str] = None
    
    pulse: Optional[str] = None
    pulse_data_time: Optional[str] = None
    avg_pulse: Optional[str] = None
    
    bmr: Optional[str] = None
    bmr_data_time: Optional[str] = None
    avg_bmr: Optional[str] = None
    
    spo2: Optional[str] = None
    spo2_data_time: Optional[str] = None
    avg_spo2: Optional[str] = None
    
    # Health flags
    hypertension: int = 0
    diabetes: int = 0
    smoking: int = 0
    
    # Encounter data
    encounter: Optional[str] = None
    encounterStatus: int = 0
    
    # Progress tracking
    days_remaining: int = 0
    duration: int = 0
    need_count: int = 0
    
    # Scores
    scores: Any = "Score not found"
    
    # Vitals arrays
    pb: List[Dict[str, Any]] = []
    pulse_list: List[Dict[str, Any]] = []
    weight_list: List[Dict[str, Any]] = []
    spo2_list: List[Dict[str, Any]] = []
    glucose_list: List[Dict[str, Any]] = []
    ketone_list: List[Dict[str, Any]] = []

class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class PerformanceMetrics(BaseModel):
    processing_time_seconds: float
    optimized: bool = True
    individual_patient: Optional[bool] = None
    batch_processed: Optional[bool] = None

class MetaInfo(BaseModel):
    total_patients: int
    current_page: int
    total_pages: int
    patients_in_response: int
    individual_patient: Optional[bool] = None

class PatientDetailsResponse(BaseModel):
    success: bool
    timestamp: str
    data: Dict[str, Any]
    message: Optional[str] = None
    meta: Optional[MetaInfo] = None
    performance: Optional[PerformanceMetrics] = None