"""Tests for camera and physical report upload, multi-page grouping, magic byte validation, and storage."""
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from src.database.schema import init_db
from src.services.patient_service import register_or_get_patient, create_visit
from src.services.report_service import (
    store_and_register_report, get_reports_for_visit, get_reports_for_patient,
    ReportValidationError, validate_file
)
from src.services.ocr_service import process_report_file, is_tesseract_available


class TestCameraAndReportUploadPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_reports.db"
        init_db(self.db_path)

        # Create synthetic patient and visit
        p, _ = register_or_get_patient("9876500099", "Mohan Rao", age=50, gender="Male", db_path=self.db_path)
        self.patient_id = p["patient_id"]
        v = create_visit(self.patient_id, db_path=self.db_path)
        self.visit_id = v["visit_id"]

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_synthetic_image_bytes(self, text="Hemoglobin 13.5 g/dL 12.0-16.0 Normal", format="JPEG"):
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((30, 80), text, fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format=format)
        return buf.getvalue()

    def test_magic_byte_validation_and_rejections(self):
        # Valid JPEG
        jpg_bytes = self._generate_synthetic_image_bytes(format="JPEG")
        self.assertEqual(validate_file(jpg_bytes, "page1.jpg"), ".jpg")
        self.assertEqual(validate_file(jpg_bytes, "page1.jpeg"), ".jpeg")

        # Valid PNG
        png_bytes = self._generate_synthetic_image_bytes(format="PNG")
        self.assertEqual(validate_file(png_bytes, "page1.png"), ".png")

        # Valid PDF signature
        pdf_bytes = b"%PDF-1.4 header bytes..."
        self.assertEqual(validate_file(pdf_bytes, "report.pdf"), ".pdf")

        # Reject spoofed extension (e.g. text file renamed to .jpg)
        fake_jpg = b"This is plain text with a jpg extension"
        with self.assertRaises(ReportValidationError):
            validate_file(fake_jpg, "fake.jpg")

        # Reject unsupported extension
        with self.assertRaises(ReportValidationError):
            validate_file(b"some content", "notes.docx")

        # Reject empty file
        with self.assertRaises(ReportValidationError):
            validate_file(b"", "empty.jpg")

    def test_multi_page_camera_scans_grouping(self):
        # Simulate patient taking photo of Page 1
        page1_bytes = self._generate_synthetic_image_bytes("HbA1c 6.8 % 4.0-5.6 High", format="JPEG")
        group_id = "GRP-CAM-2026-TEST"

        rep1, is_new1 = store_and_register_report(
            file_bytes=page1_bytes,
            filename="paper_report_page_1.jpg",
            patient_id=self.patient_id,
            visit_id=self.visit_id,
            group_id=group_id,
            db_path=self.db_path
        )
        self.assertTrue(is_new1)
        self.assertEqual(rep1["group_id"], group_id)
        self.assertEqual(rep1["file_type"], "image")
        self.assertTrue(Path(rep1["storage_path"]).exists())

        # Simulate patient taking photo of Page 2 (different content, same group_id)
        page2_bytes = self._generate_synthetic_image_bytes("Fasting Blood Sugar 145 mg/dL 70-100 High", format="JPEG")
        rep2, is_new2 = store_and_register_report(
            file_bytes=page2_bytes,
            filename="paper_report_page_2.jpg",
            patient_id=self.patient_id,
            visit_id=self.visit_id,
            group_id=group_id,
            db_path=self.db_path
        )
        self.assertTrue(is_new2)
        self.assertNotEqual(rep1["report_id"], rep2["report_id"])
        self.assertEqual(rep2["group_id"], group_id)

        # Verify visit reports retrieval contains both pages under the same visit
        visit_reports = get_reports_for_visit(self.visit_id, db_path=self.db_path)
        self.assertEqual(len(visit_reports), 2)
        r_ids = {r["report_id"] for r in visit_reports}
        self.assertIn(rep1["report_id"], r_ids)
        self.assertIn(rep2["report_id"], r_ids)

        # Verify report deduplication: uploading duplicate page 1 returns existing record
        rep1_dup, is_new_dup = store_and_register_report(
            file_bytes=page1_bytes,
            filename="paper_report_page_1.jpg",
            patient_id=self.patient_id,
            visit_id=self.visit_id,
            group_id=group_id,
            db_path=self.db_path
        )
        self.assertFalse(is_new_dup)
        self.assertEqual(rep1_dup["report_id"], rep1["report_id"])

    def test_image_report_processing_and_graceful_ocr(self):
        page_bytes = self._generate_synthetic_image_bytes(format="JPEG")
        rep, _ = store_and_register_report(
            file_bytes=page_bytes,
            filename="test_scan.jpg",
            patient_id=self.patient_id,
            visit_id=self.visit_id,
            db_path=self.db_path
        )
        # Process the stored image file
        result = process_report_file(rep["storage_path"])
        self.assertIn("status", result)
        self.assertIn(result["status"], ["success", "warning"])
        self.assertIn("extracted_rows", result)
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
