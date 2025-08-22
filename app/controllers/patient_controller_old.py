from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, date
from sqlalchemy.future import select
from app.models.patient_data_model import PatientData
from app.exceptions.custom_exceptions import NotFoundException
from app.services.patients import *
import time
import logging
import math

logger = logging.getLogger(__name__)

def serialize_datetime_fields(data: dict) -> dict:
    for key, value in data.items():
        if isinstance(value, (datetime, date)):
            data[key] = value.strftime("%Y-%m-%d %H:%M:%S")
    return data

async def get_remaining_days(db: AsyncSession, pid: int):
    """Calculate remaining days, duration, and need count for a patient"""
    try:
        # Get encounter data
        encounter_query = text("""
            SELECT * FROM form_encounter 
            WHERE date_end IS NOT NULL AND encounter_status = 'open' AND pid = :pid
        """)
        result = await db.execute(encounter_query, {"pid": pid})
        enc_data = result.mappings().first()

        if enc_data:
            end_date = enc_data.get('date_end')
            today = datetime.now()
            today_date = today.date()

            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d')

            # Calculate remaining days
            delta = end_date - today
            left_days = max(math.ceil(delta.total_seconds() / 86400), 0)
            days_remaining = max(left_days, 0)

            # Check if there's a reading for today
            reading_query = text("""
                SELECT * 
                FROM api_vitals_data 
                WHERE pid = :pid AND api_type != 'googlefit' AND reading_date = :today_date 
                LIMIT 1
            """)
            reading_result = await db.execute(reading_query, {"pid": pid, "today_date": today_date})
            reading_exists_today = reading_result.mappings().first() is not None

            if reading_exists_today:
                days_remaining = max(days_remaining - 1, 0)

            # Calculate need count
            start_date_str = enc_data['date']
            end_date_str = enc_data['date_end']
            need_count_query = text("""
                SELECT COUNT(DISTINCT reading_date) AS reading_count 
                FROM api_vitals_data 
                WHERE pid = :pid AND api_type != 'googlefit' 
                AND reading_date BETWEEN :start_date AND :end_date
            """)
            need_result = await db.execute(need_count_query, {
                "pid": pid, 
                "start_date": start_date_str, 
                "end_date": end_date_str
            })
            need_row = need_result.mappings().first()
            reading_count = min(need_row['reading_count'] if need_row and need_row['reading_count'] else 0, 16)
            need_count = 16 - reading_count

            # Calculate duration
            encounter_id = enc_data['encounter']
            duration_query = text("""
                SELECT SUM(timespent) AS duration 
                FROM rpm_encounter 
                WHERE pid = :pid AND eid = :encounter_id AND is_deleted = 0
            """)
            duration_result = await db.execute(duration_query, {
                "pid": pid, 
                "encounter_id": encounter_id
            })
            duration_row = duration_result.mappings().first()
            duration = duration_row['duration'] if duration_row and duration_row['duration'] else 0

            return days_remaining, duration, need_count
        else:
            return 0, 0, 0
    except Exception as e:
        logger.error(f"Error calculating remaining days: {str(e)}")
        return 0, 0, 0

