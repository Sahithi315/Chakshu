"""Comprehensive automated tests for document OCR, medicine extraction,
Widal & CBC laboratory investigations, and database persistence.
"""
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from src.database.schema import init_db
from src.services.patient_service import (
    register_or_get_patient, create_visit, get_visit_details, get_patient_history
)
from src.services.report_service import (
    store_and_register_report, get_reports_for_visit, get_reports_for_patient,
    get_report_by_id
)
from src.services.ocr_service import (
    process_report_file, parse_lab_lines, extract_medications_from_text,
    identify_document_type, is_tesseract_available
)

ROOT = Path(__file__).resolve().parent.parent


class TestDocumentIntelligence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_hospital.db"
        init_db(self.db_path)

        # Register patient Mohan (30 yrs, Male)
        self.patient, _ = register_or_get_patient(
            phone="9876543299",
            name="Mohan",
            age=30,
            gender="Male",
            db_path=self.db_path
        )
        self.visit = create_visit(self.patient["patient_id"], db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mohan_widal_and_cbc_extraction(self):
        """Verify dynamic extraction of Mohan's typhoid-related Widal test and CBC report."""
        report_file = ROOT / "data" / "sample_mohan_widal_lab_report.pdf"
        self.assertTrue(report_file.exists(), "Sample Mohan report file must exist")

        # Process report through document pipeline
        res = process_report_file(str(report_file))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["doc_type"], "Widal / Serology Report")

        rows = res["extracted_rows"]
        by_test = {r["test"]: r for r in rows}

        # 1. Widal Test S. typhi O
        self.assertIn("Widal Test - S. typhi O", by_test)
        self.assertEqual(by_test["Widal Test - S. typhi O"]["value"], "1:320")
        self.assertEqual(by_test["Widal Test - S. typhi O"]["status"], "High")

        # 2. Widal Test S. typhi H
        self.assertIn("Widal Test - S. typhi H", by_test)
        self.assertEqual(by_test["Widal Test - S. typhi H"]["value"], "1:160")
        self.assertEqual(by_test["Widal Test - S. typhi H"]["status"], "High")

        # 3. S. paratyphi A
        self.assertIn("S. paratyphi A", by_test)
        self.assertEqual(by_test["S. paratyphi A"]["value"], "1:80")
        self.assertEqual(by_test["S. paratyphi A"]["status"], "Normal")

        # 4. S. paratyphi B
        self.assertIn("S. paratyphi B", by_test)
        self.assertEqual(by_test["S. paratyphi B"]["value"], "1:80")
        self.assertEqual(by_test["S. paratyphi B"]["status"], "Normal")

        # 5. Hemoglobin
        self.assertIn("Hemoglobin", by_test)
        self.assertEqual(by_test["Hemoglobin"]["value"], "10.2")
        self.assertEqual(by_test["Hemoglobin"]["status"], "Low")

        # 6. TLC
        self.assertIn("Total Leukocyte Count (TLC)", by_test)
        self.assertIn(by_test["Total Leukocyte Count (TLC)"]["value"], ["12,000", "12000"])
        self.assertEqual(by_test["Total Leukocyte Count (TLC)"]["status"], "High")

        # 7. Platelet count
        self.assertIn("Platelet Count", by_test)
        self.assertIn(by_test["Platelet Count"]["value"], ["2,50,000", "250000"])
        self.assertEqual(by_test["Platelet Count"]["status"], "Normal")

        # 8. CRP
        self.assertIn("C-Reactive Protein (CRP)", by_test)
        self.assertEqual(by_test["C-Reactive Protein (CRP)"]["value"], "24.0")
        self.assertEqual(by_test["C-Reactive Protein (CRP)"]["status"], "High")

        # 9. ESR
        self.assertIn("Erythrocyte Sedimentation Rate (ESR)", by_test)
        self.assertEqual(by_test["Erythrocyte Sedimentation Rate (ESR)"]["value"], "35")
        self.assertEqual(by_test["Erythrocyte Sedimentation Rate (ESR)"]["status"], "High")

    def test_prescription_medicine_extraction(self):
        """Verify extraction of medicine name, dosage, frequency, timing, duration, route, instructions."""
        rx_text = """
        OPD PRESCRIPTION
        Patient: Mohan (30 Y / Male)
        Dr. A. Verma, MBBS MD

        Rx:
        1. Paracetamol 650 mg - twice daily after food x 5 days
        2. Pantoprazole 40 mg - once daily before food x 7 days
        3. Vitamin B12 - once daily for 1 month
        4. Ketoconazole Shampoo 2% - apply twice weekly on scalp for 4 weeks
        5. Amoxicillin 500mg - 1-0-1 after food x 5 days
        """
        meds = extract_medications_from_text(rx_text)
        self.assertEqual(len(meds), 5)

        by_name = {m["medicine_name"]: m for m in meds}

        # Paracetamol 650 mg
        self.assertIn("Paracetamol", by_name)
        self.assertEqual(by_name["Paracetamol"]["dosage"], "650 mg")
        self.assertEqual(by_name["Paracetamol"]["frequency"], "Twice daily")
        self.assertEqual(by_name["Paracetamol"]["timing"], "After food")
        self.assertEqual(by_name["Paracetamol"]["duration"], "5 days")

        # Pantoprazole 40 mg
        self.assertIn("Pantoprazole", by_name)
        self.assertEqual(by_name["Pantoprazole"]["dosage"], "40 mg")
        self.assertEqual(by_name["Pantoprazole"]["frequency"], "Once daily")
        self.assertEqual(by_name["Pantoprazole"]["timing"], "Before food")
        self.assertEqual(by_name["Pantoprazole"]["duration"], "7 days")

        # Vitamin B12
        self.assertIn("Vitamin B12", by_name)
        self.assertEqual(by_name["Vitamin B12"]["dosage"], "Not specified")
        self.assertEqual(by_name["Vitamin B12"]["frequency"], "Once daily")
        self.assertEqual(by_name["Vitamin B12"]["timing"], "Not specified")
        self.assertEqual(by_name["Vitamin B12"]["duration"], "1 months")

        # Ketoconazole Shampoo 2%
        self.assertIn("Ketoconazole Shampoo", by_name)
        self.assertEqual(by_name["Ketoconazole Shampoo"]["dosage"], "2%")
        self.assertEqual(by_name["Ketoconazole Shampoo"]["frequency"], "Twice weekly")
        self.assertEqual(by_name["Ketoconazole Shampoo"]["route"], "Topical / Shampoo")

        # Amoxicillin 500mg
        self.assertIn("Amoxicillin", by_name)
        self.assertEqual(by_name["Amoxicillin"]["dosage"], "500mg")
        self.assertIn("Twice daily", by_name["Amoxicillin"]["frequency"])
        self.assertEqual(by_name["Amoxicillin"]["timing"], "After food")

    def test_database_persistence_and_dashboard_retrieval(self):
        """Verify upload, persistence in database, and retrieval via get_visit_details."""
        report_file = ROOT / "data" / "sample_mohan_widal_lab_report.pdf"
        file_bytes = report_file.read_bytes()

        # Store and register report for Mohan
        rep, is_new = store_and_register_report(
            file_bytes=file_bytes,
            filename="mohan_widal_cbc_report.pdf",
            patient_id=self.patient["patient_id"],
            visit_id=self.visit["visit_id"],
            db_path=self.db_path
        )
        self.assertTrue(is_new)

        # Retrieve visit details (triggers auto-sync if not pre-populated)
        visit_details = get_visit_details(self.visit["visit_id"], db_path=self.db_path)

        # Check reports
        self.assertEqual(len(visit_details["reports"]), 1)
        r0 = visit_details["reports"][0]
        self.assertEqual(r0["filename"], "mohan_widal_cbc_report.pdf")
        self.assertEqual(r0["doc_type"], "Widal / Serology Report")
        self.assertIn("/api/reports/", r0["download_url"])

        # Check extracted results
        labs = visit_details["extracted_results"]
        self.assertGreaterEqual(len(labs), 7)
        lab_tests = {l["test_name"] for l in labs}
        self.assertIn("Widal Test - S. typhi O", lab_tests)
        self.assertIn("Hemoglobin", lab_tests)

        # Source document attached to each lab row
        for l in labs:
            self.assertEqual(l["source_document"], "mohan_widal_cbc_report.pdf")

        # Check findings
        findings = visit_details.get("document_findings", [])
        self.assertGreater(len(findings), 0)

        # Refresh / reopen visit from scratch (new DB query)
        refreshed = get_visit_details(self.visit["visit_id"], db_path=self.db_path)
        self.assertEqual(len(refreshed["extracted_results"]), len(labs))
        self.assertEqual(len(refreshed["reports"]), 1)

    def test_multiple_documents_for_same_patient(self):
        """Verify multiple documents (lab report + prescription) can be uploaded and associated."""
        pdf_path = ROOT / "data" / "sample_mohan_widal_lab_report.pdf"
        png_path = ROOT / "data" / "sample_mohan_widal_lab_report.png"

        rep1, _ = store_and_register_report(
            file_bytes=pdf_path.read_bytes(),
            filename="lab_investigations.pdf",
            patient_id=self.patient["patient_id"],
            visit_id=self.visit["visit_id"],
            db_path=self.db_path
        )

        rep2, _ = store_and_register_report(
            file_bytes=png_path.read_bytes(),
            filename="lab_investigations_photo.png",
            patient_id=self.patient["patient_id"],
            visit_id=self.visit["visit_id"],
            db_path=self.db_path
        )

        visit_reports = get_reports_for_visit(self.visit["visit_id"], db_path=self.db_path)
        self.assertEqual(len(visit_reports), 2)
        filenames = {r["filename"] for r in visit_reports}
        self.assertIn("lab_investigations.pdf", filenames)
        self.assertIn("lab_investigations_photo.png", filenames)

    def test_prescription_document_upload_and_extraction(self):
        """Verify uploading an OPD prescription file extracts medications and persists them in DB."""
        rx_path = ROOT / "data" / "sample_mohan_prescription.pdf"
        self.assertTrue(rx_path.exists(), "Sample Mohan prescription PDF must exist")

        rep, is_new = store_and_register_report(
            file_bytes=rx_path.read_bytes(),
            filename="mohan_opd_prescription.pdf",
            patient_id=self.patient["patient_id"],
            visit_id=self.visit["visit_id"],
            db_path=self.db_path
        )
        self.assertTrue(is_new)

        details = get_visit_details(self.visit["visit_id"], db_path=self.db_path)
        rep_synced = next(r for r in details["reports"] if r["report_id"] == rep["report_id"])
        self.assertEqual(rep_synced["doc_type"], "Prescription")
        self.assertIn(rep_synced["extraction_status"], ["Completed", "Success"])
        extracted_meds = details.get("extracted_medications", [])
        self.assertGreaterEqual(len(extracted_meds), 4)

        med_names = {m["medicine_name"] for m in extracted_meds}
        self.assertIn("Cefixime", med_names)
        self.assertIn("Paracetamol", med_names)
        self.assertIn("Pantoprazole", med_names)

        cefixime = next(m for m in extracted_meds if m["medicine_name"] == "Cefixime")
        self.assertEqual(cefixime["dosage"], "200 mg")
        self.assertIn("Twice daily", cefixime["frequency"])
        self.assertEqual(cefixime["timing"], "After food")
        self.assertEqual(cefixime["duration"], "7 days")


if __name__ == "__main__":
    unittest.main()
