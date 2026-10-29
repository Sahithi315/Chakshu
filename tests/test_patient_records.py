"""Tests for Patient Records / Medical History tab: search, chronological timeline, report archives, and data isolation."""
import tempfile
import unittest
from pathlib import Path

from src.database.schema import init_db
from src.database.connection import get_db
from src.services.patient_service import (
    register_or_get_patient, create_visit, record_vitals, save_intake,
    get_patient_complete_timeline, find_patient_by_id
)
from src.services.doctor_service import save_doctor_notes
from src.services.report_service import store_and_register_report, get_report_by_id


class TestPatientRecordsService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_records.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_chronological_visit_timeline(self):
        # 1. Register patient
        p, _ = register_or_get_patient("9888877771", "Devendra Sharma", age=56, gender="Male", db_path=self.db_path)
        pid = p["patient_id"]

        # Visit 1
        v1 = create_visit(pid, db_path=self.db_path)
        save_intake(
            visit_id=v1["visit_id"],
            patient_id=pid,
            reason_for_visit="First visit: severe knee pain",
            symptoms_text="Bilateral knee stiffness, worse in mornings",
            duration="3 weeks",
            severity="Moderate",
            conditions="Osteoarthritis",
            medications="Paracetamol 650mg SOS",
            allergies="Penicillin",
            db_path=self.db_path
        )
        record_vitals(
            visit_id=v1["visit_id"],
            patient_id=pid,
            bp_systolic=132,
            bp_diastolic=84,
            heart_rate=76,
            temperature=98.4,
            spo2=98.0,
            blood_sugar=110.0,
            db_path=self.db_path
        )
        save_doctor_notes(
            visit_id=v1["visit_id"],
            patient_id=pid,
            clinical_notes="Crepitus noted in right knee on flexion. Joint space narrowing suspected.",
            plan="Prescribed Aceclofenac 100mg BD. Order bilateral knee X-Ray AP/lateral. Follow up in 1 month.",
            doctor_id="DR-SHARMA",
            db_path=self.db_path
        )

        # Upload a report for Visit 1
        rep1, _ = store_and_register_report(
            file_bytes=b"%PDF-1.4 knee xray report",
            filename="knee_xray_report.pdf",
            patient_id=pid,
            visit_id=v1["visit_id"],
            db_path=self.db_path
        )

        # Visit 2 (subsequent visit)
        v2 = create_visit(pid, allow_duplicate_today=True, db_path=self.db_path)
        save_intake(
            visit_id=v2["visit_id"],
            patient_id=pid,
            reason_for_visit="Knee X-Ray review & follow-up",
            symptoms_text="Pain slightly reduced with medicines",
            duration="1 month",
            severity="Mild",
            conditions="Osteoarthritis",
            medications="Aceclofenac 100mg BD",
            allergies="Penicillin",
            db_path=self.db_path
        )
        save_doctor_notes(
            visit_id=v2["visit_id"],
            patient_id=pid,
            clinical_notes="Review of X-Ray: Grade 2 OA right knee. Left knee normal.",
            plan="Physiotherapy referral for quadriceps strengthening. Continue PRN analgesia.",
            doctor_id="DR-SHARMA",
            db_path=self.db_path
        )

        # Retrieve complete timeline
        timeline = get_patient_complete_timeline(pid, db_path=self.db_path)
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline["patient"]["patient_id"], pid)
        self.assertEqual(timeline["visits_count"], 2)
        self.assertIn("Osteoarthritis", timeline["chronic_conditions"])
        self.assertIn("Penicillin", timeline["known_allergies"])

        # Chronological order: newest visit first (Visit 2 then Visit 1)
        visits = timeline["visits"]
        self.assertEqual(len(visits), 2)
        self.assertEqual(visits[0]["visit_id"], v2["visit_id"], "Newest visit must appear first")
        self.assertEqual(visits[1]["visit_id"], v1["visit_id"])

        # Check visit-level isolation
        self.assertEqual(visits[0]["intake"]["reason_for_visit"], "Knee X-Ray review & follow-up")
        self.assertEqual(visits[1]["intake"]["reason_for_visit"], "First visit: severe knee pain")
        self.assertEqual(len(visits[1]["reports"]), 1)
        self.assertEqual(len(visits[0]["reports"]), 0)

        # Check all_reports archive
        self.assertEqual(len(timeline["all_reports"]), 1)
        self.assertEqual(timeline["all_reports"][0]["report_id"], rep1["report_id"])
        self.assertEqual(timeline["all_reports"][0]["filename"], "knee_xray_report.pdf")

    def test_unknown_patient_records_returns_none(self):
        res = get_patient_complete_timeline("NON_EXISTENT_MRN", db_path=self.db_path)
        self.assertIsNone(res)

    def test_report_lookup_by_id(self):
        p, _ = register_or_get_patient("9888877772", "Ananya Roy", age=32, gender="Female", db_path=self.db_path)
        v = create_visit(p["patient_id"], db_path=self.db_path)
        rep, _ = store_and_register_report(
            file_bytes=b"%PDF-1.4 thyroid panel",
            filename="thyroid_panel.pdf",
            patient_id=p["patient_id"],
            visit_id=v["visit_id"],
            db_path=self.db_path
        )

        found = get_report_by_id(rep["report_id"], db_path=self.db_path)
        self.assertIsNotNone(found)
        self.assertEqual(found["filename"], "thyroid_panel.pdf")
        self.assertEqual(found["patient_id"], p["patient_id"])

        missing = get_report_by_id("REP-NONEXISTENT", db_path=self.db_path)
        self.assertIsNone(missing)

    def test_retrieve_records_using_legacy_id_with_dashes_and_encoding(self):
        """Regression test: Ensure legacy IDs like PAT-2026-2123D6 are retrievable across all dash/encoding variants."""
        # Insert a legacy patient into DB directly
        from src.database.connection import get_db
        legacy_id = "PAT-2026-2123D6"
        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO patients (patient_id, phone, name, age, gender)
                VALUES (?, ?, ?, ?, ?)
                """,
                (legacy_id, "9876541111", "Sunitha", 22, "Female")
            )
        v1 = create_visit(legacy_id, db_path=self.db_path)
        save_intake(
            visit_id=v1["visit_id"],
            patient_id=legacy_id,
            reason_for_visit="Cold and cough",
            symptoms_text="Sore throat",
            duration="2 days",
            medications="Paracetamol and Otrivin",
            allergies="None declared",
            db_path=self.db_path
        )
        save_doctor_notes(
            visit_id=v1["visit_id"],
            patient_id=legacy_id,
            clinical_notes="Clear chest, mild pharyngitis",
            plan="Otrivin spray and rest for 3 days",
            doctor_id="DR-SHARMA",
            db_path=self.db_path
        )

        # Test variants
        test_variants = [
            legacy_id,                     # Exact: PAT-2026-2123D6
            legacy_id.lower(),             # Lowercase: pat-2026-2123d6
            "PAT-2026\u20132123D6",        # En-dash: PAT-2026–2123D6
            "PAT-2026\u20142123D6",        # Em-dash: PAT-2026—2123D6
            "PAT-2026%E2%80%932123D6",     # URL-encoded en-dash
            "  PAT-2026-2123D6  ",         # Leading/trailing whitespace
            "PAT20262123D6",               # Missing hyphens
        ]

        for variant in test_variants:
            timeline = get_patient_complete_timeline(variant, db_path=self.db_path)
            self.assertIsNotNone(timeline, f"Failed to retrieve timeline for variant: {variant}")
            self.assertEqual(timeline["patient"]["patient_id"], legacy_id, "Must resolve to canonical database ID")
            self.assertEqual(timeline["patient"]["name"], "Sunitha")
            self.assertEqual(timeline["visits_count"], 1)
            self.assertEqual(timeline["visits"][0]["doctor_notes"]["plan"], "Otrivin spray and rest for 3 days")

    def test_retrieve_records_using_short_mrn_variants(self):
        """Ensure short MRN format (e.g. P10001) resolves cleanly."""
        p, _ = register_or_get_patient("9911223344", "Rajesh Sharma", age=45, gender="Male", db_path=self.db_path)
        pid = p["patient_id"]
        self.assertTrue(pid.startswith("P"))

        v = create_visit(pid, db_path=self.db_path)
        save_intake(visit_id=v["visit_id"], patient_id=pid, reason_for_visit="Routine checkup", symptoms_text="None", db_path=self.db_path)

        for variant in [pid, pid.lower(), f"  {pid}  ", f"P-{pid[1:]}"]:
            timeline = get_patient_complete_timeline(variant, db_path=self.db_path)
            self.assertIsNotNone(timeline, f"Failed to retrieve for short MRN variant: {variant}")
            self.assertEqual(timeline["patient"]["patient_id"], pid)
            self.assertEqual(timeline["visits_count"], 1)

    def test_unknown_and_invalid_identifiers_return_none(self):
        """Ensure non-existent or empty IDs return None safely without raising exceptions."""
        for invalid in ["UNKNOWN-ID", "PAT-2099-000000", "P99999", "", "   ", None]:
            res = get_patient_complete_timeline(invalid, db_path=self.db_path)
            self.assertIsNone(res, f"Expected None for invalid ID: {invalid}")

    def test_quoted_and_punctuated_patient_id_variants(self):
        """Ensure IDs enclosed in quotes or punctuation resolve cleanly to canonical database records."""
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO patients (patient_id, phone, name, age, gender) VALUES (?, ?, ?, ?, ?)",
                ("PAT-2026-15C778", "7586985869", "Teju", 24, "Female")
            )
        v = create_visit("PAT-2026-15C778", db_path=self.db_path)
        save_intake(
            visit_id=v["visit_id"],
            patient_id="PAT-2026-15C778",
            reason_for_visit="Burning of eyes",
            symptoms_text="Severe watering",
            db_path=self.db_path
        )

        test_variants = [
            '"PAT-2026-15C778"',
            "'PAT-2026-15C778'",
            "\"PAT-2026-15C778\"",
            "`PAT-2026-15C778`",
            "[PAT-2026-15C778]",
            "PAT-2026-15C778.",
            "PAT-2026-15C778,",
            "  \"PAT-2026-15C778\"  ",
        ]
        for variant in test_variants:
            timeline = get_patient_complete_timeline(variant, db_path=self.db_path)
            self.assertIsNotNone(timeline, f"Failed for quoted variant: {variant}")
            self.assertEqual(timeline["patient"]["patient_id"], "PAT-2026-15C778")
            self.assertEqual(timeline["patient"]["name"], "Teju")

    def test_route_order_precedence_in_server(self):
        """Ensure sub-resources and static action endpoints precede generic parameter routes in server.py."""
        from app.server import routes
        from starlette.routing import Match

        # Test 1: /api/patients/PAT-2026-15C778/records matches get_patient_records_endpoint
        scope_records = {"type": "http", "method": "GET", "path": "/api/patients/PAT-2026-15C778/records"}
        first_match = None
        for r in routes:
            m, child = r.matches(scope_records)
            if m == Match.FULL:
                first_match = r
                break
        self.assertIsNotNone(first_match)
        self.assertEqual(first_match.name, "get_patient_records_endpoint")

        # Test 2: POST /api/patients/register matches register_patient_endpoint, not generic param
        scope_register = {"type": "http", "method": "POST", "path": "/api/patients/register"}
        first_match_post = None
        for r in routes:
            m, child = r.matches(scope_register)
            if m == Match.FULL:
                first_match_post = r
                break
        self.assertIsNotNone(first_match_post)
        self.assertEqual(first_match_post.name, "register_patient_endpoint")

    def test_existing_target_patient_in_active_hospital_db(self):
        """Directly verify that real patient PAT-2026-15C778 in data/hospital.db has full longitudinal records."""
        active_db = Path(__file__).resolve().parent.parent / "data" / "hospital.db"
        if not active_db.exists():
            return

        timeline = get_patient_complete_timeline("PAT-2026-15C778", db_path=active_db)
        if timeline is None:
            self.skipTest("Optional legacy patient is not present in the active local database")
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline["patient"]["name"], "Teju")
        self.assertEqual(timeline["patient"]["age"], 24)
        self.assertGreaterEqual(timeline["visits_count"], 1)

        latest_visit = timeline["visits"][0]
        self.assertEqual(latest_visit["intake"]["reason_for_visit"], "Burning of eyes")
        self.assertIn("Vision is clear", latest_visit["doctor_notes"]["clinical_notes"])
        self.assertIsNotNone(latest_visit["summary"])


if __name__ == "__main__":
    unittest.main()