async def get_patient_details(payload: dict, db: AsyncSession, request):
    start_time = time.time()
    site = payload.get("site")
    pid = int(payload.get("pid"))
    page = int(payload.get("page", 1))
    page_size = int(payload.get("page_size", 20))

    if not pid:
        raise ValueError("pid is required for this function (single patient mode)")

    # Fetch single patient
    result = await db.execute(select(PatientData).where(PatientData.pid == pid))
    patient = result.scalars().first()

    if not patient:
        raise NotFoundException(status_code=404, detail="User not found")

    # Convert ORM object to dict
    patient_row = {k: v for k, v in patient.__dict__.items() if k != "_sa_instance_state"}
    patient_row["id"] = patient_row.get("pid")

    # Fetch batch data
    enrollment_data = await get_batch_enrollment_data(db_conn=db, event=payload, patient_ids=[pid], request=request)
    vitals_data = await get_batch_vitals_data(db, [pid])
    additional_data = await get_batch_patient_data(db=db, patient_ids=[pid])

    patient_vitals = vitals_data.get(pid, {"latest": {}, "averages": {}, "form_vitals": {}})
    patient_additional = additional_data.get(pid, {"history": {}, "encounter": {}, "scores": {}})
    patient_enrollment = enrollment_data.get(pid, {})

    patient_row["enrollment"] = patient_enrollment

    # --- DOB Formatting ---
    dob_value = patient_row.get("DOB")
    if dob_value:
        dob = dob_value if isinstance(dob_value, (datetime, date)) else datetime.strptime(dob_value, "%Y-%m-%d")
        patient_row["DOB"] = dob.strftime("%d %B %Y").lstrip("0")  # Windows-safe
    else:
        patient_row["DOB"] = ""

    # --- Heart Age ---
    try:
        patient_row["heartAge"] = await calculate_heart_age_optimized(
            patient_row,
            patient_additional["history"],
            patient_vitals
        )
    except Exception as e:
        logger.error(f"Error calculating heart age: {str(e)}")
        patient_row["heartAge"] = {"statusCode": 200, "body": 3}  # Default fallback

    # --- Vitals ---
    latest_vitals = patient_vitals["latest"]
    averages = patient_vitals["averages"]
    form_vitals = patient_vitals["form_vitals"]

    # Height
    height_cm = latest_vitals.get("height_cm") or form_vitals.get("height")
    patient_row["get_vitalsheight"] = height_cm
    height_inc = await cminc(height_cm) if height_cm else None
    patient_row["height"] = f"{height_inc}/{round(float(height_cm), 1)}" if height_inc and height_cm else ""
    patient_row["height_data_time"] = latest_vitals.get("height_time", "")

    avg_height = averages.get("avg_height")
    avg_height_inc = await cminc(avg_height) if avg_height else None
    patient_row["avg_height"] = f"{avg_height_inc}/{round(float(avg_height), 1)}" if avg_height_inc and avg_height else ""

    # Weight
    weight_kg = latest_vitals.get("weight_kg") if latest_vitals.get("weight_kg") not in [None, 0, "", "0"] else form_vitals.get("weight")
    weight_kg_float = float(weight_kg) if weight_kg else 0.0

    if latest_vitals.get("weight_kg") not in [None, 0, "", "0"]:
        weight_lb = round(weight_kg_float * 2.20462, 1) if weight_kg_float > 0 else ""
        weight_fn = weight_kg_float
        weight_data_time = latest_vitals.get("weight_time", "")
    else:
        weight_lb = weight_kg_float if weight_kg_float > 0 else ""
        weight_fn = round(weight_kg_float * 0.453592, 1)
        weight_data_time = form_vitals.get("date", "")

    patient_row["weight"] = f"{weight_lb}" if weight_lb else ""
    patient_row["weight_data_time"] = weight_data_time
    patient_row["weight1"] = round(weight_kg_float, 1) if weight_kg_float > 0 else ""

    avg_weight = averages.get("avg_weight", 0)
    avg_weight_lb = round(float(avg_weight) * 2.20462, 1) if avg_weight else ""
    patient_row["avg_weight"] = f"{avg_weight_lb}/{round(float(avg_weight), 1)}" if avg_weight_lb else ""

    # BMI
    height_m = float(height_cm) / 100 if height_cm else 0.0
    bmi = round(weight_kg_float / (height_m * height_m), 1) if weight_kg_float > 0 and height_m > 0 else None
    patient_row["bmi"] = bmi

    # Blood Pressure
    systolic = latest_vitals.get("systolic")
    diastolic = latest_vitals.get("diastolic")
    patient_row["blood_pressure"] = f"{systolic}/{diastolic}" if systolic and diastolic else ""
    patient_row["blood_pressure_time"] = latest_vitals.get("bp_time", "")

    avg_systolic = averages.get("avg_systolic")
    avg_diastolic = averages.get("avg_diastolic")
    patient_row["avg_bp"] = f"{avg_systolic}/{avg_diastolic}" if avg_systolic and avg_diastolic else ""

    # Other vitals
    patient_row["glucose_data"] = latest_vitals.get("blood_glucose", "")
    patient_row["glucose_data_time"] = latest_vitals.get("blood_glucose_time", "")
    patient_row["avg_glucose"] = averages.get("avg_glucose", "")

    patient_row["ketone_data"] = latest_vitals.get("ketone", "")
    patient_row["ketone_data_time"] = latest_vitals.get("ketone_time", "")
    patient_row["avg_ketone"] = averages.get("avg_ketone", "")

    patient_row["pulse"] = latest_vitals.get("pulse", "")
    patient_row["pulse_data_time"] = latest_vitals.get("pulse_time", "")
    patient_row["avg_pulse"] = averages.get("avg_pulse", "")

    patient_row["bmr"] = latest_vitals.get("bmr", "")
    patient_row["bmr_data_time"] = latest_vitals.get("bmr_time", "")
    patient_row["avg_bmr"] = averages.get("avg_bmr", "")

    patient_row["spo2"] = latest_vitals.get("spo2", "")
    patient_row["spo2_data_time"] = latest_vitals.get("spo2_time", "")
    patient_row["avg_spo2"] = averages.get("avg_spo2", "")

    # Hypertension & diabetes flags
    usertext11 = patient_additional["history"].get("usertext11", "")
    new_ht, diabetes = 0, 0
    if usertext11:
        ht_value = usertext11.split("|")
        if "ht" in ht_value:
            new_ht = 1
        if "db" in ht_value:
            diabetes = 1
    patient_row["hypertension"] = new_ht
    patient_row["diabetes"] = diabetes

    # Smoking
    patient_row["smoking"] = 0
    tobacco_info = patient_additional["history"].get("tobacco", "")
    if tobacco_info and "current" in tobacco_info.lower():
        patient_row["smoking"] = 1

    # Encounter
    encounter_data = patient_additional["encounter"]
    patient_row["encounter"] = encounter_data.get("encounter", "")
    patient_row["encounterStatus"] = 0

    # Remaining days/duration - Calculate actual values
    days_remaining, duration, need_count = await get_remaining_days(db, pid)
    patient_row["days_remaining"] = days_remaining
    patient_row["duration"] = duration
    patient_row["need_count"] = need_count

    # Scores
    patient_row["scores"] = patient_additional.get("scores", {"statusCode": 200, "body": {}})

    # Vital data arrays
    # Blood pressure list
    systolic = latest_vitals.get("systolic")
    diastolic = latest_vitals.get("diastolic")
    if systolic and diastolic:
        patient_row["pb"] = [{"pb": f"{systolic}/{diastolic}", "time": "", "pbs": str(systolic)}]
    else:
        patient_row["pb"] = []

    # Pulse list
    pulse = latest_vitals.get("pulse")
    if pulse:
        patient_row["pulse_list"] = [{"pulse": str(pulse), "time": ""}]
    else:
        patient_row["pulse_list"] = []

    # Weight list
    if weight_kg_float > 0:
        patient_row["weight_list"] = [{"weight": weight_kg_float, "time": ""}]
    else:
        patient_row["weight_list"] = []

    # SpO2 list
    spo2 = latest_vitals.get("spo2")
    if spo2:
        patient_row["spo2_list"] = [{"spo2": spo2, "time": ""}]
    else:
        patient_row["spo2_list"] = []

    # Glucose list
    glucose = latest_vitals.get("blood_glucose")
    if glucose:
        patient_row["glucose_list"] = [{"glucose": glucose, "time": ""}]
    else:
        patient_row["glucose_list"] = []

    # Ketone list
    ketone = latest_vitals.get("ketone")
    if ketone:
        patient_row["ketone_list"] = [{"ketone": ketone, "time": ""}]
    else:
        patient_row["ketone_list"] = []

    patient_row = serialize_datetime_fields(patient_row)
    
    # Calculate processing time
    processing_time = time.time() - start_time
    
    # Format response to match expected structure
    response_data = {
        "patients": [patient_row],
        "meta": {
            "total_patients": 1,
            "current_page": page,
            "total_pages": 1,
            "patients_in_response": 1,
            "individual_patient": True
        },
        "performance": {
            "processing_time_seconds": round(processing_time, 6),
            "optimized": True,
            "individual_patient": True
        }
    }
    
    return response_data