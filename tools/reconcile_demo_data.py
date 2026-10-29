"""Reconcile the live synthetic dataset with the PDFs used by the demo UI."""

from datetime import datetime
from pathlib import Path
import json
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.connection import get_db
from src.database.schema import get_db_path
from src.services.patient_service import get_visit_details
from src.services.report_service import store_and_register_report


PDF_DIR = ROOT / "data" / "synthetic_lab_reports"
SNEHU_REPORT = ROOT / "snehu_illustrative_iron_deficiency_sample.pdf"
PATIENT_IDS = ("SYN-P001", "SYN-P002", "SYN-P003", "P10001")


def lab(test, value, unit, reference, flag="IN_RANGE"):
    notes = {
        "LOW": "below listed range",
        "HIGH": "above listed range",
        "REVIEW": "review against clinical target",
    }
    return {
        "test": test,
        "value": str(value),
        "unit": unit,
        "reference_range": reference,
        "range_note": notes.get(flag, ""),
        "source_line": f"{test} {value} {unit} {reference} {flag}",
    }


REPORT_SPECS = [
    {
        "patient_id": "SYN-P001", "visit_id": "VIS-P001-00", "date": "2025-11-12 14:05:00",
        "path": PDF_DIR / "SYN-P001_P001-D02_lab_report.pdf",
        "rows": [
            lab("HbA1c", 8.1, "%", "4.0-5.6", "HIGH"),
            lab("Fasting plasma glucose", 156, "mg/dL", "70-99", "HIGH"),
            lab("Creatinine", 0.9, "mg/dL", "0.7-1.3"),
            lab("Sodium", 139, "mmol/L", "135-145"),
        ],
    },
    {
        "patient_id": "SYN-P001", "visit_id": "VIS-P001-01", "date": "2026-04-15 14:05:00",
        "path": PDF_DIR / "SYN-P001_P001-D04_lab_report.pdf",
        "rows": [
            lab("HbA1c", 7.6, "%", "4.0-5.6", "HIGH"),
            lab("Fasting plasma glucose", 132, "mg/dL", "70-99", "HIGH"),
            lab("Creatinine", 0.9, "mg/dL", "0.7-1.3"),
            lab("LDL cholesterol", 118, "mg/dL", "Laboratory-specific", "REVIEW"),
        ],
    },
    {
        "patient_id": "SYN-P002", "visit_id": "VIS-P002-00", "date": "2025-09-08 14:07:00",
        "path": PDF_DIR / "SYN-P002_P002-D02_vitals_and_labs.pdf",
        "rows": [
            lab("Creatinine", 0.8, "mg/dL", "0.6-1.1"),
            lab("Potassium", 4.0, "mmol/L", "3.5-5.1"),
            lab("Sodium", 140, "mmol/L", "135-145"),
        ],
    },
    {
        "patient_id": "SYN-P002", "visit_id": "VIS-P002-01", "date": "2026-02-10 14:07:00",
        "path": PDF_DIR / "SYN-P002_P002-D04_vitals_and_labs.pdf",
        "rows": [
            lab("Creatinine", 0.8, "mg/dL", "0.6-1.1"),
            lab("Potassium", 4.1, "mmol/L", "3.5-5.1"),
        ],
    },
    {
        "patient_id": "SYN-P003", "visit_id": "VIS-P003-00", "date": "2025-08-19 14:08:00",
        "path": PDF_DIR / "SYN-P003_P003-D02_lab_report.pdf",
        "rows": [
            lab("Total cholesterol", 238, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("LDL cholesterol", 158, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("HDL cholesterol", 42, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("Triglycerides", 190, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("TSH", 2.4, "mIU/L", "0.4-4.0"),
            lab("Haemoglobin", 13.8, "g/dL", "13.0-17.0"),
        ],
    },
    {
        "patient_id": "SYN-P003", "visit_id": "VIS-P003-01", "date": "2026-03-03 14:08:00",
        "path": PDF_DIR / "SYN-P003_P003-D04_lab_report.pdf",
        "rows": [
            lab("Total cholesterol", 211, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("LDL cholesterol", 132, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("HDL cholesterol", 44, "mg/dL", "Laboratory-specific", "REVIEW"),
            lab("Triglycerides", 176, "mg/dL", "Laboratory-specific", "REVIEW"),
        ],
    },
    {
        "patient_id": "P10001", "visit_id": "VIS-20261029-F3871", "date": "2026-10-29 14:00:00",
        "path": SNEHU_REPORT,
        "rows": [
            lab("Haemoglobin", 9.8, "g/dL", "12.0-15.5", "LOW"),
            lab("RBC count", 3.7, "million/µL", "3.8-5.2", "LOW"),
            lab("MCV", 72, "fL", "80-100", "LOW"),
            lab("MCH", 23, "pg", "27-33", "LOW"),
            lab("WBC count", 6500, "/µL", "4000-11000"),
            lab("Platelets", 310000, "/µL", "150000-450000"),
            lab("Serum iron", 28, "µg/dL", "50-170", "LOW"),
            lab("Ferritin", 8, "ng/mL", "15-150", "LOW"),
            lab("TIBC", 460, "µg/dL", "250-450", "HIGH"),
            lab("Transferrin saturation", 6.1, "%", "20-50", "LOW"),
        ],
    },
]


def backup_database():
    db_path = get_db_path()
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"hospital-before-meaningful-data-{stamp}.db"
    source = sqlite3.connect(str(db_path))
    target = sqlite3.connect(str(backup_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def ensure_coherent_people_and_visits(conn):
    conn.execute("UPDATE patients SET name = 'Meera Kulkarni', age = 46 WHERE patient_id = 'SYN-P002'")
    conn.execute("UPDATE patients SET name = 'Imran Shaikh', age = 61 WHERE patient_id = 'SYN-P003'")
    conn.execute("UPDATE patients SET name = 'Snehu', age = 19, gender = 'Female' WHERE patient_id = 'P10001'")

    conn.execute("UPDATE visits SET created_at = '2025-11-12 10:15:00' WHERE visit_id = 'VIS-P001-00'")
    conn.execute("UPDATE intakes SET created_at = '2025-11-12 10:15:00' WHERE visit_id = 'VIS-P001-00'")
    conn.execute("UPDATE vitals SET created_at = '2025-11-12 10:15:00' WHERE visit_id = 'VIS-P001-00'")
    conn.execute("UPDATE doctor_notes SET updated_at = '2025-11-12 10:15:00' WHERE visit_id = 'VIS-P001-00'")
    conn.execute("UPDATE visits SET created_at = '2025-09-08 11:30:00' WHERE visit_id = 'VIS-P002-00'")
    conn.execute("UPDATE intakes SET created_at = '2025-09-08 11:30:00' WHERE visit_id = 'VIS-P002-00'")
    conn.execute("UPDATE vitals SET created_at = '2025-09-08 11:30:00' WHERE visit_id = 'VIS-P002-00'")
    conn.execute("UPDATE doctor_notes SET updated_at = '2025-09-08 11:30:00' WHERE visit_id = 'VIS-P002-00'")

    conn.execute(
        """INSERT INTO visits (visit_id, patient_id, token_number, status, created_at)
           VALUES ('VIS-P003-00', 'SYN-P003', 'T-087', 'completed', '2025-08-19 10:00:00')
           ON CONFLICT(visit_id) DO UPDATE SET status = 'completed', created_at = excluded.created_at"""
    )
    conn.execute(
        """INSERT INTO intakes (intake_id, visit_id, patient_id, reason_for_visit, symptoms_text, duration, severity,
                                  associated_symptoms, medical_conditions, current_medications, known_allergies,
                                  previous_history, submitted_by, created_at)
           VALUES ('INT-VIS-P003-00', 'VIS-P003-00', 'SYN-P003', 'Dyslipidemia review',
                   'intermittent low energy without chest pain or shortness of breath', 'Several weeks', 'Mild',
                   'No fever or unintentional weight loss', 'Dyslipidemia', 'No regular medicine confirmed at this visit',
                   'Unconfirmed antibiotic-associated rash in childhood', 'Sedentary lifestyle', 'patient', '2025-08-19 10:00:00')
           ON CONFLICT(visit_id) DO UPDATE SET reason_for_visit = excluded.reason_for_visit,
                   symptoms_text = excluded.symptoms_text, duration = excluded.duration, severity = excluded.severity,
                   associated_symptoms = excluded.associated_symptoms, medical_conditions = excluded.medical_conditions,
                   current_medications = excluded.current_medications, known_allergies = excluded.known_allergies,
                   previous_history = excluded.previous_history, created_at = excluded.created_at"""
    )
    conn.execute(
        """INSERT INTO vitals (visit_id, patient_id, bp_systolic, bp_diastolic, heart_rate, temperature, spo2,
                                blood_sugar, recorded_by, created_at)
           VALUES ('VIS-P003-00', 'SYN-P003', 130, 80, 76, 97.7, 98, 108, 'NURSE-ANITA', '2025-08-19 10:00:00')
           ON CONFLICT(visit_id) DO UPDATE SET bp_systolic = excluded.bp_systolic,
                   bp_diastolic = excluded.bp_diastolic, heart_rate = excluded.heart_rate,
                   temperature = excluded.temperature, spo2 = excluded.spo2, blood_sugar = excluded.blood_sugar,
                   recorded_by = excluded.recorded_by, created_at = excluded.created_at"""
    )
    conn.execute(
        """INSERT INTO doctor_notes (visit_id, patient_id, doctor_id, clinical_notes, plan, updated_at)
           VALUES ('VIS-P003-00', 'SYN-P003', 'DR-SHARMA',
                   'General examination stable. Cardiovascular and respiratory examinations were unremarkable.',
                   'Reviewed the lipid results, documented lifestyle counselling, and requested medication reconciliation and a repeat lipid profile before follow-up.',
                   '2025-08-19 10:30:00')
           ON CONFLICT(visit_id) DO UPDATE SET clinical_notes = excluded.clinical_notes,
                   plan = excluded.plan, doctor_id = excluded.doctor_id, updated_at = excluded.updated_at"""
    )

    conn.execute(
        """UPDATE intakes SET reason_for_visit = 'Review of persistent fatigue with uploaded iron studies',
                   symptoms_text = 'persistent tiredness, reduced concentration and occasional light-headedness',
                   duration = '3 weeks', severity = 'Moderate',
                   associated_symptoms = 'reduced exercise tolerance; no chest pain or fainting',
                   medical_conditions = 'No known chronic conditions', current_medications = 'No regular medicines',
                   known_allergies = 'No known drug allergies',
                   previous_history = 'No earlier hospital consultation is recorded'
           WHERE visit_id = 'VIS-20261029-F3871'"""
    )
    conn.execute(
        """UPDATE intakes SET medical_conditions = 'Dyslipidemia',
                   current_medications = 'Atorvastatin 10 mg nightly from an older prescription (current status unverified)'
           WHERE visit_id = 'VIS-P003-01'"""
    )


def replace_reports_and_results(conn):
    placeholders = ",".join("?" for _ in PATIENT_IDS)
    conn.execute(f"DELETE FROM reports WHERE patient_id IN ({placeholders})", PATIENT_IDS)

    for spec in REPORT_SPECS:
        path = spec["path"]
        if not path.exists():
            raise FileNotFoundError(path)
        report, _ = store_and_register_report(
            file_bytes=path.read_bytes(),
            filename=path.name,
            patient_id=spec["patient_id"],
            visit_id=spec["visit_id"],
            conn=conn,
        )
        conn.execute("UPDATE reports SET created_at = ? WHERE report_id = ?", (spec["date"], report["report_id"]))
        for item in spec["rows"]:
            conn.execute(
                """INSERT INTO extracted_results (
                       extract_id, report_id, patient_id, visit_id, test_name, test_value, unit,
                       reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', ?, 1, 'curated_pdf_review')""",
                (
                    f"EXT-{uuid.uuid4().hex[:8]}", report["report_id"], spec["patient_id"], spec["visit_id"],
                    item["test"], item["value"], item["unit"], item["reference_range"], item["range_note"],
                    item["source_line"],
                ),
            )


def refresh_summaries(conn):
    placeholders = ",".join("?" for _ in PATIENT_IDS)
    conn.execute(f"DELETE FROM summaries WHERE patient_id IN ({placeholders})", PATIENT_IDS)


def main():
    backup_path = backup_database()
    with get_db() as conn:
        ensure_coherent_people_and_visits(conn)
        replace_reports_and_results(conn)
        refresh_summaries(conn)

    with get_db() as conn:
        visit_ids = [row["visit_id"] for row in conn.execute(
            "SELECT visit_id FROM visits WHERE patient_id IN (?, ?, ?, ?) ORDER BY created_at",
            PATIENT_IDS,
        ).fetchall()]
    for visit_id in visit_ids:
        get_visit_details(visit_id)

    with get_db() as conn:
        report_count = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE patient_id IN (?, ?, ?, ?)", PATIENT_IDS
        ).fetchone()[0]
        result_count = conn.execute(
            "SELECT COUNT(*) FROM extracted_results WHERE patient_id IN (?, ?, ?, ?)", PATIENT_IDS
        ).fetchone()[0]
        duplicate_count = conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT report_id, test_name, test_value, unit, reference_range, page, COUNT(*) AS n
                   FROM extracted_results
                   WHERE patient_id IN (?, ?, ?, ?)
                   GROUP BY report_id, test_name, test_value, unit, reference_range, page
                   HAVING n > 1
               )""",
            PATIENT_IDS,
        ).fetchone()[0]
    print(json.dumps({
        "backup": str(backup_path),
        "reports": report_count,
        "results": result_count,
        "duplicate_result_groups": duplicate_count,
        "refreshed_visits": visit_ids,
    }, indent=2))


if __name__ == "__main__":
    main()
