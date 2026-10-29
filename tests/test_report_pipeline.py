"""Tests for medical report upload, validation, secure storage, deduplication, and OCR parsing."""
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from src.database.schema import init_db
from src.services.report_service import (
    validate_file, sanitize_filename, store_and_register_report,
    ReportValidationError, MAX_FILE_SIZE_BYTES
)
from src.services.ocr_service import parse_lab_lines, process_report_file
from src.services.patient_service import register_or_get_patient, create_visit

ROOT = Path(__file__).resolve().parent.parent


class TestReportPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_hospital.db"
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_validation_valid_formats(self):
        # Valid PDF header
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        ext = validate_file(pdf_bytes, "report.pdf")
        self.assertEqual(ext, ".pdf")

        # Valid PNG header
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        ext = validate_file(png_bytes, "scan.png")
        self.assertEqual(ext, ".png")

        # Valid JPEG header
        jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        ext = validate_file(jpg_bytes, "photo.jpg")
        self.assertEqual(ext, ".jpg")

    def test_file_validation_rejections(self):
        # Empty file
        with self.assertRaises(ReportValidationError):
            validate_file(b"", "empty.pdf")

        # Exceeds max file size
        large_bytes = b"%PDF-" + b"0" * (MAX_FILE_SIZE_BYTES + 10)
        with self.assertRaises(ReportValidationError):
            validate_file(large_bytes, "oversized.pdf")

        # Unsupported extension
        with self.assertRaises(ReportValidationError):
            validate_file(b"%PDF-1.4 test", "malicious.exe")

        # Disguised file (wrong magic bytes)
        with self.assertRaises(ReportValidationError):
            validate_file(b"This is just plain text", "fake.pdf")

    def test_filename_sanitization_and_path_traversal(self):
        # Path traversal attempts
        self.assertEqual(sanitize_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(sanitize_filename("..\\..\\windows\\system32.jpg"), "system32.jpg")
        # Special characters
        clean = sanitize_filename("my report (1) #final&bad!.pdf")
        self.assertNotIn(" ", clean)
        self.assertNotIn("#", clean)
        self.assertNotIn("&", clean)

    def test_report_deduplication(self):
        p, _ = register_or_get_patient("9888877777", "Deepak Joshi", db_path=self.db_path)
        v = create_visit(p["patient_id"], db_path=self.db_path)

        pdf_bytes = b"%PDF-1.4\nSynthetic test file for deduplication\n%%EOF"
        rep1, is_new1 = store_and_register_report(
            file_bytes=pdf_bytes,
            filename="lab_test.pdf",
            patient_id=p["patient_id"],
            visit_id=v["visit_id"],
            db_path=self.db_path
        )
        self.assertTrue(is_new1)
        self.assertEqual(rep1["patient_id"], p["patient_id"])

        # Upload exact same file again for the same patient
        rep2, is_new2 = store_and_register_report(
            file_bytes=pdf_bytes,
            filename="lab_test_copy.pdf",
            patient_id=p["patient_id"],
            visit_id=v["visit_id"],
            db_path=self.db_path
        )
        self.assertFalse(is_new2)  # Reused existing report!
        self.assertEqual(rep1["report_id"], rep2["report_id"])
        self.assertEqual(rep1["file_hash"], rep2["file_hash"])

    def test_parse_lab_lines_regex(self):
        sample_ocr_text = """
        NIVARA DIAGNOSTIC LABS
        Patient Name: Aarav Nair   Date: 2026-10-20
        Hemoglobin 13.5 g/dL 12.0 - 15.5 NORMAL
        Fasting Blood Sugar 142 mg/dL 70 - 100 HIGH
        HbA1c 7.8 % 4.0 - 5.6 HIGH
        Creatinine 0.9 mg/dL 0.6 - 1.2 IN_RANGE
        Doctor Signature: Dr. Sen
        """
        rows = parse_lab_lines(sample_ocr_text, page_no=1)
        self.assertEqual(len(rows), 4)

        by_test = {r["test"]: r for r in rows}
        self.assertIn("Hemoglobin", by_test)
        self.assertEqual(by_test["Hemoglobin"]["value"], "13.5")
        self.assertEqual(by_test["Hemoglobin"]["unit"], "g/dL")
        self.assertEqual(by_test["Hemoglobin"]["range_note"], "")

        self.assertIn("Fasting Blood Sugar", by_test)
        self.assertEqual(by_test["Fasting Blood Sugar"]["value"], "142")
        self.assertEqual(by_test["Fasting Blood Sugar"]["range_note"], "outside listed range")

        self.assertIn("HbA1c", by_test)
        self.assertEqual(by_test["HbA1c"]["value"], "7.8")
        self.assertEqual(by_test["HbA1c"]["range_note"], "outside listed range")

    def test_process_existing_synthetic_pdf(self):
        pdf_path = ROOT / "data" / "synthetic_lab_reports" / "synthetic_report_001.pdf"
        if pdf_path.exists():
            res = process_report_file(str(pdf_path))
            self.assertEqual(res["status"], "success")
            self.assertGreater(len(res["extracted_rows"]), 0)
            first_row = res["extracted_rows"][0]
            self.assertIn("test", first_row)
            self.assertIn("value", first_row)
            self.assertIn("unit", first_row)


if __name__ == "__main__":
    unittest.main()
