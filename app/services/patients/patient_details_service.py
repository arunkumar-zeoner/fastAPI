from typing import List, Dict, Any, Optional
import logging
import json
import math
from datetime import datetime, date
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy import text
from app.models import PatientEnrollment, PatientData, EnrollmentPrograms, ListOptions
from app.utils.logger_utils import logger

# Utility functions
def cminc(cm):
	"""Convert centimeters to inches"""
	try:
		cm = float(cm)
		inches = cm / 2.54
		return round(inches % 12, 2)
	except (TypeError, ValueError):
		return None

def get_time(dt):
    """Format datetime as ISO 8601 string"""
    if not dt:
        return ''
    if isinstance(dt, datetime):
        return dt.isoformat(timespec='seconds')
    return str(dt)

def format_dob_human(dob_value):
	"""Format DOB as 'D Month YYYY' cross-platform (no leading zero day)."""
	if not dob_value:
		return ''
	try:
		if isinstance(dob_value, (datetime, date)):
			s = dob_value.strftime('%d %B %Y')
		else:
			dob = datetime.strptime(str(dob_value), '%Y-%m-%d')
			s = dob.strftime('%d %B %Y')
		return s.lstrip('0')
	except Exception:
		return ''

def format_date_iso(d):
	"""Format date/datetime into 'YYYY-%m-%d' string for JSON."""
	if not d:
		return ''
	if isinstance(d, (datetime, date)):
		return d.strftime('%Y-%m-%d')
	return str(d)

def calculate_age(dob):
	"""Calculate age from date of birth"""
	if isinstance(dob, str):
		try:
			dob = datetime.strptime(dob, "%Y-%m-%d")
		except ValueError:
			try:
				dob = datetime.strptime(dob, "%d %B %Y")
			except ValueError:
				logger.warning(f"Unrecognized DOB format: {dob}")
				return 0
	
	if isinstance(dob, (date, datetime)):
		today = datetime.today()
		age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
		return age
	return 0

async def get_remaining_days(db, pid: int) -> tuple[int, int, int]:
	"""Calculate remaining days, duration, and need count for a patient"""
	try:
		# Get encounter data
		stmt = text("""
			SELECT * FROM form_encounter 
			WHERE date_end IS NOT NULL AND encounter_status='open' AND pid=:pid
		""")
		result = await db.execute(stmt, {"pid": pid})
		enc_data = result.fetchone()

		if not enc_data:
			return 0, 0, 0

		end_date = enc_data.date_end
		today = datetime.now()
		today_date = today.date()

		if isinstance(end_date, str):
			try:
				end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
			except ValueError:
				end_date = datetime.strptime(end_date, '%Y-%m-%d')

		delta = end_date - today
		left_days = max(math.ceil(delta.total_seconds() / 86400), 0)
		days_remaining = max(left_days, 0)

		# Check if there's a reading for today
		stmt = text("""
			SELECT * FROM api_vitals_data 
			WHERE pid = :pid AND api_type != 'googlefit' AND reading_date = :today_date 
			LIMIT 1
		""")
		result = await db.execute(stmt, {"pid": pid, "today_date": today_date})
		reading_exists_today = result.fetchone() is not None

		if reading_exists_today:
			days_remaining = max(days_remaining - 1, 0)

		# Calculate reading count
		start_date_str = enc_data.date
		end_date_str = enc_data.date_end
		stmt = text("""
			SELECT COUNT(DISTINCT reading_date) AS reading_count 
			FROM api_vitals_data 
			WHERE pid = :pid AND api_type != 'googlefit' 
			AND reading_date BETWEEN :start_date AND :end_date
		""")
		result = await db.execute(stmt, {"pid": pid, "start_date": start_date_str, "end_date": end_date_str})
		reading_count = min(result.fetchone().reading_count or 0, 16)
		need_count = 16 - reading_count

		# Calculate duration
		encounter_id = enc_data.encounter
		stmt = text("""
			SELECT SUM(timespent) AS duration 
			FROM rpm_encounter 
			WHERE pid = :pid AND eid = :encounter_id AND is_deleted = 0
		""")
		result = await db.execute(stmt, {"pid": pid, "encounter_id": encounter_id})
		duration = result.fetchone().duration or 0

		return days_remaining, duration, need_count

	except Exception as e:
		logger.error(f"Error calculating remaining days: {str(e)}")
		return 0, 0, 0

