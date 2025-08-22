import json
import math
import numbers
from typing import List, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from app.models import PatientEnrollment, PatientData, EnrollmentPrograms, ListOptions
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, bindparam
from app.utils.logger_utils import logger


async def get_batch_enrollment_data(
    db_conn, event, patient_ids: List[int], request
) -> Dict[int, Dict]:

    if not patient_ids:
        return {}

    try:
        logger.info(f"Fetching enrollment for {len(patient_ids)} patients in batch")

        enrollment_data = await get_batch_enrollment_status(request, patient_ids, db_conn)

        # Format the result
        formatted_enrollment_data = {}
        for pid in patient_ids:
            detail = enrollment_data.get(pid)
            if detail and detail.get("enrollment_info"):
                formatted_enrollment_data[pid] = {
                    "patient_id": pid,
                    "enrollments": [detail],
                    "total_enrollments": 1,
                }
            else:
                formatted_enrollment_data[pid] = {
                    "patient_id": pid,
                    "enrollments": [],
                    "total_enrollments": 0,
                }

        return formatted_enrollment_data

    except Exception as e:
        logger.error(f"Error in batch enrollment fetch: {str(e)}", exc_info=True)
        return {pid: {} for pid in patient_ids}

async def get_batch_enrollment_status(
    request: Request,
    patient_ids: List[int],
    db: AsyncSession
) -> Dict[int, Dict]:

    body_params = await request.json()
    query_params = dict(request.query_params)
    program_filter = body_params.get("program_id") or query_params.get("program_id")

    enrollment_data = {}

    try:
        # Prepare placeholders and parameters
        pid_placeholders = ','.join([f":pid{i}" for i in range(len(patient_ids))])
        pid_params = {f"pid{i}": pid for i, pid in enumerate(patient_ids)}

        # 🚀 BATCH QUERY 1
        enrollment_sql = f"""
            SELECT
                pe.id AS enrollment_id,
                pe.pid AS patient_id,
                pe.enrollment_status,
                pe.current_step,
                pe.progress_percentage,
                pe.total_programs,
                pe.completed_programs,
                pe.start_date,
                pe.completion_date,
                pe.created_at,
                pe.updated_at,
                pt.fname,
                pt.lname,
                pt.DOB,
                GROUP_CONCAT(
                    CONCAT(
                        ep.program_option_id, '^',
                        ep.program_name, '^',
                        ep.program_status
                    ) SEPARATOR '~'
                ) AS enrolled_programs
            FROM patient_enrollment pe
            LEFT JOIN patient_data pt ON pe.pid = pt.pid
            LEFT JOIN enrollment_programs ep ON pe.id = ep.enrollment_id
            WHERE pe.pid IN ({pid_placeholders})
        """

        if program_filter:
            enrollment_sql += " AND ep.program_option_id = :program_filter"
            pid_params["program_filter"] = program_filter

        enrollment_sql += " GROUP BY pe.id ORDER BY pe.updated_at DESC"

        result = await db.execute(text(enrollment_sql), pid_params)
        records = result.mappings().all()

        all_program_ids = set()
        enrollment_by_patient = {}

        for record in records:
            pid = record["patient_id"]
            enrollment_by_patient[pid] = record

            if record["enrolled_programs"]:
                for prog_str in record["enrolled_programs"].split("~"):
                    parts = prog_str.split("^")
                    if len(parts) >= 3:
                        all_program_ids.add(parts[0])

        # 🚀 BATCH QUERY 2
        program_options_map = {}
        if all_program_ids:
            prog_placeholders = ','.join([f":prog{i}" for i in range(len(all_program_ids))])
            prog_params = {f"prog{i}": pid for i, pid in enumerate(all_program_ids)}

            program_sql = f"""
                SELECT
                    option_id,
                    title AS program_name,
                    codes,
                    activity,
                    seq
                FROM list_options
                WHERE list_id = 'enrollment_programs'
                AND option_id IN ({prog_placeholders})
                ORDER BY seq
            """

            prog_result = await db.execute(text(program_sql), prog_params)
            program_options = prog_result.mappings().all()

            for prog in program_options:
                program_options_map[prog["option_id"]] = prog

        # Final assembly
        for pid in patient_ids:
            if pid in enrollment_by_patient:
                record = enrollment_by_patient[pid]
                enrolled_programs = []
                if record["enrolled_programs"]:
                    for prog_str in record["enrolled_programs"].split("~"):
                        parts = prog_str.split("^")
                        if len(parts) >= 3:
                            enrolled_programs.append({
                                "program_option_id": parts[0],
                                "program_name": parts[1],
                                "program_status": parts[2]
                            })

                program_details = []
                for prog in enrolled_programs:
                    detail = program_options_map.get(prog["program_option_id"])
                    if detail:
                        program_details.append({
                            "program_id": prog["program_option_id"],
                            "program_name": detail["program_name"],
                            "program_code": detail["codes"] or prog["program_option_id"].upper(),
                            "status": prog["program_status"],
                            "is_active": detail["activity"] == 1 if detail["activity"] is not None else False,
                            "sequence": detail["seq"]
                        })

                total_programs = record["total_programs"] or len(program_details)
                completed_programs = record["completed_programs"] or len([
                    p for p in enrolled_programs if p["program_status"] == "completed"
                ])

                enrollment_data[pid] = {
                    "patient_id": pid,
                    "enrollment_info": {
                        "enrollment_id": record["enrollment_id"],
                        "patient_id": str(record["patient_id"]),
                        "status": record["enrollment_status"],
                        "current_step": record["current_step"] or "Programs",
                        "progress_percentage": float(record["progress_percentage"] or 0),
                        "start_date": record["start_date"].isoformat() if record["start_date"] else None,
                        "end_date": record["completion_date"].isoformat() if record["completion_date"] else None,
                        "last_updated": record["updated_at"].isoformat() if record["updated_at"] else None,
                        "total_programs": total_programs,
                        "completed_programs": completed_programs,
                        "fname": record["fname"],
                        "lname": record["lname"],
                        "DOB": record["DOB"].isoformat() if record["DOB"] else None
                    },
                    "programs": program_details,
                    "progress_summary": {
                        "total_programs": total_programs,
                        "completed_programs": completed_programs,
                        "progress_percentage": float(record["progress_percentage"] or 0),
                        "calculated_percentage": round((completed_programs / total_programs * 100), 2) if total_programs > 0 else 0
                    }
                }
            else:
                enrollment_data[pid] = {
                    "patient_id": pid,
                    "enrollment_info": None,
                    "programs": [],
                    "progress_summary": {
                        "total_programs": 0,
                        "completed_programs": 0,
                        "progress_percentage": 0,
                        "calculated_percentage": 0
                    }
                }

        logger.info(f"✅ BATCH: Retrieved enrollment data for {len(enrollment_data)} patients")
        return enrollment_data

    except Exception as e:
        logger.error(f"❌ Error in get_batch_enrollment_status: {str(e)}", exc_info=True)
        return {pid: {} for pid in patient_ids}

