"""Tests for database persistence, patient registration, visits, tokens, and isolation."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.database.schema import init_db
from src.database.connection import get_db
from src.services.patient_service import (
    register_or_get_patient, find_patient_by_phone, find_patient_by_id,
    create_visit, get_active_visits, get_visit_details, get_patient_history,
    record_vitals, save_intake, PatientNameConflictError
)


class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_hospital.db"
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_and_deduplicate_patient(self):
        # Register new patient
        p1, is_new1 = register_or_get_patient("9876543210", "Sunil Rao", age=45, gender="Male", db_path=self.db_path)
        self.assertTrue(is_new1)
        self.assertTrue(p1["patient_id"].startswith("P"))
        self.assertTrue(len(p1["patient_id"]) <= 8, "Short permanent MRN format requirement")

        # Register same phone and name again -> should deduplicate
        p2, is_new2 = register_or_get_patient("9876543210", "Sunil Rao", db_path=self.db_path)
        self.assertFalse(is_new2)
        self.assertEqual(p1["patient_id"], p2["patient_id"])

        # Different name, same phone -> raises PatientNameConflictError unless force_new=True
        with self.assertRaises(PatientNameConflictError):
            register_or_get_patient("9876543210", "Kavita Rao", db_path=self.db_path)

        # Explicit force_new registers new distinct patient (family member)
        p3, is_new3 = register_or_get_patient("9876543210", "Kavita Rao", force_new=True, db_path=self.db_path)
        self.assertTrue(is_new3)
        self.assertNotEqual(p1["patient_id"], p3["patient_id"])

    def test_create_visit_and_token_assignment(self):
        p, _ = register_or_get_patient("9998887776", "Anita Desai", db_path=self.db_path)
        v1 = create_visit(p["patient_id"], db_path=self.db_path)
        self.assertTrue(v1["visit_id"].startswith("VIS-"))
        self.assertEqual(v1["token_number"], "T-101")

        # Double check-in on same day reuses active waiting token
        v1_rep = create_visit(p["patient_id"], db_path=self.db_path)
        self.assertEqual(v1_rep["token_number"], "T-101")

        # Distinct patient gets next sequential token
        p2, _ = register_or_get_patient("9998887777", "Deepak Rao", db_path=self.db_path)
        v2 = create_visit(p2["patient_id"], db_path=self.db_path)
        self.assertEqual(v2["token_number"], "T-102")

    def test_record_vitals_and_intake(self):
        p, _ = register_or_get_patient("9123456780", "Vikram Sen", db_path=self.db_path)
        v = create_visit(p["patient_id"], db_path=self.db_path)

        record_vitals(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            bp_systolic=130,
            bp_diastolic=85,
            heart_rate=76,
            temperature=98.6,
            spo2=99.0,
            blood_sugar=120.0,
            recorded_by="nurse_mary",
            db_path=self.db_path
        )

        intake_id = save_intake(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            reason_for_visit="Severe headache and nausea",
            symptoms_text="pulsing headache on right side for 2 days",
            duration="2 days",
            severity="Severe",
            conditions="Migraine",
            medications="Paracetamol occasionally",
            allergies="Sulfa drugs",
            submitted_by="patient",
            db_path=self.db_path
        )
        self.assertTrue(intake_id.startswith("INT-"))

        details = get_visit_details(v["visit_id"], db_path=self.db_path)
        self.assertIsNotNone(details["vitals"])
        self.assertEqual(details["vitals"]["bp_systolic"], 130)
        self.assertIsNotNone(details["intake"])
        self.assertEqual(details["intake"]["reason_for_visit"], "Severe headache and nausea")

    def test_patient_record_isolation(self):
        # Create Patient A with visit
        p_a, _ = register_or_get_patient("9000000001", "Patient Alpha", db_path=self.db_path)
        v_a = create_visit(p_a["patient_id"], db_path=self.db_path)
        save_intake(v_a["visit_id"], p_a["patient_id"], "Reason Alpha", "Symptoms Alpha", db_path=self.db_path)

        # Create Patient B with visit
        p_b, _ = register_or_get_patient("9000000002", "Patient Beta", db_path=self.db_path)
        v_b = create_visit(p_b["patient_id"], db_path=self.db_path)
        save_intake(v_b["visit_id"], p_b["patient_id"], "Reason Beta", "Symptoms Beta", db_path=self.db_path)

        # Verify Patient A's history contains ONLY Patient A's records
        history_a = get_patient_history(p_a["patient_id"], db_path=self.db_path)
        self.assertEqual(len(history_a), 1)
        self.assertEqual(history_a[0]["patient_id"], p_a["patient_id"])
        self.assertEqual(history_a[0]["intake"]["reason_for_visit"], "Reason Alpha")

        # Verify Patient B's history contains ONLY Patient B's records
        history_b = get_patient_history(p_b["patient_id"], db_path=self.db_path)
        self.assertEqual(len(history_b), 1)
        self.assertEqual(history_b[0]["patient_id"], p_b["patient_id"])
        self.assertEqual(history_b[0]["intake"]["reason_for_visit"], "Reason Beta")


if __name__ == "__main__":
    unittest.main()