async def get_batch_vitals_data(db, patient_ids: List[int]) -> Dict[int, Dict]:
	"""Fetch all vitals data for multiple patients in optimized batch queries"""
	vitals_data = {}

	if not patient_ids:
		return vitals_data

	# Initialize data structure
	for pid in patient_ids:
		vitals_data[pid] = {
			'latest': {},
			'averages': {},
			'form_vitals': {}
		}

	pids_str = ','.join([':pid' + str(i) for i in range(len(patient_ids))])
	params = {f'pid{i}': pid for i, pid in enumerate(patient_ids)}

	try:
		# Latest API vitals for all patients
		latest_vitals_query = f"""
			WITH latest_glucose AS (
				SELECT pid, blood_glucose, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN blood_glucose IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_weight AS (
				SELECT pid, weight_kg, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN weight_kg IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_height AS (
				SELECT pid, height_cm, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN height_cm IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_pulse AS (
				SELECT pid, pulse, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN pulse IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_bp AS (
				SELECT pid, systolic, diastolic, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN systolic IS NOT NULL OR diastolic IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_ketone AS (
				SELECT pid, ketone_mg_per_dL, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN ketone_mg_per_dL IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_bmr AS (
				SELECT pid, bmr, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN bmr IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			),
			latest_spo2 AS (
				SELECT pid, spo2, reading_time,
					ROW_NUMBER() OVER (PARTITION BY pid ORDER BY 
						CASE WHEN spo2 IS NOT NULL THEN 0 ELSE 1 END,
						reading_time DESC) AS rn
				FROM api_vitals_data
				WHERE pid IN ({pids_str})
			)
			SELECT
				g.pid,
				g.blood_glucose,
				g.reading_time AS glucose_time,
				w.weight_kg,
				w.reading_time AS weight_time,
				h.height_cm,
				h.reading_time AS height_time,
				p.pulse,
				p.reading_time AS pulse_time,
				bp.systolic,
				bp.diastolic,
				bp.reading_time AS bp_time,
				k.ketone_mg_per_dL,
				k.reading_time AS ketone_time,
				b.bmr,
				b.reading_time AS bmr_time,
				s.spo2,
				s.reading_time AS spo2_time,
				g.reading_time
			FROM latest_glucose g
			LEFT JOIN latest_weight w ON g.pid = w.pid
			LEFT JOIN latest_height h ON g.pid = h.pid
			LEFT JOIN latest_pulse p ON g.pid = p.pid
			LEFT JOIN latest_bp bp ON g.pid = bp.pid
			LEFT JOIN latest_ketone k ON g.pid = k.pid
			LEFT JOIN latest_bmr b ON g.pid = b.pid
			LEFT JOIN latest_spo2 s ON g.pid = s.pid
			WHERE g.rn = 1 AND w.rn = 1 AND h.rn = 1 AND bp.rn = 1 AND k.rn = 1 AND b.rn = 1 AND s.rn = 1
		"""

		result = await db.execute(text(latest_vitals_query), params)
		latest_results = result.fetchall()

		# Process latest vitals
		for row in latest_results:
			pid = row.pid
			vitals_data[pid]['latest'] = {
				'blood_glucose': row.blood_glucose,
				'blood_glucose_time': row.glucose_time,
				'ketone': row.ketone_mg_per_dL,
				'ketone_time': row.ketone_time,
				'systolic': row.systolic,
				'diastolic': row.diastolic,
				'bp_time': row.bp_time,
				'height_cm': row.height_cm,
				'height_time': row.height_time,
				'weight_kg': row.weight_kg,
				'weight_time': row.weight_time,
				'pulse': row.pulse,
				'pulse_time': row.pulse_time,
				'bmr': row.bmr,
				'bmr_time': row.bmr_time,
				'spo2': row.spo2,
				'spo2_time': row.spo2_time,
			}

		# 5-day averages for all patients
		averages_query = f"""
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
			WHERE pid IN ({pids_str})
			AND reading_time >= DATE_SUB(NOW(), INTERVAL 5 DAY)
			GROUP BY pid
		"""
		result = await db.execute(text(averages_query), params)
		avg_results = result.fetchall()

		for row in avg_results:
			pid = row.pid
			vitals_data[pid]['averages'] = {
				'avg_glucose': round(row.avg_glucose, 1) if row.avg_glucose else '',
				'avg_ketone': round(row.avg_ketone, 1) if row.avg_ketone else '',
				'avg_systolic': round(row.avg_systolic, 1) if row.avg_systolic else '',
				'avg_diastolic': round(row.avg_diastolic, 1) if row.avg_diastolic else '',
				'avg_height': round(row.avg_height, 1) if row.avg_height else '',
				'avg_weight': round(row.avg_weight, 1) if row.avg_weight else '',
				'avg_pulse': round(row.avg_pulse, 1) if row.avg_pulse else '',
				'avg_bmr': round(row.avg_bmr, 1) if row.avg_bmr else '',
				'avg_spo2': round(row.avg_spo2, 1) if row.avg_spo2 else ''
			}

		# Form vitals for all patients
		form_vitals_query = f"""
			SELECT
				id, pid, date, height, weight, BMI, bps,
				ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
			FROM form_vitals
			WHERE pid IN ({pids_str})
		"""
		result = await db.execute(text(form_vitals_query), params)
		form_results = result.fetchall()

		for row in form_results:
			if row.rn == 1:  # Most recent record
				pid = row.pid
				vitals_data[pid]['form_vitals'] = {
					'id': row.id,
					'date': row.date,
					'height': row.height,
					'weight': row.weight,
					'BMI': row.BMI,
					'bps': row.bps
				}

	except Exception as e:
		logger.error(f"Error fetching vitals data: {str(e)}")

	return vitals_data