async def get_batch_vitals_data(db: AsyncSession, patient_ids: List[int]) -> Dict[int, Dict]:
    """Fetch all vitals data for multiple patients in optimized batch queries"""
    vitals_data: Dict[int, Dict] = {}

    if not patient_ids:
        return vitals_data

    # Initialize dict structure
    for pid in patient_ids:
        vitals_data[pid] = {
            "latest": {},
            "averages": {},
            "form_vitals": {}
        }

    # ------------------ Latest Vitals ------------------
    latest_vitals_query = text("""
        WITH latest_glucose AS (
            SELECT pid, blood_glucose, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN blood_glucose IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_weight AS (
            SELECT pid, weight_kg, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN weight_kg IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_height AS (
            SELECT pid, height_cm, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN height_cm IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_pulse AS (
            SELECT pid, pulse, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN pulse IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_bp AS (
            SELECT pid, systolic, diastolic, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN systolic IS NOT NULL OR diastolic IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_ketone AS (
            SELECT pid, ketone_mg_per_dL, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN ketone_mg_per_dL IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_bmr AS (
            SELECT pid, bmr, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN bmr IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        ),
        latest_spo2 AS (
            SELECT pid, spo2, reading_time,
                   ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
                        CASE WHEN spo2 IS NOT NULL THEN 0 ELSE 1 END,
                        reading_time DESC) AS rn
            FROM api_vitals_data
            WHERE pid IN :pids
        )
        SELECT
            g.pid,
            g.blood_glucose, g.reading_time AS glucose_time,
            w.weight_kg, w.reading_time AS weight_time,
            h.height_cm, h.reading_time AS height_time,
            p.pulse, p.reading_time AS pulse_time,
            bp.systolic, bp.diastolic, bp.reading_time AS bp_time,
            k.ketone_mg_per_dL, k.reading_time AS ketone_time,
            b.bmr, b.reading_time AS bmr_time,
            s.spo2, s.reading_time AS spo2_time
        FROM latest_glucose g
        LEFT JOIN latest_weight w ON g.pid = w.pid
        LEFT JOIN latest_height h ON g.pid = h.pid
        LEFT JOIN latest_pulse p ON g.pid = p.pid
        LEFT JOIN latest_bp bp ON g.pid = bp.pid
        LEFT JOIN latest_ketone k ON g.pid = k.pid
        LEFT JOIN latest_bmr b ON g.pid = b.pid
        LEFT JOIN latest_spo2 s ON g.pid = s.pid
        WHERE g.rn = 1 AND w.rn = 1 AND h.rn = 1 AND p.rn = 1
          AND bp.rn = 1 AND k.rn = 1 AND b.rn = 1 AND s.rn = 1
    """).bindparams(bindparam("pids", expanding=True))

    result = await db.execute(latest_vitals_query, {"pids": patient_ids})
    for row in result.mappings():
        pid = row["pid"]
        vitals_data[pid]["latest"] = {
            "blood_glucose": float(row["blood_glucose"]) if row["blood_glucose"] is not None else None,
            "blood_glucose_time": row["glucose_time"],
            "ketone": float(row["ketone_mg_per_dL"]) if row["ketone_mg_per_dL"] is not None else None,
            "ketone_time": row["ketone_time"],
            "systolic": float(row["systolic"]) if row["systolic"] is not None else None,
            "diastolic": float(row["diastolic"]) if row["diastolic"] is not None else None,
            "bp_time": row["bp_time"],
            "height_cm": float(row["height_cm"]) if row["height_cm"] is not None else None,
            "height_time": row["height_time"],
            "weight_kg": float(row["weight_kg"]) if row["weight_kg"] is not None else None,
            "weight_time": row["weight_time"],
            "pulse": float(row["pulse"]) if row["pulse"] is not None else None,
            "pulse_time": row["pulse_time"],
            "bmr": float(row["bmr"]) if row["bmr"] is not None else None,
            "bmr_time": row["bmr_time"],
            "spo2": float(row["spo2"]) if row["spo2"] is not None else None,
            "spo2_time": row["spo2_time"],
        }

    # ------------------ Averages ------------------
    averages_query = text("""
        SELECT
            pid,
            AVG(blood_glucose) as avg_glucose,
            AVG(ketone_mg_per_dL) as avg_ketone,
            AVG(systolic) as avg_systolic,
            AVG(diastolic) as avg_diastolic,
            AVG(height_cm) as avg_height,
            AVG(weight_kg) as avg_weight,
            AVG(pulse) as avg_pulse,
            AVG(bmr) as avg_bmr,
            AVG(spo2) as avg_spo2
        FROM api_vitals_data
        WHERE pid IN :pids
          AND reading_time >= DATE_SUB(NOW(), INTERVAL 5 DAY)
        GROUP BY pid
    """).bindparams(bindparam("pids", expanding=True))

    result = await db.execute(averages_query, {"pids": patient_ids})
    for row in result.mappings():
        pid = row["pid"]
        vitals_data[pid]["averages"] = {
            "avg_glucose": round(row["avg_glucose"], 1) if row["avg_glucose"] else None,
            "avg_ketone": round(row["avg_ketone"], 1) if row["avg_ketone"] else None,
            "avg_systolic": round(row["avg_systolic"], 1) if row["avg_systolic"] else None,
            "avg_diastolic": round(row["avg_diastolic"], 1) if row["avg_diastolic"] else None,
            "avg_height": round(row["avg_height"], 1) if row["avg_height"] else None,
            "avg_weight": round(row["avg_weight"], 1) if row["avg_weight"] else None,
            "avg_pulse": round(row["avg_pulse"], 1) if row["avg_pulse"] else None,
            "avg_bmr": round(row["avg_bmr"], 1) if row["avg_bmr"] else None,
            "avg_spo2": round(row["avg_spo2"], 1) if row["avg_spo2"] else None,
        }

    # ------------------ Form Vitals ------------------
    form_vitals_query = text("""
        SELECT
            id, pid, date, height, weight, BMI, bps,
            ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
        FROM form_vitals
        WHERE pid IN :pids
    """).bindparams(bindparam("pids", expanding=True))

    result = await db.execute(form_vitals_query, {"pids": patient_ids})
    for row in result.mappings():
        pid = row["pid"]
        if row["rn"] == 1:
            vitals_data[pid]["form_vitals"] = {
                "id": row["id"],
                "date": row["date"],
                "height": row["height"],
                "weight": row["weight"],
                "BMI": row["BMI"],
                "bps": row["bps"],
            }

    return vitals_data

