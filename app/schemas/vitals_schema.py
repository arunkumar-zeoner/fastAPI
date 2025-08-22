from pydantic import BaseModel
from typing import Optional, Dict

class VitalsLatest(BaseModel):
    blood_glucose: Optional[float]
    blood_glucose_time: Optional[str]
    ketone: Optional[float]
    ketone_time: Optional[str]
    systolic: Optional[int]
    diastolic: Optional[int]
    bp_time: Optional[str]
    height_cm: Optional[float]
    height_time: Optional[str]
    weight_kg: Optional[float]
    weight_time: Optional[str]
    pulse: Optional[int]
    pulse_time: Optional[str]
    bmr: Optional[float]
    bmr_time: Optional[str]
    spo2: Optional[int]
    spo2_time: Optional[str]

class VitalsAverages(BaseModel):
    avg_glucose: Optional[float]
    avg_ketone: Optional[float]
    avg_systolic: Optional[float]
    avg_diastolic: Optional[float]
    avg_height: Optional[float]
    avg_weight: Optional[float]
    avg_pulse: Optional[float]
    avg_bmr: Optional[float]
    avg_spo2: Optional[float]

class FormVitals(BaseModel):
    id: int
    date: str
    height: Optional[float]
    weight: Optional[float]
    BMI: Optional[float]
    bps: Optional[str]

class VitalsResponse(BaseModel):
    latest: VitalsLatest
    averages: VitalsAverages
    form_vitals: Optional[FormVitals]