async def get_batch_patient_data(db, patient_ids: List[int]) -> Dict[int, Dict]:
	"""Fetch additional patient data in batch queries"""
	patient_data = {}

	if not patient_ids:
		return patient_data

	pids_str = ','.join([':pid' + str(i) for i in range(len(patient_ids))])
	params = {f'pid{i}': pid for i, pid in enumerate(patient_ids)}

	try:
		# History data for all patients
		history_query = f"""
			SELECT
				pid, tobacco, usertext11,
				ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
			FROM history_data
			WHERE pid IN ({pids_str})
		"""
		result = await db.execute(text(history_query), params)
		history_results = result.fetchall()

		# Encounter data for all patients
		encounter_query = f"""
			SELECT
				pid, encounter, date, date_end, encounter_status,
				ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
			FROM form_encounter
			WHERE pid IN ({pids_str})
		"""
		result = await db.execute(text(encounter_query), params)
		encounter_results = result.fetchall()

		# Report analyzer scores for all patients
		scores_query = f"""
			SELECT
				pid, lambda_response, status,
				ROW_NUMBER() OVER (PARTITION BY pid ORDER BY id DESC) as rn
			FROM report_analyzer
			WHERE pid IN ({pids_str})
			AND status = 200
		"""
		result = await db.execute(text(scores_query), params)
		scores_results = result.fetchall()

		# Process results
		for pid in patient_ids:
			patient_data[pid] = {
				'history': {},
				'encounter': {},
				'scores': "Score not found"
			}

		# Process history data
		for row in history_results:
			if row.rn == 1:
				pid = row.pid
				patient_data[pid]['history'] = {
					'tobacco': row.tobacco,
					'usertext11': row.usertext11
				}

		# Process encounter data
		for row in encounter_results:
			if row.rn == 1:
				pid = row.pid
				patient_data[pid]['encounter'] = {
					'encounter': row.encounter,
					'date': row.date,
					'date_end': row.date_end,
					'encounter_status': row.encounter_status
				}

		# Process scores data
		for row in scores_results:
			if row.rn == 1:
				pid = row.pid
				try:
					lambda_response = row.lambda_response.strip()
					decoded_response = json.loads(lambda_response)
					filtered_body = {k: v for k, v in decoded_response.get('body', {}).items() if v is not None}
					patient_data[pid]['scores'] = {
						'statusCode': decoded_response.get('statusCode'),
						'body': filtered_body
					}
				except (json.JSONDecodeError, AttributeError):
					patient_data[pid]['scores'] = "Score not found"

	except Exception as e:
		logger.error(f"Error fetching additional patient data: {str(e)}")

	return patient_data