async def get_batch_patient_data(db: AsyncSession, patient_ids: List[int]) -> Dict[int, Dict]:
    patient_data: Dict[int, Dict] = {}

    if not patient_ids:
        return patient_data

    # Initialize structure
    for pid in patient_ids:
        patient_data[pid] = {
            "history": {},
            "encounter": {},
            "scores": None,
        }

    # Convert ids for query
    ids_str = ",".join(str(pid) for pid in patient_ids)

    # 🚀 History query
    history_query = text(f"""
        SELECT pid, tobacco, usertext11,
               ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) AS rn
        FROM history_data
        WHERE pid IN ({ids_str})
    """)
    history_results = (await db.execute(history_query)).mappings().all()

    # 🚀 Encounter query
    encounter_query = text(f"""
        SELECT pid, encounter, date, date_end, encounter_status,
               ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) AS rn
        FROM form_encounter
        WHERE pid IN ({ids_str})
    """)
    encounter_results = (await db.execute(encounter_query)).mappings().all()

    # 🚀 Scores query
    scores_query = text(f"""
        SELECT pid, lambda_response, status,
               ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) AS rn
        FROM report_analyzer
        WHERE pid IN ({ids_str}) AND status = 200
    """)
    scores_results = (await db.execute(scores_query)).mappings().all()

    # 🧠 Process history
    for row in history_results:
        if row["rn"] == 1:
            pid = row["pid"]
            patient_data[pid]["history"] = {
                "tobacco": row.get("tobacco"),
                "usertext11": row.get("usertext11"),
            }

    # 🧠 Process encounter
    for row in encounter_results:
        if row["rn"] == 1:
            pid = row["pid"]
            patient_data[pid]["encounter"] = {
                "encounter": row.get("encounter"),
                "date": row.get("date"),
                "date_end": row.get("date_end"),
                "encounter_status": row.get("encounter_status"),
            }

    # 🧠 Process scores
    for row in scores_results:
        if row["rn"] == 1:
            pid = row["pid"]
            try:
                raw = row.get("lambda_response", "").strip()
                decoded = json.loads(raw)
                body = decoded.get("body", {})
                filtered_body = {k: v for k, v in body.items() if v is not None}
                patient_data[pid]["scores"] = {
                    "statusCode": decoded.get("statusCode"),
                    "body": filtered_body,
                }
            except (json.JSONDecodeError, AttributeError, TypeError):
                patient_data[pid]["scores"] = None

    return patient_data 
    
