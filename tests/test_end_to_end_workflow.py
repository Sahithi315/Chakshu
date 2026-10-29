"""End-to-end integration test verifying the complete clinical workflow."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from src.database.schema import init_db
from src.services.patient_service import (
    register_or_get_patient, create_visit, record_vitals, save_intake,
    get_visit_details, get_patient_history
)
from src.services.report_service import store_and_register_report
from src.services.ocr_service import process_report_file
from src.services.summary_service import generate_clinical_summary, save_summary
from src.services.doctor_service import (
    record_doctor_decision, save_doctor_notes, get_longitudinal_labs
)
from src.symptoms.infer import Extractor

ROOT = Path(__file__).resolve().parent.parent


class TestEndToEndClinicalWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "hospital_e2e.db"
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_patient_consultation_lifecycle(self):
        # 1. Patient Registration & Token
        patient, is_new = register_or_get_patient(
            phone="9876500001",
            name="Ramesh Patel",
            age=54,
            gender="Male",
            db_path=self.db_path
        )
        self.assertTrue(is_new)
        pid = patient["patient_id"]

        visit1 = create_visit(pid, db_path=self.db_path)
        vid1 = visit1["visit_id"]
        self.assertEqual(visit1["token_number"], "T-101")

        # 2. Nurse records vitals
        record_vitals(
            visit_id=vid1,
            patient_id=pid,
            bp_systolic=144,
            bp_diastolic=92,
            heart_rate=80,
            temperature=98.4,
            spo2=98.0,
            blood_sugar=155.0,
            recorded_by="nurse_priya",
            db_path=self.db_path
        )

        # 3. Patient completes intake questionnaire
        symptom_text = "no chest pain but dry cough for 5 days, mild headache"
        save_intake(
            visit_id=vid1,
            patient_id=pid,
            reason_for_visit="Persistent cough and blood sugar check",
            symptoms_text=symptom_text,
            duration="5 days",
            severity="Mild",
            associated_symptoms="Throat dryness",
            conditions="Type 2 Diabetes (3 years), Hypertension",
            medications="Metformin 500mg BD, Telmisartan 40mg OD",
            allergies="No known drug allergies",
            history="No previous hospitalizations",
            submitted_by="patient",
            db_path=self.db_path
        )

        # 4. Patient tags symptoms using symptom extractor
        extractor = Extractor(fallback_to_baseline=True)
        extracted_sym = extractor.extract(symptom_text)
        self.assertEqual(len(extracted_sym["symptoms"]), 3)
        sym_dict = {s["text"]: s["negated"] for s in extracted_sym["symptoms"]}
        self.assertTrue(sym_dict["chest pain"])  # Denied symptom
        self.assertFalse(sym_dict["cough"])      # Present symptom
        self.assertFalse(sym_dict["headache"])   # Present symptom

        # 5. Patient uploads medical report (synthetic lab report PDF)
        sample_pdf = ROOT / "data" / "synthetic_lab_reports" / "synthetic_report_001.pdf"
        self.assertTrue(sample_pdf.exists(), "Sample PDF fixture should exist")
        pdf_bytes = sample_pdf.read_bytes()

        rep_rec, is_new_rep = store_and_register_report(
            file_bytes=pdf_bytes,
            filename="synthetic_report_001.pdf",
            patient_id=pid,
            visit_id=vid1,
            db_path=self.db_path
        )
        self.assertTrue(is_new_rep)

        # 6. Report processing pipeline
        report_results = process_report_file(rep_rec["storage_path"])
        self.assertEqual(report_results["status"], "success")
        self.assertGreater(len(report_results["extracted_rows"]), 0)

        # 7. AI Pre-Consultation Summary Generation
        summary_payload = generate_clinical_summary(
            intake_data={
                "reason_for_visit": "Persistent cough and blood sugar check",
                "symptoms_text": symptom_text,
                "duration": "5 days",
                "severity": "Mild",
                "medical_conditions": "Type 2 Diabetes (3 years), Hypertension",
                "current_medications": "Metformin 500mg BD, Telmisartan 40mg OD",
                "known_allergies": "No known drug allergies"
            },
            vitals_data={"bp_systolic": 144, "bp_diastolic": 92, "heart_rate": 80, "temperature": 98.4, "spo2": 98.0, "blood_sugar": 155.0},
            extracted_labs=report_results["extracted_rows"]
        )
        save_summary(vid1, pid, summary_payload, db_path=self.db_path)

        # 8. Doctor reviews brief, confirms/corrects items
        record_doctor_decision(
            visit_id=vid1,
            patient_id=pid,
            item_id="sym_cough_1",
            part_type="symptom",
            decision="confirmed",
            db_path=self.db_path
        )
        record_doctor_decision(
            visit_id=vid1,
            patient_id=pid,
            item_id="lab_hb_1",
            part_type="lab",
            decision="confirmed",
            db_path=self.db_path
        )

        # 9. Doctor records consultation notes and completes visit
        save_doctor_notes(
            visit_id=vid1,
            patient_id=pid,
            clinical_notes="Patient alert and oriented. Chest clear. Blood pressure mildly elevated. Advised diet control.",
            plan="Continue Metformin. Check fasting blood sugar in 1 week.",
            doctor_id="DR-SHARMA",
            db_path=self.db_path
        )

        # Verify completed visit state
        v1_details = get_visit_details(vid1, db_path=self.db_path)
        self.assertEqual(v1_details["status"], "completed")
        self.assertIsNotNone(v1_details["doctor_notes"])
        self.assertEqual(len(v1_details["decisions"]), 2)

        # 10. RETURNING PATIENT: Second visit
        patient_ret, is_new_ret = register_or_get_patient(
            phone="9876500001",
            name="Ramesh Patel",
            db_path=self.db_path
        )
        self.assertFalse(is_new_ret)
        self.assertEqual(patient_ret["patient_id"], pid)

        # Retrieve prior history
        history = get_patient_history(pid, db_path=self.db_path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["visit_id"], vid1)
        self.assertEqual(history[0]["doctor_notes"]["doctor_id"], "DR-SHARMA")

        # Second visit created
        visit2 = create_visit(pid, db_path=self.db_path)
        self.assertEqual(visit2["token_number"], "T-102")


if __name__ == "__main__":
    unittest.main()