async def get_batch_enrollment_data(
	db_conn, event, context, patient_ids: List[int]
) -> Dict[int, Dict]:
	"""Fetch enrollment data for multiple patients in batch"""
	if not patient_ids:
		return {}

	try:
		logger.info(f"Fetching enrollment for {len(patient_ids)} patients in batch")
		enrollment_data = await get_batch_enrollment_status(db_conn, event, context, patient_ids)

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
	db, event: dict, context: dict, patient_ids: List[int]
) -> Dict[int, Dict]:
	"""Get enrollment status for multiple patients in batch"""
	if not patient_ids:
		return {}

	query_params = event.get("queryStringParameters") or {}
	body_params = event.get("body", {})
	if isinstance(body_params, str):
		try:
			body_params = json.loads(body_params)
		except json.JSONDecodeError:
			body_params = {}

	program_filter = body_params.get("program_id") or query_params.get("program_id")

	try:
		stmt = (
			select(PatientEnrollment)
			.where(PatientEnrollment.pid.in_(patient_ids))
		)

		if program_filter:
			stmt = (
				stmt.join(
					EnrollmentPrograms,
					EnrollmentPrograms.enrollment_id == PatientEnrollment.id
				)
				.where(EnrollmentPrograms.program_option_id == program_filter)
			)

		result = await db.execute(stmt)
		raw_enrollments = result.scalars().all()

		# Deduplicate if the join introduced duplicates
		enrollment_by_id = {e.id: e for e in raw_enrollments}
		enrollments = list(enrollment_by_id.values())

		if not enrollments:
			return {}

		# Collect enrollment_ids and pids
		enrollment_ids = [e.id for e in enrollments]
		pids = {e.pid for e in enrollments}

		# Fetch programs for these enrollments
		prog_stmt = select(EnrollmentPrograms).where(
			EnrollmentPrograms.enrollment_id.in_(enrollment_ids)
		)
		prog_result = await db.execute(prog_stmt)
		all_program_rows = prog_result.scalars().all()

		# Group programs by enrollment_id
		from collections import defaultdict
		programs_by_enroll = defaultdict(list)
		for p in all_program_rows:
			programs_by_enroll[p.enrollment_id].append(p)

		# Fetch program metadata (ListOptions) for all program ids
		all_program_ids = {p.program_option_id for p in all_program_rows if p.program_option_id}
		program_options = {}
		if all_program_ids:
			program_stmt = (
				select(ListOptions)
				.where(
					ListOptions.list_id == "enrollment_programs",
					ListOptions.option_id.in_(all_program_ids)
				)
				.order_by(ListOptions.seq)
			)
			program_result = await db.execute(program_stmt)
			program_options = {opt.option_id: opt for opt in program_result.scalars().all()}

		# Fetch patient details for pids
		patient_map = {}
		if pids:
			patient_stmt = select(PatientData).where(PatientData.pid.in_(pids))
			patient_result = await db.execute(patient_stmt)
			patient_map = {p.pid: p for p in patient_result.scalars().all()}

		# Build response
		enrollment_data = {}
		for enrollment in enrollments:
			pid = enrollment.pid
			patient = patient_map.get(pid)

			enrolled_programs = programs_by_enroll.get(enrollment.id, [])
			program_details = []
			for p in enrolled_programs:
				meta = program_options.get(p.program_option_id)
				if meta:
					program_details.append({
						"program_id": p.program_option_id,
						"program_name": meta.title,
						"program_code": meta.codes or (p.program_option_id.upper() if p.program_option_id else None),
						"status": p.program_status,
						"is_active": meta.activity == 1 if meta.activity is not None else False,
						"sequence": meta.seq,
					})

			completed_programs = sum(
				1 for p in enrolled_programs if getattr(p, "program_status", None) == "completed"
			)
			total_programs = enrollment.total_programs or len(program_details)

			enrollment_data[pid] = {
				"patient_id": pid,
				"enrollment_info": {
					"enrollment_id": enrollment.id,
					"status": enrollment.enrollment_status,
					"current_step": enrollment.current_step or "Programs",
					"progress_percentage": float(enrollment.progress_percentage or 0),
					"start_date": enrollment.start_date.isoformat() if enrollment.start_date else None,
					"end_date": enrollment.completion_date.isoformat() if enrollment.completion_date else None,
					"last_updated": enrollment.updated_at.isoformat() if enrollment.updated_at else None,
					"total_programs": total_programs,
					"completed_programs": completed_programs,
					"fname": getattr(patient, "fname", None),
					"lname": getattr(patient, "lname", None),
					"DOB": patient.DOB.isoformat() if getattr(patient, "DOB", None) else None,
				},
				"programs": program_details,
				"progress_summary": {
					"total_programs": total_programs,
					"completed_programs": completed_programs,
					"progress_percentage": float(enrollment.progress_percentage or 0),
					"calculated_percentage": round((completed_programs / total_programs * 100), 2) if total_programs > 0 else 0,
				},
			}

		return enrollment_data

	except Exception as e:
		logger.error(f"Error in get_batch_enrollment_status: {str(e)}", exc_info=True)
		return {pid: {} for pid in patient_ids}

