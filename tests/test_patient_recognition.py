"""Tests for phone normalization, returning patient recognition, name conflict handling, token idempotency, and history retention."""
import tempfile
import unittest
from pathlib import Path

from src.database.schema import init_db
from src.services.patient_service import (
    normalize_phone, normalize_name, names_are_consistent,
    register_or_get_patient, create_visit, PatientNameConflictError,
    find_patient_by_phone, find_patient_by_id, get_patient_history,
    record_vitals, save_intake, checkin_returning_patient,
    verify_and_get_returning_patient, lookup_patient_by_phone_and_name
)
from src.services.doctor_service import save_doctor_notes


class TestPhoneAndNameNormalization(unittest.TestCase):
    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+91 98765 43210"), "9876543210")
        self.assertEqual(normalize_phone("+91-98765-43210"), "9876543210")
        self.assertEqual(normalize_phone("919876543210"), "9876543210")
        self.assertEqual(normalize_phone("09876543210"), "9876543210")
        self.assertEqual(normalize_phone("9876543210"), "9876543210")
        self.assertEqual(normalize_phone("  98765 43210  "), "9876543210")
        self.assertEqual(normalize_phone(""), "")

    def test_name_normalization_and_consistency(self):
        # Case and whitespace variations
        self.assertTrue(names_are_consistent("Ramesh Patel", "ramesh patel"))
        self.assertTrue(names_are_consistent("  Ramesh   Patel ", "Ramesh Patel"))
        
        # Titles and honorifics
        self.assertTrue(names_are_consistent("Mr. Ramesh Patel", "Ramesh Patel"))
        self.assertTrue(names_are_consistent("Dr. Ramesh Patel", "Ramesh Patel"))
        self.assertTrue(names_are_consistent("Mrs. Anita Sharma", "Anita Sharma"))

        # Subset & order variation
        self.assertTrue(names_are_consistent("Ramesh Patel", "Patel Ramesh"))
        self.assertTrue(names_are_consistent("Ramesh Kumar Patel", "Ramesh Patel"))
        self.assertTrue(names_are_consistent("Ramesh", "Ramesh Patel"))

        # Conflicting/distinct names should not match
        self.assertFalse(names_are_consistent("Ramesh Patel", "Suresh Patel"))
        self.assertFalse(names_are_consistent("Anita Sharma", "Sunita Sharma"))
        self.assertFalse(names_are_consistent("Pooja Verma", "Ramesh Patel"))


