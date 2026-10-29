"""Authenticated patient -> nurse -> doctor -> records lifecycle."""
from pathlib import Path
import tempfile
import unittest

from starlette.testclient import TestClient

from src.database import schema
from src.database.connection import get_db


class AuthenticatedLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = schema.DEFAULT_DB_PATH
        schema.DEFAULT_DB_PATH = Path(self.temp_dir.name) / "lifecycle.db"
        schema.init_db()

        from app.server import app
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        schema.DEFAULT_DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def login(self, username, password):
        response = self.client.post(
            "/api/auth/staff/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    @staticmethod
    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    def test_patient_nurse_doctor_records_lifecycle_with_rbac(self):
        self.assertEqual(self.client.get("/api/visits").status_code, 401)

        registration = self.client.post(
            "/api/patients/register",
            json={
                "name": "Synthetic Lifecycle Patient",
                "phone": "9000004321",
                "age": 38,
                "gender": "Female",
            },
        )
        self.assertEqual(registration.status_code, 200, registration.text)
        registered = registration.json()
        patient_id = registered["patient"]["patient_id"]
        visit_id = registered["visit"]["visit_id"]
        patient_token = registered["patient_token"]

        intake_payload = {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "reason_for_visit": "Synthetic follow-up",
            "symptoms_text": "Mild headache for two days",
            "duration": "1 to 3 days",
            "severity": "Mild (manageable)",
        }
        self.assertEqual(self.client.post("/api/intake", json=intake_payload).status_code, 401)
        intake = self.client.post(
            "/api/intake", json=intake_payload, headers=self.auth(patient_token)
        )
        self.assertEqual(intake.status_code, 200, intake.text)

        nurse_token = self.login("nurse.demo", "Nurse123!")
        doctor_token = self.login("doctor.demo", "Doctor123!")
        self.assertEqual(self.client.get("/api/visits", headers=self.auth(nurse_token)).status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/patients/{patient_id}/records", headers=self.auth(nurse_token)).status_code,
            403,
        )

        vitals_payload = {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "bp_systolic": 122,
            "bp_diastolic": 78,
            "heart_rate": 72,
            "temperature": 98.4,
            "spo2": 99,
            "blood_sugar": 105,
            "recorded_by": "SPOOFED-ID",
        }
        self.assertEqual(
            self.client.post("/api/vitals", json=vitals_payload, headers=self.auth(doctor_token)).status_code,
            403,
        )
        vitals = self.client.post("/api/vitals", json=vitals_payload, headers=self.auth(nurse_token))
        self.assertEqual(vitals.status_code, 200, vitals.text)
        remaining_triage = self.client.get(
            "/api/visits?needs_vitals=1", headers=self.auth(nurse_token)
        )
        self.assertEqual(remaining_triage.status_code, 200, remaining_triage.text)
        self.assertNotIn(visit_id, [visit["visit_id"] for visit in remaining_triage.json()])
        doctor_queue = self.client.get("/api/visits", headers=self.auth(doctor_token))
        self.assertIn(visit_id, [visit["visit_id"] for visit in doctor_queue.json()])

        notes = self.client.post(
            "/api/doctor/notes",
            json={
                "patient_id": patient_id,
                "visit_id": visit_id,
                "clinical_notes": "Synthetic examination completed.",
                "plan": "Synthetic documentation plan only.",
                "doctor_id": "SPOOFED-ID",
            },
            headers=self.auth(doctor_token),
        )
        self.assertEqual(notes.status_code, 200, notes.text)

        doctor_queue_after_completion = self.client.get("/api/visits", headers=self.auth(doctor_token))
        self.assertEqual(doctor_queue_after_completion.status_code, 200)
        self.assertNotIn(visit_id, [visit["visit_id"] for visit in doctor_queue_after_completion.json()])

        records = self.client.get(
            f"/api/patients/{patient_id}/records", headers=self.auth(doctor_token)
        )
        self.assertEqual(records.status_code, 200, records.text)
        self.assertEqual(records.json()["visits"][0]["status"], "completed")

        with get_db() as conn:
            vital_row = conn.execute("SELECT recorded_by FROM vitals WHERE visit_id = ?", (visit_id,)).fetchone()
            note_row = conn.execute("SELECT doctor_id FROM doctor_notes WHERE visit_id = ?", (visit_id,)).fetchone()
        self.assertEqual(vital_row["recorded_by"], "NURSE-ANITA")
        self.assertEqual(note_row["doctor_id"], "DR-SHARMA")


if __name__ == "__main__":
    unittest.main()
