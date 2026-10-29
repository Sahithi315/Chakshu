"""Tests for doctor decision recording, notes persistence, and longitudinal queries."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.database.schema import init_db
from src.database.connection import get_db
from src.services.patient_service import register_or_get_patient, create_visit, get_visit_details
from src.services.doctor_service import (
    record_doctor_decision, save_doctor_notes, get_longitudinal_labs
)


class TestDoctorWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_hospital.db"
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_doctor_decisions(self):
        p, _ = register_or_get_patient("9555544444", "Meera Sen", db_path=self.db_path)
        v = create_visit(p["patient_id"], db_path=self.db_path)

        # Confirm a symptom
        record_doctor_decision(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            item_id="item_sym_1",
            part_type="symptom",
            decision="confirmed",
            db_path=self.db_path
        )

        # Correct a lab item
        record_doctor_decision(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            item_id="item_lab_1",
            part_type="lab",
            decision="corrected",
            corrected_value={"text": "14.0", "kind": "Lab result", "quote_ok": True},
            db_path=self.db_path
        )

        # Reject an item
        record_doctor_decision(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            item_id="item_sym_2",
            part_type="symptom",
            decision="rejected",
            db_path=self.db_path
        )

        details = get_visit_details(v["visit_id"], db_path=self.db_path)
        decisions = details["decisions"]
        self.assertEqual(len(decisions), 3)
        self.assertEqual(decisions["item_sym_1"]["decision"], "confirmed")
        self.assertEqual(decisions["item_lab_1"]["decision"], "corrected")
        self.assertEqual(decisions["item_lab_1"]["corrected_value"]["text"], "14.0")
        self.assertEqual(decisions["item_sym_2"]["decision"], "rejected")

    def test_doctor_consultation_notes_and_visit_completion(self):
        p, _ = register_or_get_patient("9444433333", "Rohan Verma", db_path=self.db_path)
        v = create_visit(p["patient_id"], db_path=self.db_path)
        self.assertEqual(v["status"], "waiting")

        save_doctor_notes(
            visit_id=v["visit_id"],
            patient_id=p["patient_id"],
            clinical_notes="Chest clear on auscultation. Normal heart sounds. Advised rest and fluids.",
            plan="Review in 1 week if cough persists.",
            doctor_id="DOC-DR-GUPTA",
            db_path=self.db_path
        )

        details = get_visit_details(v["visit_id"], db_path=self.db_path)
        self.assertEqual(details["status"], "completed")
        self.assertIsNotNone(details["doctor_notes"])
        self.assertIn("auscultation", details["doctor_notes"]["clinical_notes"])

    def test_longitudinal_lab_trends(self):
        p, _ = register_or_get_patient("9333322222", "Karan Singhania", db_path=self.db_path)
        v1 = create_visit(p["patient_id"], db_path=self.db_path)
        v2 = create_visit(p["patient_id"], db_path=self.db_path)

        with get_db(self.db_path) as conn:
            # Insert report records first for foreign key integrity
            conn.execute(
                """
                INSERT INTO reports (report_id, patient_id, visit_id, filename, file_type, file_hash, storage_path)
                VALUES ('R1', ?, ?, 'report1.pdf', 'pdf', 'hash1', '/tmp/r1.pdf'),
                       ('R2', ?, ?, 'report2.pdf', 'pdf', 'hash2', '/tmp/r2.pdf')
                """,
                (p["patient_id"], v1["visit_id"], p["patient_id"], v2["visit_id"])
            )
            # Insert lab records across the two visits into extracted_results
            conn.execute(
                """
                INSERT INTO extracted_results (extract_id, report_id, patient_id, visit_id, test_name, test_value, unit, reference_range, range_note)
                VALUES ('E1', 'R1', ?, ?, 'HbA1c', '8.4', '%', '4.0-5.6', 'outside listed range')
                """,
                (p["patient_id"], v1["visit_id"])
            )
            conn.execute(
                """
                INSERT INTO extracted_results (extract_id, report_id, patient_id, visit_id, test_name, test_value, unit, reference_range, range_note)
                VALUES ('E2', 'R2', ?, ?, 'HbA1c', '7.6', '%', '4.0-5.6', 'outside listed range')
                """,
                (p["patient_id"], v2["visit_id"])
            )

        trends = get_longitudinal_labs(p["patient_id"], db_path=self.db_path)
        self.assertIn("HbA1c", trends)
        self.assertEqual(len(trends["HbA1c"]), 2)
        self.assertEqual(trends["HbA1c"][0]["value"], "8.4")
        self.assertEqual(trends["HbA1c"][1]["value"], "7.6")


if __name__ == "__main__":
    unittest.main()
