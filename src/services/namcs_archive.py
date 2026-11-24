"""Look up de-identified survey encounters from the Patient Records archive."""

import json
import re
import zlib

from src.database.connection import get_db
from src.database.postgres import database_url


def _archive_patient(survey_id, record):
    age = record.get("AGE")
    return {
        "patient_id": f"NAMCS-SURVEY-{survey_id:06d}",
        "name": f"NAMCS Visit {survey_id}",
        "age": int(float(age)) if age not in (None, "") else None,
        "gender": {"1": "Male", "2": "Female"}.get(str(record.get("SEX"))),
        "phone": None,
        "source": "namcs",
    }


def _survey_prefix(query):
    match = re.fullmatch(r"(?:NAMCS(?:[-\s]+(?:VISIT|SURVEY))?[-\s]*)?(\d{1,6})", query, re.IGNORECASE)
    return match[1].lstrip("0") if match else None


def search_archive(query, limit=25):
    if not database_url():
        return []
    prefix = _survey_prefix(query)
    if not prefix and not re.fullmatch(r"NAMCS(?:[-\s]+(?:VISIT|SURVEY))?[-\s]*", query, re.IGNORECASE):
        return []
    with get_db() as conn:
        if prefix:
            # A numeric prefix is a union of bounded ranges on the primary key.
            ranges = [(int(prefix) * 10**power, (int(prefix) + 1) * 10**power)
                      for power in range(7 - len(prefix))]
            predicates = " OR ".join("(survey_id >= ? AND survey_id < ?)" for _ in ranges)
            rows = conn.execute(
                f"SELECT survey_id, record FROM namcs_archive WHERE {predicates} ORDER BY survey_id LIMIT ?",
                (*[bound for interval in ranges for bound in interval], limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT survey_id, record FROM namcs_archive ORDER BY survey_id LIMIT ?", (limit,)).fetchall()
    return [_archive_patient(row["survey_id"], json.loads(zlib.decompress(row["record"]))) for row in rows]


def get_archive_profile(patient_id):
    match = re.fullmatch(r"NAMCS-SURVEY-(\d{1,6})", patient_id, re.IGNORECASE)
    if not match or not database_url():
        return None
    survey_id = int(match[1])
    with get_db() as conn:
        row = conn.execute("SELECT record FROM namcs_archive WHERE survey_id = ?", (survey_id,)).fetchone()
    if not row:
        return None
    record = json.loads(zlib.decompress(row["record"]))
    diagnoses = []
    for index in range(1, 31):
        field = f"DX{index}"
        code = record.get(field)
        if code in (None, "", "-9"):
            continue
        diagnoses.append({
            "slot": index,
            "code": code,
            "label": record.get(f"{field}_LABEL"),
            "explanation": record.get(f"{field}_EXPLANATION"),
            "type": {"1": "Primary", "2": "Non-primary"}.get(str(record.get(f"DX_TYPE{index}"))),
        })
    return {
        "source": "namcs",
        "patient": _archive_patient(survey_id, record),
        "visits_count": 1,
        "chronic_conditions": "Not provided",
        "current_medications": "Not provided",
        "known_allergies": "Not provided",
        "visits": [{
            "visit_id": f"NAMCS-SURVEY-{survey_id}",
            "status": "completed",
            "survey_year": record.get("YEAR"),
            "survey_month": record.get("MONTH"),
            "diagnoses": diagnoses,
        }],
        "all_reports": [],
    }