async def get_patients_data_optimized(db, event, context, page=1, page_size=10):
	"""Optimized function that eliminates N+1 queries and processes data in batches"""
	offset = (page - 1) * page_size

	try:
		# Get total count
		result = await db.execute(text("SELECT COUNT(*) as total FROM patient_data"))
		total_rows = result.fetchone().total

		# Get paginated patients
		result = await db.execute(text("""
			SELECT pid, id, fname, lname, mname, DOB, sex, phone_cell,
				   street, city, state, postal_code, email
			FROM patient_data
			ORDER BY pid
			LIMIT :limit OFFSET :offset
		"""), {"limit": page_size, "offset": offset})
		patients = result.fetchall()

		if not patients:
			return {
				'patients': [],
				'pagination': {
					'page': page,
					'page_size': page_size,
					'total': total_rows,
					'total_pages': (total_rows + page_size - 1) // page_size
				}
			}

		patient_ids = [p.pid for p in patients]

		# Batch fetch all data
		logger.info(f"Fetching data for {len(patient_ids)} patients in batch...")

		enrollment_data = await get_batch_enrollment_data(db, event, context, patient_ids)
		vitals_data = await get_batch_vitals_data(db, patient_ids)
		additional_data = await get_batch_patient_data(db, patient_ids)

		# Process each patient with batch-fetched data
		results = []
		for patient_row in patients:
			pid = patient_row.pid
			patient_dict = {
				'pid': pid,
				'id': pid,
				'fname': patient_row.fname,
				'lname': patient_row.lname,
				'mname': patient_row.mname,
				'DOB': patient_row.DOB,
				'sex': patient_row.sex,
				'phone_cell': patient_row.phone_cell,
				'street': patient_row.street,
				'city': patient_row.city,
				'state': patient_row.state,
				'postal_code': patient_row.postal_code,
				'email': patient_row.email
			}

			# Get pre-fetched data
			patient_vitals = vitals_data.get(pid, {'latest': {}, 'averages': {}, 'form_vitals': {}})
			patient_additional = additional_data.get(pid, {'history': {}, 'encounter': {}, 'scores': {}})
			patient_enrollment = enrollment_data.get(pid, {})

			# Set enrollment data
			patient_dict['enrollment'] = patient_enrollment

			# Format DOB
			dob_value = patient_dict.get('DOB')
			patient_dict['DOB'] = format_dob_human(dob_value)

			# Process vitals data
			latest_vitals = patient_vitals['latest']
			averages = patient_vitals['averages']
			form_vitals = patient_vitals['form_vitals']

			# Height processing
			height_cm = latest_vitals.get('height_cm') or form_vitals.get('height')
			patient_dict['get_vitalsheight'] = height_cm
			height_inc = cminc(height_cm) if height_cm else None
			patient_dict['height'] = f"{height_inc}/{round(float(height_cm), 1)}" if height_inc and height_cm else ''
			patient_dict['height_data_time'] = get_time(latest_vitals.get('height_time')) if latest_vitals.get('height_time') else ''

			avg_height = averages.get('avg_height')
			avg_height_inc = cminc(avg_height) if avg_height else None
			patient_dict['avg_height'] = f"{avg_height_inc}/{round(float(avg_height), 1)}" if avg_height_inc and avg_height else ''

			# Weight processing
			weight_kg = latest_vitals.get('weight_kg') if latest_vitals.get('weight_kg') not in [None, 0, '', '0'] else form_vitals.get('weight')
			weight_kg_float = float(weight_kg) if weight_kg else 0.0

			if latest_vitals.get('weight_kg') not in [None, 0, '', '0']:
				weight_lb = round(weight_kg_float * 2.20462, 1) if weight_kg_float > 0 else ''
				weight_data_time = get_time(latest_vitals.get('weight_time')) if latest_vitals.get('weight_time') else ''
			else:
				weight_lb = weight_kg_float if weight_kg_float > 0 else ''
				_form_date = form_vitals.get('date')
				weight_data_time = format_date_iso(_form_date)

			patient_dict['weight'] = f"{weight_lb}" if weight_lb else ''
			patient_dict['weight_data_time'] = weight_data_time
			patient_dict['weight1'] = round(weight_kg_float, 1) if weight_kg_float > 0 else ''

			avg_weight = averages.get('avg_weight', 0)
			avg_weight_lb = round(float(avg_weight) * 2.20462, 1) if avg_weight else ''
			patient_dict['avg_weight'] = f"{avg_weight_lb}/{round(float(avg_weight), 1)}" if avg_weight_lb else ''

			# BMI calculation
			height_m = float(height_cm) / 100 if height_cm else 0.0
			bmi = round(weight_kg_float / (height_m * height_m), 1) if weight_kg_float > 0 and height_m > 0 else None
			patient_dict['bmi'] = bmi

			# Blood pressure
			systolic = latest_vitals.get('systolic')
			diastolic = latest_vitals.get('diastolic')
			patient_dict['blood_pressure'] = f"{systolic}/{diastolic}" if systolic and diastolic else ''
			patient_dict['blood_pressure_time'] = get_time(latest_vitals.get('bp_time')) if latest_vitals.get('bp_time') else ''

			avg_systolic = averages.get('avg_systolic')
			avg_diastolic = averages.get('avg_diastolic')
			patient_dict['avg_bp'] = f"{avg_systolic}/{avg_diastolic}" if avg_systolic and avg_diastolic else ''

			# Other vitals
			patient_dict['glucose_data'] = latest_vitals.get('blood_glucose', '')
			patient_dict['glucose_data_time'] = get_time(latest_vitals.get('blood_glucose_time')) if latest_vitals.get('blood_glucose_time') else ''
			patient_dict['avg_glucose'] = averages.get('avg_glucose', '')
			patient_dict['ketone_data'] = latest_vitals.get('ketone', '')
			patient_dict['ketone_data_time'] = get_time(latest_vitals.get('ketone_time')) if latest_vitals.get('ketone_time') else ''
			patient_dict['pulse'] = latest_vitals.get('pulse', '')
			patient_dict['pulse_data_time'] = get_time(latest_vitals.get('pulse_time')) if latest_vitals.get('pulse_time') else ''
			patient_dict['avg_pulse'] = averages.get('avg_pulse', '')
			patient_dict['bmr'] = latest_vitals.get('bmr', '')
			patient_dict['bmr_data_time'] = get_time(latest_vitals.get('bmr_time')) if latest_vitals.get('bmr_time') else ''
			patient_dict['avg_bmr'] = averages.get('avg_bmr', '')
			patient_dict['spo2'] = latest_vitals.get('spo2', '')
			patient_dict['spo2_data_time'] = get_time(latest_vitals.get('spo2_time')) if latest_vitals.get('spo2_time') else ''
			patient_dict['avg_spo2'] = averages.get('avg_spo2', '')

			# Health flags
			usertext11 = patient_additional['history'].get('usertext11', '')
			new_ht = 0
			diabetes = 0
			if usertext11:
				ht_value = usertext11.split("|")
				if "ht" in ht_value:
					new_ht = 1
				if 'db' in ht_value:
					diabetes = 1
			patient_dict['hypertension'] = new_ht
			patient_dict['diabetes'] = diabetes

			patient_dict['smoking'] = 0
			tobacco_info = patient_additional['history'].get('tobacco', '')
			if tobacco_info and 'current' in tobacco_info.lower():
				patient_dict['smoking'] = 1

			# Encounter processing
			encounter_data = patient_additional['encounter']
			patient_dict['encounter'] = encounter_data.get('encounter', '')
			patient_dict['encounterStatus'] = 0

			# Calculate days remaining and duration
			days_remaining, duration, need_count = await get_remaining_days(db, pid)
			patient_dict['days_remaining'] = days_remaining
			patient_dict['duration'] = duration
			patient_dict['need_count'] = need_count

			# Scores
			patient_dict['scores'] = patient_additional.get('scores', "Score not found")

			# Build vitals arrays
			reading_time = latest_vitals.get('reading_time')
			time_str = get_time(reading_time) if reading_time else ''

			# Initialize arrays
			patient_dict['pb'] = []
			patient_dict['pulse_list'] = []
			patient_dict['weight_list'] = []
			patient_dict['spo2_list'] = []
			patient_dict['glucose_list'] = []
			patient_dict['ketone_list'] = []

			# Add data to arrays if available
			if systolic and diastolic:
				patient_dict['pb'].append({
					'pb': f"{systolic}/{diastolic}",
					'time': time_str,
					'pbs': systolic
				})

			if latest_vitals.get('pulse'):
				patient_dict['pulse_list'].append({
					'pulse': latest_vitals['pulse'],
					'time': time_str
				})

			if weight_lb:
				patient_dict['weight_list'].append({
					'weight': weight_lb,
					'time': time_str
				})

			if latest_vitals.get('spo2'):
				patient_dict['spo2_list'].append({
					'spo2': latest_vitals['spo2'],
					'time': time_str
				})

			if latest_vitals.get('blood_glucose'):
				patient_dict['glucose_list'].append({
					'glucose': latest_vitals['blood_glucose'],
					'time': time_str
				})

			if latest_vitals.get('ketone'):
				patient_dict['ketone_list'].append({
					'ketone': latest_vitals['ketone'],
					'time': time_str
				})

			results.append(patient_dict)

		return {
			'patients': results,
			'pagination': {
				'page': page,
				'page_size': page_size,
				'total': total_rows,
				'total_pages': (total_rows + page_size - 1) // page_size
			}
		}

	except Exception as e:
		logger.error(f"Error in get_patients_data_optimized: {str(e)}")
		raise

