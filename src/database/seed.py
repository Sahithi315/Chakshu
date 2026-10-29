"""Database seeder: populates hospital.db with synthetic patient records, visits, vitals, and reports."""
from pathlib import Path
import json
import uuid
from src.database.connection import get_db
from src.database.schema import init_db
from src.services.patient_service import register_or_get_patient, create_visit, record_vitals, save_intake
from src.services.report_service import store_and_register_report
from src.services.ocr_service import process_report_file
from src.services.summary_service import generate_clinical_summary, save_summary

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "data" / "synthetic_lab_reports" / "manifest.json"
PDF_DIR = ROOT / "data" / "synthetic_lab_reports"

SEED_PATIENTS = [
    {
        "patient_id": "SYN-P001",
        "name": "Aarav Nair",
        "phone": "9876543210",
        "age": 52,
        "gender": "Male",
        "reason": "Type 2 diabetes follow-up and foot tingling",
        "symptoms": "bilateral foot tingling for 2 months, mild numbness in toes, no chest pain",
        "duration": "2 months",
        "severity": "Mild",
        "associated": "Tingling sensation worse at night",
        "conditions": "Type 2 Diabetes Mellitus (4 years), Dyslipidemia",
        "medications": "Metformin 500 mg twice daily, Atorvastatin 10 mg at bedtime",
        "allergies": "No known drug allergies",
        "history": "Diagnosed with diabetes in 2022. Non-smoker.",
        "vitals": {"bp_systolic": 136, "bp_diastolic": 84, "heart_rate": 78, "temperature": 98.1, "spo2": 98.0, "blood_sugar": 142.0},
        "reports": ["SYN-P001_P001-D04_lab_report.pdf"],
        "prior_visit": {
            "visit_id": "VIS-P001-00",
            "token_number": "T-098",
            "created_at": "2025-11-12 10:15:00",
            "reason": "Routine diabetes follow-up & initial bilateral foot numbness",
            "symptoms": "intermittent numbness in toes, mild burning sensation on soles of feet",
            "duration": "3 weeks",
            "severity": "Mild",
            "conditions": "Type 2 Diabetes Mellitus, Hyperlipidemia",
            "medications": "Metformin 500mg BD",
            "allergies": "No known drug allergies",
            "clinical_notes": "Bilateral distal lower extremity sensory reduction to 10g monofilament testing. Dorsalis pedis pulses palpable bilaterally. Heart rate regular, lungs clear on auscultation. BP 138/86 mmHg.",
            "plan": "Impression: Early Diabetic Peripheral Neuropathy. Continue Metformin 500mg BD. Add Atorvastatin 10mg at bedtime for dyslipidemia. Advised strict glycemic control, daily foot inspections, and supportive footwear. Order repeat HbA1c and lipid panel in 3 months.",
            "doctor_id": "DR-SHARMA",
            "vitals": {"bp_systolic": 138, "bp_diastolic": 86, "heart_rate": 76, "temperature": 98.2, "spo2": 98.0, "blood_sugar": 156.0}
        }
    },
    {
        "patient_id": "SYN-P002",
        "name": "Meera Kulkarni",
        "phone": "9876543211",
        "age": 46,
        "gender": "Female",
        "reason": "Hypertension routine review and episodic headache",
        "symptoms": "intermittent morning headaches for 3 weeks, mild neck stiffness, no visual changes",
        "duration": "3 weeks",
        "severity": "Moderate",
        "associated": "Occasional dizziness upon sudden standing",
        "conditions": "Essential Hypertension (6 years)",
        "medications": "Amlodipine 5 mg once daily (missed 3 doses recently)",
        "allergies": "Penicillin (rash)",
        "history": "Family history of early coronary artery disease.",
        "vitals": {"bp_systolic": 148, "bp_diastolic": 92, "heart_rate": 82, "temperature": 97.9, "spo2": 99.0, "blood_sugar": 108.0},
        "reports": ["SYN-P002_P002-D04_vitals_and_labs.pdf"],
        "prior_visit": {
            "visit_id": "VIS-P002-00",
            "token_number": "T-092",
            "created_at": "2025-09-08 11:30:00",
            "reason": "Hypertension routine check and episodic occipital tension",
            "symptoms": "throbbing morning headaches for 10 days, work-related stress",
            "duration": "10 days",
            "severity": "Moderate",
            "conditions": "Essential Hypertension (6 years)",
            "medications": "Amlodipine 5mg OD",
            "allergies": "Penicillin (rash)",
            "clinical_notes": "BP 152/94 mmHg sitting right arm. Fundus normal, no papilledema. S1/S2 audible, no murmurs. Lungs clear. Stress-related tension component noted.",
            "plan": "Impression: Stage 2 Hypertension, suboptimal control with recent medication non-adherence. Emphasized strict daily compliance with Amlodipine 5mg OD. Advised low-sodium diet (<2g/day) and home BP log recording. Follow up in 3-4 weeks.",
            "doctor_id": "DR-KAPOOR",
            "vitals": {"bp_systolic": 152, "bp_diastolic": 94, "heart_rate": 84, "temperature": 98.4, "spo2": 99.0, "blood_sugar": 102.0}
        }
    },
    {
        "patient_id": "SYN-P003",
        "name": "Imran Shaikh",
        "phone": "9876543212",
        "age": 61,
        "gender": "Male",
        "reason": "Follow-up for dyslipidemia and generalized fatigue",
        "symptoms": "feeling tired and low energy for 1 month, no shortness of breath, no fever",
        "duration": "1 month",
        "severity": "Mild",
        "associated": "Slight muscle soreness",
        "conditions": "Dyslipidemia",
        "medications": "Atorvastatin 10 mg at night from an older prescription (current status unverified)",
        "allergies": "Unknown / Unconfirmed antibiotic rash in childhood",
        "history": "Sedentary lifestyle, attempting dietary improvements.",
        "vitals": {"bp_systolic": 128, "bp_diastolic": 78, "heart_rate": 74, "temperature": 98.0, "spo2": 98.5, "blood_sugar": 115.0},
        "reports": ["SYN-P003_P003-D04_lab_report.pdf"]
    }
]