# ------------------- Core Calculation -------------------

async def calculate_heart_age_optimized(patient_row: Dict[str, Any], history_data: Dict[str, Any], vitals_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        gender = patient_row.get('sex')

        # Smoking status
        smoking = 0
        tobacco_info = history_data.get('tobacco', '')
        if tobacco_info and 'current' in tobacco_info.lower():
            smoking = 1

        # Blood pressure
        bp = 0.0
        latest_vitals = vitals_data.get('latest', {})
        if latest_vitals.get('systolic'):
            bp = float(latest_vitals['systolic'])
        elif vitals_data.get('form_vitals', {}).get('bps'):
            bp = float(vitals_data['form_vitals']['bps'])

        # Height and weight
        height_cm = latest_vitals.get('height_cm') or vitals_data.get('form_vitals', {}).get('height') or 0
        weight_kg = latest_vitals.get('weight_kg') or vitals_data.get('form_vitals', {}).get('weight') or 0

        height_m = float(height_cm) / 100 if height_cm else 0.0
        weight_kg = float(weight_kg) if weight_kg else 0.0

        # BMI
        bmi = vitals_data.get('form_vitals', {}).get('BMI')
        if not bmi and weight_kg > 0 and height_m > 0:
            bmi = weight_kg / (height_m * height_m)
        bmi = float(bmi) if bmi else 0.0

        # Hypertension and diabetes
        hypertension = 0
        diabetes = 0
        usertext11 = history_data.get('usertext11', '')
        if usertext11:
            ht_values = usertext11.split('|')
            if 'ht' in ht_values:
                hypertension = 1
            if 'db' in ht_values:
                diabetes = 1

        # Age
        dob = patient_row.get('DOB')
        age = 0
        if dob:
            if isinstance(dob, str):
                try:
                    dob = datetime.strptime(dob, '%Y-%m-%d')
                except ValueError:
                    try:
                        dob = datetime.strptime(dob, '%d %B %Y')
                    except ValueError:
                        logger.warning(f"Unrecognized DOB format: {dob}")
                        dob = None
            if isinstance(dob, (date, datetime)):
                age = await calculate_age(dob)

        request_data = {
            "gender": 1 if gender == 'Male' else 0,
            "age": age,
            "bp": bp,
            "hypertension": hypertension,
            "smoking": smoking,
            "diabetes": diabetes,
            "bmi": bmi
        }

        result = await heart_age(request_data)
        return result

    except Exception as e:
        logger.error(f"Error calculating heart age: {str(e)}")
        return {}

# ------------------- Helper Functions -------------------

async def calculate_age(dob: date) -> int:
    today = datetime.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

async def cminc(cm: float) -> float:
    try:
        inches = float(cm) / 2.54
        return round(inches % 12, 2)
    except (TypeError, ValueError):
        return None

async def get_time(dt: Any) -> str:
    if not dt:
        return ''
    if isinstance(dt, datetime):
        return dt.strftime('%H:%M:%S')
    return str(dt)

# ------------------- Patient Model -------------------

class Patient:
    def __init__(self, gender, age, bp, hypertension, smoking, diabetes, bmi=None, height=None, weight=None):
        self.gender = gender
        self.age = age
        self.bp = bp
        self.hypertension = hypertension
        self.smoking = smoking
        self.diabetes = diabetes
        if height is not None and isinstance(height, (int, float)) and weight is not None and isinstance(weight, (int, float)):
            calculated_bmi = (weight / math.pow(height, 2)) * 703
            self.bmi = float("{:.2f}".format(calculated_bmi))
        else:
            self.bmi = bmi

# ------------------- Risk Models -------------------

async def male(patient: Patient) -> float:
    D30 = 55.69199925
    D31 = math.pow(-math.log(0.88431), (1 / 3.11296))
    D32 = D30 * (1 / round(D31, 9))
    D33 = 1 / 3.11296

    coeff_bp = 1.85508 if patient.hypertension == 0 else 1.92672

    beta = (round(math.log(patient.age), 9) * 3.11296 +
            round(math.log(patient.bp), 9) * coeff_bp +
            patient.smoking * 0.70953 +
            round(math.log(patient.bmi), 9) * 0.79277 +
            patient.diabetes * 0.5316)

    risk_score = 1 - math.pow(0.88431, round(math.exp(round(beta, 8) - 23.9388), 9))
    D34 = math.pow(-math.log(1 - round(risk_score, 9)), round(D33, 9))
    D35 = D32 * round(D34, 8)
    return D35

async def female(patient: Patient) -> float:
    G32 = 158.1101697
    F33 = 0.36750249
    coeff_bp = 2.81291 if patient.hypertension == 0 else 2.88267

    beta = (math.log(patient.age) * 2.72107 +
            math.log(patient.bp) * coeff_bp +
            patient.smoking * 0.61868 +
            math.log(patient.bmi) * 0.51125 +
            patient.diabetes * 0.77763)

    G34 = math.pow(-math.log(1 - (1 - math.pow(0.94833, math.exp(beta - 26.0145)))), F33)
    G35 = G32 * G34
    return G35

# ------------------- Heart Age Wrapper -------------------

async def heart_age(event: Dict[str, Any]) -> Dict[str, Any]:
    result = "NA"
    statusCode = 200
    patient = None
    try:
        patient = Patient(**event)
    except Exception as e:
        statusCode = 400
        logger.info(str(event))
        logger.error(e)

    if patient is not None:
        try:
            logger.info(str(patient.__dict__))
            result = await male(patient) if patient.gender == 1 else await female(patient)
        except Exception as e:
            statusCode = 400
            logger.error(e)

    return {
        'statusCode': statusCode,
        'body': round(result) if isinstance(result, numbers.Number) else result
    }