async def get_single_patient_data_optimized(db, event, context, pid: int) -> Dict:
	"""Optimized function to fetch data for a single patient"""
	try:
		# Get single patient
		result = await db.execute(text("""
			SELECT pid, id, fname, lname, mname, DOB, sex, phone_cell,
				   street, city, state, postal_code, email
			FROM patient_data
			WHERE pid = :pid
		"""), {"pid": pid})
		patient = result.fetchone()

		if not patient:
			return None

		# Use the same batch functions but with single patient ID
		patient_ids = [pid]

		# Batch fetch all data
		logger.info(f"Fetching data for single patient {pid}...")

		enrollment_data = await get_batch_enrollment_data(db, event, context, patient_ids)
		vitals_data = await get_batch_vitals_data(db, patient_ids)
		additional_data = await get_batch_patient_data(db, patient_ids)

		# Process patient with batch-fetched data
		patient_dict = {
			'pid': pid,
			'id': pid,
			'fname': patient.fname,
			'lname': patient.lname,
			'mname': patient.mname,
			'DOB': patient.DOB,
			'sex': patient.sex,
			'phone_cell': patient.phone_cell,
			'street': patient.street,
			'city': patient.city,
			'state': patient.state,
			'postal_code': patient.postal_code,
			'email': patient.email
		}

		# Get pre-fetched data
		patient_vitals = vitals_data.get(pid, {'latest': {}, 'averages': {}, 'form_vitals': {}})
		patient_additional = additional_data.get(pid, {'history': {}, 'encounter': {}, 'scores': {}})
		patient_enrollment = enrollment_data.get(pid, {})

		# Set enrollment data
		patient_dict['enrollment'] = patient_enrollment

		# Format DOB
		dob_value = patient_dict.get('DOB')
		patient_dict['DOB'] = format_dob_human(dob_value)

		# Process vitals data (same logic as batch function)
		latest_vitals = patient_vitals['latest']
		averages = patient_vitals['averages']
		form_vitals = patient_vitals['form_vitals']

		# Height processing
		height_cm = latest_vitals.get('height_cm') or form_vitals.get('height')
		patient_dict['get_vitalsheight'] = height_cm
		height_inc = cminc(height_cm) if height_cm else None
		patient_dict['height'] = f"{height_inc}/{round(float(height_cm), 1)}" if height_inc and height_cm else ''
		patient_dict['height_data_time'] = get_time(latest_vitals.get('height_time')) if latest_vitals.get('height_time') else ''

		avg_height = averages.get('avg_height')
		avg_height_inc = cminc(avg_height) if avg_height else None
		patient_dict['avg_height'] = f"{avg_height_inc}/{round(float(avg_height), 1)}" if avg_height_inc and avg_height else ''

		# Weight processing
		weight_kg = latest_vitals.get('weight_kg') if latest_vitals.get('weight_kg') not in [None, 0, '', '0'] else form_vitals.get('weight')
		weight_kg_float = float(weight_kg) if weight_kg else 0.0

		if latest_vitals.get('weight_kg') not in [None, 0, '', '0']:
			weight_lb = round(weight_kg_float * 2.20462, 1) if weight_kg_float > 0 else ''
			weight_data_time = get_time(latest_vitals.get('weight_time')) if latest_vitals.get('weight_time') else ''
		else:
			weight_lb = weight_kg_float if weight_kg_float > 0 else ''
			_form_date = form_vitals.get('date')
			weight_data_time = format_date_iso(_form_date)

		patient_dict['weight'] = f"{weight_lb}" if weight_lb else ''
		patient_dict['weight_data_time'] = weight_data_time
		patient_dict['weight1'] = weight_kg_float if weight_kg_float > 0 else ''

		avg_weight = averages.get('avg_weight', 0)
		avg_weight_lb = round(float(avg_weight) * 2.20462, 1) if avg_weight else ''
		patient_dict['avg_weight'] = f"{avg_weight_lb}/{round(float(avg_weight))}" if avg_weight_lb else ''

		# BMI calculation
		height_m = float(height_cm) / 100 if height_cm else 0.0
		bmi = round(weight_kg_float / (height_m * height_m), 1) if weight_kg_float > 0 and height_m > 0 else None
		patient_dict['bmi'] = bmi

		# Blood pressure
		systolic = latest_vitals.get('systolic')
		diastolic = latest_vitals.get('diastolic')
		patient_dict['blood_pressure'] = f"{systolic}/{diastolic}" if systolic and diastolic else ''
		patient_dict['blood_pressure_time'] = get_time(latest_vitals.get('bp_time')) if latest_vitals.get('bp_time') else ''

		avg_systolic = averages.get('avg_systolic')
		avg_diastolic = averages.get('avg_diastolic')
		patient_dict['avg_bp'] = f"{avg_systolic}/{avg_diastolic}" if avg_systolic and avg_diastolic else ''

		# Other vitals
		patient_dict['glucose_data'] = latest_vitals.get('blood_glucose', '')
		patient_dict['glucose_data_time'] = get_time(latest_vitals.get('blood_glucose_time')) if latest_vitals.get('blood_glucose_time') else ''
		patient_dict['avg_glucose'] = averages.get('avg_glucose', '')
		patient_dict['ketone_data'] = latest_vitals.get('ketone', '')
		patient_dict['ketone_data_time'] = get_time(latest_vitals.get('ketone_time')) if latest_vitals.get('ketone_time') else ''
		patient_dict['pulse'] = latest_vitals.get('pulse', '')
		patient_dict['pulse_data_time'] = get_time(latest_vitals.get('pulse_time')) if latest_vitals.get('pulse_time') else ''
		patient_dict['avg_pulse'] = averages.get('avg_pulse', '')
		patient_dict['bmr'] = latest_vitals.get('bmr', '')
		patient_dict['bmr_data_time'] = get_time(latest_vitals.get('bmr_time')) if latest_vitals.get('bmr_time') else ''
		patient_dict['avg_bmr'] = averages.get('avg_bmr', '')
		patient_dict['spo2'] = latest_vitals.get('spo2', '')
		patient_dict['spo2_data_time'] = get_time(latest_vitals.get('spo2_time')) if latest_vitals.get('spo2_time') else ''
		patient_dict['avg_spo2'] = averages.get('avg_spo2', '')

		# Health flags
		usertext11 = patient_additional['history'].get('usertext11', '')
		new_ht = 0
		diabetes = 0
		if usertext11:
			ht_value = usertext11.split("|")
			if "ht" in ht_value:
				new_ht = 1
			if 'db' in ht_value:
				diabetes = 1

		patient_dict['hypertension'] = new_ht
		patient_dict['diabetes'] = diabetes

		smoking = 0
		tobacco_info = patient_additional['history'].get('tobacco', '')
		if tobacco_info and 'current' in tobacco_info.lower():
			smoking = 1

		patient_dict['smoking'] = smoking

		# Encounter processing
		encounter_data = patient_additional['encounter']
		patient_dict['encounter'] = encounter_data.get('encounter', '')
		patient_dict['encounterStatus'] = 0

		# Calculate days remaining and duration
		days_remaining, duration, need_count = await get_remaining_days(db, pid)
		patient_dict['days_remaining'] = days_remaining
		patient_dict['duration'] = duration
		patient_dict['need_count'] = need_count

		# Scores
		patient_dict['scores'] = patient_additional.get('scores', "Score not found")

		# Build vitals arrays
		reading_time = latest_vitals.get('reading_time')
		time_str = get_time(reading_time) if reading_time else ''

		# Initialize arrays
		patient_dict['pb'] = []
		patient_dict['pulse_list'] = []
		patient_dict['weight_list'] = []
		patient_dict['spo2_list'] = []
		patient_dict['glucose_list'] = []
		patient_dict['ketone_list'] = []

		# Add data to arrays if available
		if systolic and diastolic:
			patient_dict['pb'].append({
				'pb': f"{systolic}/{diastolic}",
				'time': time_str,
				'pbs': systolic
			})

		if latest_vitals.get('pulse'):
			patient_dict['pulse_list'].append({
				'pulse': latest_vitals['pulse'],
				'time': time_str
			})

		if weight_lb:
			patient_dict['weight_list'].append({
				'weight': weight_lb,
				'time': time_str
			})

		if latest_vitals.get('spo2'):
			patient_dict['spo2_list'].append({
				'spo2': latest_vitals['spo2'],
				'time': time_str
			})

		if latest_vitals.get('blood_glucose'):
			patient_dict['glucose_list'].append({
				'glucose': latest_vitals['blood_glucose'],
				'time': time_str
			})

		if latest_vitals.get('ketone'):
			patient_dict['ketone_list'].append({
				'ketone': latest_vitals['ketone'],
				'time': time_str
			})

		return patient_dict

	except Exception as e:
		logger.error(f"Error in get_single_patient_data_optimized: {str(e)}")
		raise