def seed_database(db_path=None):
    """Seed synthetic patient records into SQLite database."""
    init_db(db_path)

    with get_db(db_path) as conn:
        for pdata in SEED_PATIENTS:
            pid = pdata["patient_id"]

            # 1. Register or retrieve patient
            p_row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (pid,)).fetchone()
            if not p_row:
                conn.execute(
                    """
                    INSERT INTO patients (patient_id, phone, name, age, gender)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pid, pdata["phone"], pdata["name"], pdata["age"], pdata["gender"])
                )

            # 2. Prior completed visit if present in seed
            prior = pdata.get("prior_visit")
            if prior:
                p_vid = prior["visit_id"]
                p_vrow = conn.execute("SELECT * FROM visits WHERE visit_id = ?", (p_vid,)).fetchone()
                if not p_vrow:
                    conn.execute(
                        """
                        INSERT INTO visits (visit_id, patient_id, token_number, status, created_at)
                        VALUES (?, ?, ?, 'completed', ?)
                        """,
                        (p_vid, pid, prior["token_number"], prior["created_at"])
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO intakes (intake_id, visit_id, patient_id, reason_for_visit, symptoms_text, duration, severity, medical_conditions, current_medications, known_allergies, submitted_by, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'patient', ?)
                        """,
                        (f"INT-{p_vid}", p_vid, pid, prior["reason"], prior["symptoms"], prior["duration"], prior["severity"], prior["conditions"], prior["medications"], prior["allergies"], prior["created_at"])
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO doctor_notes (visit_id, patient_id, doctor_id, clinical_notes, plan, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (p_vid, pid, prior.get("doctor_id", "DR-SHARMA"), prior["clinical_notes"], prior["plan"], prior["created_at"])
                    )
                    pv_vit = prior.get("vitals", {})
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO vitals (visit_id, patient_id, bp_systolic, bp_diastolic, heart_rate, temperature, spo2, blood_sugar, recorded_by, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'nurse_priya', ?)
                        """,
                        (p_vid, pid, pv_vit.get("bp_systolic", 138), pv_vit.get("bp_diastolic", 86), pv_vit.get("heart_rate", 76), pv_vit.get("temperature", 98.2), pv_vit.get("spo2", 98.0), pv_vit.get("blood_sugar", 150.0), prior["created_at"])
                    )

            # 3. Check or create active visit
            v_row = conn.execute("SELECT * FROM visits WHERE patient_id = ? AND status = 'waiting'", (pid,)).fetchone()
            if not v_row:
                visit_id = f"VIS-{pid[-4:]}-01"
                token_num = f"T-{100 + len(conn.execute('SELECT id FROM visits').fetchall()) + 1}"
                conn.execute(
                    """
                    INSERT INTO visits (visit_id, patient_id, token_number, status)
                    VALUES (?, ?, ?, 'waiting')
                    """,
                    (visit_id, pid, token_num)
                )
            else:
                visit_id = v_row["visit_id"]

            # 3. Vitals
            vits = pdata.get("vitals", {})
            record_vitals(
                visit_id=visit_id,
                patient_id=pid,
                bp_systolic=vits.get("bp_systolic"),
                bp_diastolic=vits.get("bp_diastolic"),
                heart_rate=vits.get("heart_rate"),
                temperature=vits.get("temperature"),
                spo2=vits.get("spo2"),
                blood_sugar=vits.get("blood_sugar"),
                recorded_by="nurse_anita",
                conn=conn
            )

            # 4. Intake
            save_intake(
                visit_id=visit_id,
                patient_id=pid,
                reason_for_visit=pdata["reason"],
                symptoms_text=pdata["symptoms"],
                duration=pdata["duration"],
                severity=pdata["severity"],
                associated_symptoms=pdata["associated"],
                conditions=pdata["conditions"],
                medications=pdata["medications"],
                allergies=pdata["allergies"],
                history=pdata["history"],
                submitted_by="patient",
                conn=conn
            )

            # 5. Process reports
            extracted_labs_for_summary = []
            for rep_name in pdata.get("reports", []):
                rep_path = PDF_DIR / rep_name
                if rep_path.exists():
                    file_bytes = rep_path.read_bytes()
                    rep_record, is_new = store_and_register_report(
                        file_bytes=file_bytes,
                        filename=rep_name,
                        patient_id=pid,
                        visit_id=visit_id,
                        conn=conn
                    )
                    # Extract report contents
                    res = process_report_file(rep_path)
                    extracted_rows = res.get("extracted_rows", [])
                    if not extracted_rows:
                        stored_rows = [dict(row) for row in conn.execute(
                            "SELECT test_name AS test, test_value AS value, unit, reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method FROM extracted_results WHERE report_id = ?",
                            (rep_record["report_id"],)
                        ).fetchall()]
                        extracted_labs_for_summary.extend(stored_rows)
                        continue
                    conn.execute("DELETE FROM extracted_results WHERE report_id = ?", (rep_record["report_id"],))
                    for r in extracted_rows:
                        eid = f"EXT-{uuid.uuid4().hex[:8]}"
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO extracted_results (
                                extract_id, report_id, patient_id, visit_id, test_name, test_value,
                                unit, reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (eid, rep_record["report_id"], pid, visit_id, r["test"], r["value"],
                             r.get("unit", ""), r.get("reference_range", ""), r.get("range_note", ""),
                             r.get("page", 1), json.dumps(r.get("bbox", [])), r.get("source_line", ""),
                             1 if r.get("quote_ok", True) else 0, r.get("extraction_method", "pdfplumber"))
                        )
                        extracted_labs_for_summary.append(r)

            # 6. Generate and save pre-consultation summary (including prior visits & doctor notes)
            prior_visits = []
            p_rows = conn.execute(
                "SELECT * FROM visits WHERE patient_id = ? AND visit_id != ? ORDER BY created_at DESC",
                (pid, visit_id)
            ).fetchall()
            for pv in p_rows:
                pv_dict = dict(pv)
                pv_in = conn.execute("SELECT * FROM intakes WHERE visit_id = ?", (pv["visit_id"],)).fetchone()
                pv_dict["intake"] = dict(pv_in) if pv_in else {}
                pv_vit = conn.execute("SELECT * FROM vitals WHERE visit_id = ?", (pv["visit_id"],)).fetchone()
                pv_dict["vitals"] = dict(pv_vit) if pv_vit else {}
                pv_doc = conn.execute("SELECT * FROM doctor_notes WHERE visit_id = ?", (pv["visit_id"],)).fetchone()
                pv_dict["doctor_notes"] = dict(pv_doc) if pv_doc else {}
                pv_dict["extracted_results"] = [dict(r) for r in conn.execute("SELECT * FROM extracted_results WHERE visit_id = ?", (pv["visit_id"],)).fetchall()]
                prior_visits.append(pv_dict)

            summary = generate_clinical_summary(
                intake_data=pdata,
                vitals_data=pdata.get("vitals"),
                extracted_labs=extracted_labs_for_summary,
                returning_history=prior_visits,
                patient_info=pdata
            )
            save_summary(visit_id, pid, summary, conn=conn)

    print("Synthetic database seed completed successfully.")


if __name__ == "__main__":
    seed_database()
