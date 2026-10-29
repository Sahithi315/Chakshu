"""Tests for structured clinical summary generation, evidence linking, and gap detection."""
import unittest
from src.services.summary_service import generate_clinical_summary


class TestSummaryService(unittest.TestCase):
    def test_summary_structure_and_disclaimer(self):
        intake_data = {
            "reason_for_visit": "Persistent cough and fever",
            "symptoms_text": "cough for 5 days, fever on and off, no chest pain",
            "duration": "5 days",
            "severity": "Moderate",
            "associated_symptoms": "mild sore throat",
            "medical_conditions": "Hypertension",
            "current_medications": "Amlodipine 5mg",
            "known_allergies": "No known drug allergies",
            "previous_history": "Non-smoker"
        }
        vitals_data = {
            "bp_systolic": 138,
            "bp_diastolic": 88,
            "heart_rate": 84,
            "temperature": 100.8,
            "spo2": 97.5,
            "blood_sugar": 110.0
        }
        labs = [
            {"test": "WBC Count", "value": "12500", "unit": "/uL", "reference_range": "4000-11000",
             "range_note": "outside listed range", "page": 1, "quote_ok": True, "source_line": "WBC 12500 /uL HIGH"},
            {"test": "Hemoglobin", "value": "13.2", "unit": "g/dL", "reference_range": "12-15",
             "range_note": "", "page": 1, "quote_ok": True, "source_line": "Hemoglobin 13.2 g/dL NORMAL"}
        ]

        summary = generate_clinical_summary(intake_data, vitals_data, labs)

        # 1. Non-diagnostic disclaimer is present
        self.assertIn("disclaimer", summary)
        self.assertIn("Not for autonomous diagnosis", summary["disclaimer"])

        # 2. Patient reported evidence correctly stored
        self.assertEqual(summary["patient_reported"]["reason_for_visit"], "Persistent cough and fever")
        self.assertEqual(summary["patient_reported"]["duration"], "5 days")

        # 3. Nurse vitals review flags fever
        vitals_strings = " ".join(summary["nurse_vitals"])
        self.assertIn("Febrile", vitals_strings)

        # 4. Lab categorization: abnormal vs normal
        abnormal = summary["lab_evidence"]["abnormal_results"]
        self.assertEqual(len(abnormal), 1)
        self.assertEqual(abnormal[0]["test"], "WBC Count")

        normal = summary["lab_evidence"]["in_range_results"]
        self.assertEqual(len(normal), 1)
        self.assertEqual(normal[0]["test"], "Hemoglobin")

    def test_missing_information_gaps_flagged(self):
        # Empty intake data missing allergies and duration
        intake_data = {
            "reason_for_visit": "Knee pain",
            "symptoms_text": "pain in right knee",
            "duration": "",
            "known_allergies": "",
            "current_medications": ""
        }
        summary = generate_clinical_summary(intake_data)
        gaps = summary["information_gaps"]

        # Both missing allergy and duration should be flagged
        gaps_text = " ".join(gaps)
        self.assertIn("Allergy", gaps_text)
        self.assertIn("Duration", gaps_text)

    def test_longitudinal_summary_with_past_doctor_notes_and_problems(self):
        # Current visit (2nd visit)
        intake_data = {
            "reason_for_visit": "Follow up for bilateral foot tingling",
            "symptoms_text": "mild persistent tingling in toes",
            "duration": "2 months",
            "medical_conditions": "Type 2 Diabetes Mellitus",
            "current_medications": "Metformin 500mg BD",
            "known_allergies": "No known allergies"
        }
        past_visits = [
            {
                "visit_id": "VIS-001",
                "token_number": "T-098",
                "created_at": "2026-10-01 10:00:00",
                "intake": {
                    "reason_for_visit": "Initial complaint of foot numbness",
                    "duration": "3 weeks"
                },
                "doctor_notes": {
                    "clinical_notes": "Monofilament sensation decreased in lower extremities. Pulses palpable.",
                    "plan": "Early diabetic neuropathy. Continue Metformin 500mg BD. Add Atorvastatin 10mg."
                },
                "extracted_results": [
                    {"test_name": "HbA1c", "test_value": "8.8", "unit": "%"}
                ]
            }
        ]
        patient_info = {"name": "Aarav Nair", "age": 52, "patient_id": "SYN-P001"}

        summary = generate_clinical_summary(
            intake_data=intake_data,
            returning_history=past_visits,
            patient_info=patient_info
        )

        card = summary["single_card"]

        # 1. Header indicates 2nd visit
        self.assertIn("2nd visit", card["header"])
        self.assertIn("Aarav Nair", card["header"])

        # 2. SAME COMPLAINT BEFORE contains previous doctor notes and previous problem
        same_complaints = " ".join(card["same_complaint_before"])
        self.assertIn("Initial complaint of foot numbness", same_complaints)
        self.assertIn("Prior Doctor Exam:", same_complaints)
        self.assertIn("Monofilament sensation decreased", same_complaints)
        self.assertIn("Prior Doctor Advice & Rx:", same_complaints)
        self.assertIn("Early diabetic neuropathy", same_complaints)

        # 3. CONFIRM IN ROOM includes follow-up verification on prior doctor plan
        confirm_text = " ".join(card["confirm_in_room"])
        self.assertIn("adherence to previous advice", confirm_text.lower())
        self.assertIn("Early diabetic neuropathy", confirm_text)


if __name__ == "__main__":
    unittest.main()