class TestPatientRecognitionAndConflict(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_hospital.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_time_patient_registration(self):
        p, is_new = register_or_get_patient("9876543210", "Ramesh Patel", age=45, gender="Male", db_path=self.db_path)
        self.assertTrue(is_new)
        self.assertTrue(p["patient_id"].startswith("P"))
        self.assertTrue(len(p["patient_id"]) <= 8, "Short permanent MRN format requirement (e.g. P10001)")
        self.assertEqual(p["phone"], "9876543210")
        self.assertEqual(p["name"], "Ramesh Patel")

    def test_different_patients_receive_unique_short_mrns(self):
        p1, _ = register_or_get_patient("9876500011", "Patient One", db_path=self.db_path)
        p2, _ = register_or_get_patient("9876500012", "Patient Two", db_path=self.db_path)
        self.assertNotEqual(p1["patient_id"], p2["patient_id"])
        self.assertTrue(p1["patient_id"].startswith("P"))
        self.assertTrue(p2["patient_id"].startswith("P"))

    def test_returning_patient_recognition_reuses_mrn(self):
        # Initial registration with formatted phone
        p1, is_new1 = register_or_get_patient("+91 98765-43210", "Ramesh Patel", age=45, gender="Male", db_path=self.db_path)
        self.assertTrue(is_new1)

        # Returning patient check-in with 10 digits and lowercase name with salutation
        p2, is_new2 = register_or_get_patient("9876543210", "mr. ramesh patel", db_path=self.db_path)
        self.assertFalse(is_new2)
        self.assertEqual(p1["patient_id"], p2["patient_id"], "Permanent MRN must be reused for returning patient")

    def test_name_conflict_detection_and_resolution(self):
        # Register original patient
        p1, _ = register_or_get_patient("9876543210", "Ramesh Patel", age=45, gender="Male", db_path=self.db_path)

        # Family member or another person checks in with the same phone but conflicting name
        with self.assertRaises(PatientNameConflictError) as ctx:
            register_or_get_patient("9876543210", "Pooja Sharma", age=30, gender="Female", db_path=self.db_path)
        self.assertIn("Ramesh Patel", str(ctx.exception))
        self.assertEqual(ctx.exception.existing_patient["patient_id"], p1["patient_id"])

        # Resolution Option 1: User confirms identity ("Yes, I am Ramesh Patel")
        p_confirmed, is_new_conf = register_or_get_patient(
            "9876543210", "Pooja Sharma", confirm_existing=True, db_path=self.db_path
        )
        self.assertFalse(is_new_conf)
        self.assertEqual(p_confirmed["patient_id"], p1["patient_id"])

        # Resolution Option 2: Family member registers as distinct patient on shared phone (force_new=True)
        p_family, is_new_fam = register_or_get_patient(
            "9876543210", "Pooja Sharma", age=30, gender="Female", force_new=True, db_path=self.db_path
        )
        self.assertTrue(is_new_fam)
        self.assertNotEqual(p_family["patient_id"], p1["patient_id"], "Family member must receive unique MRN")
        self.assertEqual(p_family["phone"], "9876543210")

    def test_token_idempotency_and_sequence(self):
        p1, _ = register_or_get_patient("9876500001", "Arun Kumar", db_path=self.db_path)
        p2, _ = register_or_get_patient("9876500002", "Bala Murali", db_path=self.db_path)

        # First visit for p1
        v1 = create_visit(p1["patient_id"], db_path=self.db_path)
        self.assertEqual(v1["token_number"], "T-101")
        self.assertEqual(v1["status"], "waiting")

        # Double-click or browser refresh by p1 should return the same waiting visit and token
        v1_repeat = create_visit(p1["patient_id"], db_path=self.db_path)
        self.assertEqual(v1_repeat["visit_id"], v1["visit_id"])
        self.assertEqual(v1_repeat["token_number"], "T-101")

        # Second patient gets sequential next token
        v2 = create_visit(p2["patient_id"], db_path=self.db_path)
        self.assertEqual(v2["token_number"], "T-102")

    def test_multi_visit_history_preservation(self):
        # Visit 1
        p, _ = register_or_get_patient("9876599999", "Sunitha Rao", age=48, gender="Female", db_path=self.db_path)
        v1 = create_visit(p["patient_id"], db_path=self.db_path)
        save_intake(
            visit_id=v1["visit_id"],
            patient_id=p["patient_id"],
            reason_for_visit="Hypertension follow-up",
            symptoms_text="Occasional headache in mornings",
            duration="2 weeks",
            conditions="Hypertension",
            medications="Amlodipine 5mg",
            allergies="None",
            db_path=self.db_path
        )
        save_doctor_notes(
            visit_id=v1["visit_id"],
            patient_id=p["patient_id"],
            clinical_notes="BP under fair control. No target organ damage.",
            plan="Continue Amlodipine 5mg. Review in 1 month.",
            db_path=self.db_path
        )

        # Later return visit (allow_duplicate_today=True to simulate distinct subsequent visit)
        v2 = create_visit(p["patient_id"], allow_duplicate_today=True, db_path=self.db_path)
        self.assertNotEqual(v1["visit_id"], v2["visit_id"])

        # Longitudinal history retrieval
        past_records = get_patient_history(p["patient_id"], exclude_visit_id=v2["visit_id"], db_path=self.db_path)
        self.assertEqual(len(past_records), 1)
        prev = past_records[0]
        self.assertEqual(prev["visit_id"], v1["visit_id"])
        self.assertEqual(prev["token_number"], "T-101")
        self.assertEqual(prev["doctor_notes"]["clinical_notes"], "BP under fair control. No target organ damage.")
        self.assertEqual(prev["intake"]["reason_for_visit"], "Hypertension follow-up")

    def test_verified_returning_patient_checkin_flow(self):
        # 1. Register initial patient
        p, _ = register_or_get_patient("9876543201", "Gopal Das", age=58, gender="Male", db_path=self.db_path)
        mrn = p["patient_id"]

        # Initial visit with chronic conditions
        v1 = create_visit(mrn, db_path=self.db_path)
        save_intake(
            visit_id=v1["visit_id"],
            patient_id=mrn,
            reason_for_visit="Routine diabetes check",
            symptoms_text="No acute distress",
            conditions="Type 2 Diabetes, High Cholesterol",
            medications="Metformin 1000mg, Rosuvastatin 10mg",
            allergies="Sulfa drugs",
            db_path=self.db_path
        )
        save_doctor_notes(
            visit_id=v1["visit_id"],
            patient_id=mrn,
            clinical_notes="Fasting glucose elevated. Advised dietary control.",
            plan="Continue Metformin 1000mg BD.",
            db_path=self.db_path
        )

        # 2. Returning patient check-in with MRN and matching phone verification
        res = checkin_returning_patient(
            patient_id=mrn,
            verification_phone="9876543201",
            db_path=self.db_path
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["patient"]["patient_id"], mrn, "MRN must be preserved")
        self.assertNotEqual(res["visit"]["visit_id"], v1["visit_id"], "New visit ID must be issued after prior visit is completed")
        self.assertIn("Type 2 Diabetes", res["prefill"]["medical_conditions"], "Past conditions must be prefilled")
        self.assertIn("Sulfa drugs", res["prefill"]["known_allergies"], "Past allergies must be prefilled")

    def test_identity_verification_rejection_on_mismatched_phone(self):
        p, _ = register_or_get_patient("9876543202", "Maya Devi", db_path=self.db_path)
        mrn = p["patient_id"]

        # Attempt returning check-in with wrong phone
        with self.assertRaises(ValueError) as ctx:
            checkin_returning_patient(patient_id=mrn, verification_phone="9999999999", db_path=self.db_path)
        self.assertIn("Identity verification failed", str(ctx.exception))

    def test_unknown_mrn_rejection(self):
        with self.assertRaises(ValueError) as ctx:
            checkin_returning_patient(patient_id="P99999", verification_phone="9876543200", db_path=self.db_path)
        self.assertIn("No patient found with MRN", str(ctx.exception))

    def test_forgot_mrn_lookup_by_phone(self):
        p, _ = register_or_get_patient("9876543203", "Kishore Kumar", db_path=self.db_path)
        mrn = p["patient_id"]

        # Lookup by phone
        records = lookup_patient_by_phone_and_name("9876543203", db_path=self.db_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["patient_id"], mrn)
        self.assertEqual(records[0]["name"], "Kishore Kumar")

    def test_legacy_patient_id_backward_compatibility(self):
        # Insert a legacy patient manually with PAT-2024-XXXX format
        with init_db(self.db_path) as conn:
            pass  # Ensures db exists
        from src.database.connection import get_db
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO patients (patient_id, phone, name, age, gender) VALUES (?, ?, ?, ?, ?)",
                ("PAT-2024-LEGACY01", "9876543204", "Legacy Patient", 65, "Male")
            )

        # Lookup and checkin with legacy MRN
        p = find_patient_by_id("pat-2024-legacy01", db_path=self.db_path)
        self.assertIsNotNone(p)
        self.assertEqual(p["patient_id"], "PAT-2024-LEGACY01")

        # Returning checkin with legacy MRN
        res = checkin_returning_patient("PAT-2024-LEGACY01", verification_phone="9876543204", db_path=self.db_path)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["patient"]["patient_id"], "PAT-2024-LEGACY01")


if __name__ == "__main__":
    unittest.main()
