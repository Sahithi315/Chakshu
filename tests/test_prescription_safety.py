import unittest
from src.services.prescription_safety_service import check_prescription_safety


class TestPrescriptionSafety(unittest.TestCase):
    def test_incomplete_and_duplicate_medicines_are_flagged(self):
        result = check_prescription_safety([
            {"name": "Metformin", "strength": "500 mg", "dose": "1 tablet", "frequency": "twice daily", "duration": "30 days"},
            {"name": "Metformin", "strength": "", "dose": "1 tablet", "frequency": "", "duration": "30 days"}
        ])
        types = {issue["type"] for issue in result["issues"]}
        self.assertIn("duplicate", types)
        self.assertIn("incomplete", types)

    def test_allergy_and_supported_interaction_are_flagged(self):
        result = check_prescription_safety([
            {"name": "Amoxicillin", "strength": "500 mg", "dose": "1 capsule", "frequency": "three times daily", "duration": "5 days"},
            {"name": "Warfarin", "strength": "2 mg", "dose": "1 tablet", "frequency": "daily", "duration": "30 days"},
            {"name": "Aspirin", "strength": "75 mg", "dose": "1 tablet", "frequency": "daily", "duration": "30 days"}
        ], allergies="Penicillin allergy")
        types = {issue["type"] for issue in result["issues"]}
        self.assertIn("allergy", types)
        self.assertIn("interaction", types)

    def test_clear_result_retains_coverage_warning(self):
        result = check_prescription_safety([
            {"name": "Paracetamol", "strength": "500 mg", "dose": "1 tablet", "frequency": "as directed", "duration": "2 days"}
        ], allergies="No known allergies")
        self.assertEqual(result["status"], "no_issues_found")
        self.assertEqual(result["issues"], [])
        self.assertIn("not proof", result["coverage_note"])


if __name__ == "__main__":
    unittest.main()
