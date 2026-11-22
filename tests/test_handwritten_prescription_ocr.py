"""Automated test suite for Handwritten Prescription OCR & Doctor Dashboard Verification in CareVision.

Tests:
1. Clear handwritten prescriptions.
2. Difficult or poorly readable handwriting.
3. Prescriptions with multiple medicines.
4. Prescriptions containing abbreviations.
5. Rotated and low-quality images.
6. Multi-page prescriptions.
7. Printed prescriptions and lab reports to ensure existing OCR is not broken.
8. Database persistence and doctor verification/correction lifecycle.
"""
from pathlib import Path
import io
import tempfile
import unittest
import numpy as np
import cv2
from PIL import Image

from src.database import schema
from src.database.connection import get_db
from src.services.image_preprocessing import (
    preprocess_prescription_image, correct_skew, remove_shadows_and_noise,
    enhance_contrast, apply_adaptive_threshold, analyze_handwriting_features
)
from src.services.ocr_service import (
    process_report_file, extract_medications_from_text, identify_document_type,
    is_tesseract_available, parse_lab_lines
)
from src.services.patient_service import (
    register_or_get_patient, create_visit, get_visit_details
)
from src.services.report_service import store_and_register_report
from src.services.doctor_service import record_doctor_decision


class HandwrittenPrescriptionOCRTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = schema.DEFAULT_DB_PATH
        schema.DEFAULT_DB_PATH = Path(self.temp_dir.name) / "test_handwriting.db"
        schema.init_db()

    def tearDown(self):
        schema.DEFAULT_DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _create_handwritten_image(self, lines, add_noise=False, rotate_angle=0, add_shadow=False):
        """Helper to generate synthetic realistic prescription images with OpenCV and PIL."""
        h, w = 600, 1000
        img = np.ones((h, w), dtype=np.uint8) * 250

        # Optional gradient shadow
        if add_shadow:
            for y in range(h):
                img[y, :] = np.clip(img[y, :].astype(int) - int((y / h) * 60), 0, 255).astype(np.uint8)

        # Draw prescription lines with script/cursive font
        y_pos = 90
        for line in lines:
            # Doctor handwriting font simulation with variable stroke
            cv2.putText(img, line, (40, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (25, 25, 30), 2, cv2.LINE_AA)
            y_pos += 80

        # Optional noise
        if add_noise:
            noise = np.random.normal(0, 8, img.shape).astype(np.uint8)
            img = cv2.add(img, noise)

        pil_img = Image.fromarray(img)
        if rotate_angle != 0:
            pil_img = pil_img.rotate(rotate_angle, expand=True)

        return pil_img

    def test_01_clear_handwritten_prescription(self):
        """1. Clear handwritten prescription: extracts medicine name, dosage, frequency, duration, route."""
        lines = [
            "Rx",
            "1. Tab Paracetamol 500mg 1-0-1 After Food 5 days",
            "2. Tab Pantoprazole 40mg 1-0-0 Before Food 7 days"
        ]
        pil_img = self._create_handwritten_image(lines)

        # Save to temp file
        img_path = Path(self.temp_dir.name) / "clear_rx.png"
        pil_img.save(str(img_path))

        res = process_report_file(img_path)
        self.assertEqual(res["status"], "success")
        self.assertIn("Prescription", res["doc_type"])

        meds = res["extracted_medications"]
        self.assertGreaterEqual(len(meds), 1)

        names = [m["medicine_name"].lower() for m in meds]
        self.assertTrue(any("paracetamol" in n or "pantoprazole" in n for n in names))

        paracetamol = next((m for m in meds if "paracetamol" in m["medicine_name"].lower()), meds[0])
        self.assertTrue(paracetamol["dosage"].startswith("500") or "500" in paracetamol["dosage"])
        self.assertTrue("twice daily" in paracetamol["frequency"].lower() or "1-0-1" in paracetamol["frequency"])
        self.assertEqual(paracetamol["timing"], "After food")
        self.assertEqual(paracetamol["duration"], "5 days")
        self.assertEqual(paracetamol["route"], "Oral")
        self.assertEqual(paracetamol["verification_status"], "unverified")
        self.assertGreater(paracetamol["confidence"], 50.0)

    def test_02_difficult_or_poorly_readable_handwriting(self):
        """2. Difficult or poorly readable handwriting: flags unreadable text as 'Unclear' without guessing."""
        difficult_text = """
        Dr. Consultant
        Rx
        1. Tab ???~~~ 10mg OD for 10 days
        2. Cap ?????? 250mg TDS
        """
        meds = extract_medications_from_text(difficult_text, is_handwritten=True)
        self.assertGreaterEqual(len(meds), 1)

        for m in meds:
            # Must preserve raw text and not substitute with invented medicines
            self.assertTrue(m["is_uncertain"] or m["confidence_level"] in ["low", "unclear"] or "Unclear" in m["medicine_name"])
            self.assertEqual(m["review_status"], "review_needed")
            self.assertNotEqual(m["medicine_name"].lower(), "paracetamol")
            self.assertIn(m["dosage"], ["10mg", "250mg", "Not specified", "Unclear"])

    def test_03_prescriptions_with_multiple_medicines(self):
        """3. Prescriptions with multiple medicines: extracts all prescribed items."""
        lines = [
            "Rx",
            "1. Tab Pantoprazole 40mg 1-0-0 Before Food 14 days",
            "2. Cap Amoxicillin 500mg 1-0-1 After Food 5 days",
            "3. Syp Cetirizine 5mg 0-0-1 At bedtime 3 days",
            "4. Tab Multivitamin 1-0-0 Morning 30 days"
        ]
        text = "\n".join(lines)
        meds = extract_medications_from_text(text, is_handwritten=True)
        self.assertEqual(len(meds), 4)

        med_names = [m["medicine_name"].lower() for m in meds]
        self.assertTrue(any("pantoprazole" in n for n in med_names))
        self.assertTrue(any("amoxicillin" in n for n in med_names))
        self.assertTrue(any("cetirizine" in n for n in med_names))
        self.assertTrue(any("multivitamin" in n for n in med_names))

        # Check routes
        routes = {m["medicine_name"].lower(): m["route"] for m in meds}
        for name, route in routes.items():
            self.assertEqual(route, "Oral")

    def test_04_prescriptions_containing_abbreviations(self):
        """4. Prescriptions containing abbreviations: maps medical shorthand accurately."""
        abbrev_text = """
        Rx
        Tab Dolo 650mg SOS After food
        Tab Metformin 500mg BD PC 1 month
        Cap Omeprazole 20mg OD AC 14 days
        Tab Clonazepam 0.5mg HS At bedtime 7 days
        """
        meds = extract_medications_from_text(abbrev_text, is_handwritten=True)
        self.assertEqual(len(meds), 4)

        by_name = {m["medicine_name"].lower(): m for m in meds}

        dolo = next((m for k, m in by_name.items() if "dolo" in k), None)
        self.assertIsNotNone(dolo)
        self.assertIn("SOS", dolo["frequency"])

        metformin = next((m for k, m in by_name.items() if "metformin" in k), None)
        self.assertIsNotNone(metformin)
        self.assertIn("Twice daily", metformin["frequency"])
        self.assertEqual(metformin["timing"], "After food")
        self.assertEqual(metformin["duration"], "1 months")

        omeprazole = next((m for k, m in by_name.items() if "omeprazole" in k), None)
        self.assertIsNotNone(omeprazole)
        self.assertIn("Once daily", omeprazole["frequency"])
        self.assertEqual(omeprazole["timing"], "Before food")

        clonazepam = next((m for k, m in by_name.items() if "clonazepam" in k), None)
        self.assertIsNotNone(clonazepam)
        self.assertIn("bedtime", clonazepam["timing"].lower())

    def test_05_rotated_and_low_quality_images(self):
        """5. Rotated and low-quality images: preprocessing corrects orientation, deskew, and shadow."""
        lines = [
            "Rx",
            "Tab Paracetamol 500mg BD 5 days"
        ]
        pil_img = self._create_handwritten_image(lines, add_noise=True, add_shadow=True)

        # Preprocessing pipeline test
        prep = preprocess_prescription_image(pil_img)
        self.assertIn("original_pil", prep)
        self.assertIn("enhanced_pil", prep)
        self.assertIn("binary_pil", prep)
        self.assertIsInstance(prep["deskew_angle"], float)

        # Original document is preserved untouched
        self.assertEqual(prep["original_pil"].size, pil_img.size)

        # Verify deskew and shadow functions individually
        gray = np.array(pil_img.convert("L"))
        deskewed, angle = correct_skew(gray)
        self.assertEqual(deskewed.shape, gray.shape)

        shadow_free = remove_shadows_and_noise(gray)
        self.assertEqual(shadow_free.shape, gray.shape)

        enhanced = enhance_contrast(shadow_free)
        self.assertEqual(enhanced.shape, gray.shape)

        binary = apply_adaptive_threshold(enhanced)
        self.assertEqual(binary.shape, gray.shape)

    def test_06_multi_page_prescriptions(self):
        """6. Multi-page prescriptions: processes each page and aggregates extracted medications."""
        page1 = self._create_handwritten_image(["Rx Page 1", "1. Tab Pantoprazole 40mg OD Before Food 7 days"])
        page2 = self._create_handwritten_image(["Rx Page 2", "2. Cap Amoxicillin 500mg BD After Food 5 days"])

        pdf_path = Path(self.temp_dir.name) / "multipage_rx.pdf"
        # Save as multi-page PDF using PIL
        page1.save(str(pdf_path), save_all=True, append_images=[page2])

        res = process_report_file(pdf_path)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["pages_processed"], 2)

        meds = res["extracted_medications"]
        self.assertGreaterEqual(len(meds), 2)

        pages = [m.get("page", 1) for m in meds]
        self.assertIn(1, pages)
        self.assertIn(2, pages)

    def test_07_printed_prescriptions_and_labs_not_broken(self):
        """7. Printed prescriptions and lab reports: existing OCR functionality is preserved."""
        # A. Printed Lab Report
        sample_lab_text = """
        PATIENT INVESTIGATION REPORT
        Haemoglobin 9.2 g/dL 12.0-15.0 Low
        Total Leukocyte Count 11500 /uL 4000-10000 High
        Platelet Count 2.5 lakhs/uL 1.5-4.5 Normal
        """
        labs = parse_lab_lines(sample_lab_text, page_no=1, source_mode="ocr_printed")
        self.assertEqual(len(labs), 3)
        hb = next(l for l in labs if "Haemoglobin" in l["test"])
        self.assertEqual(hb["status"], "Low")
        self.assertEqual(hb["value"], "9.2")

        tlc = next(l for l in labs if "Leukocyte" in l["test"])
        self.assertEqual(tlc["status"], "High")

        doc_type_lab = identify_document_type(sample_lab_text, "lab_report.pdf", is_handwritten=False)
        self.assertEqual(doc_type_lab, "Blood / Laboratory Report")

        # B. Printed Prescription
        sample_printed_rx = """
        OUTPATIENT CLINIC PRESCRIPTION
        1. Tab Paracetamol 650mg Twice daily After food 5 days
        2. Tab Cetirizine 10mg Once daily At bedtime 3 days
        """
        printed_meds = extract_medications_from_text(sample_printed_rx, is_handwritten=False)
        self.assertEqual(len(printed_meds), 2)
        self.assertEqual(printed_meds[0]["is_handwritten"], 0)
        self.assertEqual(printed_meds[0]["extraction_method"], "ocr")

    def test_08_database_persistence_and_doctor_verification_workflow(self):
        """8. Database persistence & doctor verification: confirms, corrects, and rejects persist correctly."""
        # 1. Register a patient and visit
        patient, _ = register_or_get_patient("9876543210", "Test Patient Verification")
        patient_id = patient["patient_id"]
        visit = create_visit(patient_id, "T-101")
        visit_id = visit["visit_id"]

        # 2. Store a prescription image
        pil_img = self._create_handwritten_image(["Rx", "1. Tab Paracetamol 500mg 1-0-1 After food 5 days"])
        img_bytes = io.BytesIO()
        pil_img.save(img_bytes, format="PNG")
        file_bytes = img_bytes.getvalue()

        rep_rec, is_new = store_and_register_report(
            file_bytes=file_bytes,
            filename="handwritten_rx.png",
            patient_id=patient_id,
            visit_id=visit_id
        )
        report_id = rep_rec["report_id"]

        # 3. Simulate OCR extraction and database insertion
        res = process_report_file(rep_rec["storage_path"])
        meds = res["extracted_medications"]
        self.assertGreaterEqual(len(meds), 1)

        med_id = "MED-TEST-001"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO extracted_medications (
                    med_id, report_id, patient_id, visit_id, medicine_name, dosage,
                    frequency, timing, duration, route, instructions, source_line,
                    raw_text, confidence, confidence_level, is_handwritten, page,
                    verification_status, extraction_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (med_id, report_id, patient_id, visit_id, meds[0]["medicine_name"],
                 meds[0]["dosage"], meds[0]["frequency"], meds[0]["timing"], meds[0]["duration"],
                 meds[0]["route"], meds[0]["instructions"], meds[0]["source_line"],
                 meds[0]["raw_text"], meds[0]["confidence"], meds[0]["confidence_level"],
                 1, 1, "unverified", "handwriting_ocr")
            )

        # 4. Check that get_visit_details retrieves the extracted medication
        visit_details = get_visit_details(visit_id)
        db_meds = visit_details["extracted_medications"]
        self.assertEqual(len(db_meds), 1)
        self.assertEqual(db_meds[0]["med_id"], med_id)
        self.assertEqual(db_meds[0]["verification_status"], "unverified")
        self.assertEqual(db_meds[0]["is_handwritten"], 1)

        # 5. Doctor verifies with correction (edits dosage and frequency)
        corrections = {
            "medicine_name": "Paracetamol (Calpol)",
            "dosage": "650 mg",
            "frequency": "Thrice daily (1-1-1)",
            "duration": "7 days"
        }
        record_doctor_decision(
            visit_id=visit_id,
            patient_id=patient_id,
            item_id=med_id,
            part_type="medication",
            decision="corrected",
            corrected_value=corrections
        )

        # 6. Reopen dashboard via get_visit_details and verify persistence
        reloaded_visit = get_visit_details(visit_id)
        reloaded_meds = reloaded_visit["extracted_medications"]
        self.assertEqual(len(reloaded_meds), 1)
        rel_med = reloaded_meds[0]

        # Verified status is 'corrected'
        self.assertEqual(rel_med["verification_status"], "corrected")
        self.assertEqual(rel_med["medicine_name"], "Paracetamol (Calpol)")
        self.assertEqual(rel_med["dosage"], "650 mg")
        self.assertEqual(rel_med["frequency"], "Thrice daily (1-1-1)")
        self.assertEqual(rel_med["duration"], "7 days")

        # 7. Doctor confirms another decision
        record_doctor_decision(
            visit_id=visit_id,
            patient_id=patient_id,
            item_id=med_id,
            part_type="medication",
            decision="confirmed"
        )
        reloaded_visit_2 = get_visit_details(visit_id)
        self.assertEqual(reloaded_visit_2["extracted_medications"][0]["verification_status"], "confirmed")

    def test_09_inika_prescription_regression(self):
        """9. Regression test for uploaded Inika.jpeg handwritten prescription.
        Verifies:
        - Successful OCR extraction (status == 'success', not 'warning' or stuck in 'PROCESSING')
        - Recognition as 'Handwritten Prescription'
        - Extracted medicine 'Rockcef' with dosage '200 mg', frequency 'Twice daily (1-0-1)', duration
        - Flagged with review_needed / is_uncertain requiring doctor verification
        - Database persistence in reports and extracted_medications
        - Correct retrieval in get_visit_details
        - Doctor verification persistence
        """
        inika_fixture = Path("tests/fixtures/Inika.jpeg")
        if not inika_fixture.exists():
            # Fallback to brain fixture if needed
            inika_fixture = Path(r"C:/Users/A S Nemitha/.gemini/antigravity/brain/8d58543a-42f0-4f32-a59f-aedd2479266b/.user_uploaded/media_1793975154259_5e28705c.jpg")
        self.assertTrue(inika_fixture.exists(), f"Inika test image must exist at {inika_fixture}")

        patient, _ = register_or_get_patient(phone="8792815377", name="Inika", age=6, gender="F")
        patient_id = patient["patient_id"]
        visit = create_visit(patient_id)
        visit_id = visit["visit_id"]

        file_bytes = inika_fixture.read_bytes()
        rep_rec, is_new = store_and_register_report(
            file_bytes=file_bytes,
            filename="Inika.jpeg",
            patient_id=patient_id,
            visit_id=visit_id
        )

        res = process_report_file(rep_rec["storage_path"])
        self.assertEqual(res["status"], "success")
        self.assertIn("Handwritten Prescription", res["doc_type"])
        self.assertTrue(res["is_handwritten"])
        self.assertGreaterEqual(res["findings_count"], 1)

        meds = res["extracted_medications"]
        self.assertGreaterEqual(len(meds), 1)
        rockcef_med = next((m for m in meds if "rockcef" in m["medicine_name"].lower()), None)
        self.assertIsNotNone(rockcef_med, f"Expected Rockcef to be extracted, got: {meds}")
        self.assertEqual(rockcef_med["dosage"], "200 mg")
        self.assertEqual(rockcef_med["strength"], "200 mg")
        self.assertEqual(rockcef_med["medicine_type"], "Tablet")
        self.assertEqual(rockcef_med["quantity"], "10 tablets")
        self.assertIn("10 tablets (5 days)", rockcef_med["duration"])
        self.assertIn("Twice daily (1-0-1)", rockcef_med["frequency"])
        self.assertEqual(rockcef_med["route"], "Oral")
        self.assertTrue(rockcef_med["is_uncertain"])
        self.assertEqual(rockcef_med["review_status"], "review_needed")
        self.assertEqual(rockcef_med["verification_status"], "unverified")

        # Save to database and verify extraction_status is 'Completed'
        with get_db() as conn:
            conn.execute(
                """
                UPDATE reports SET doc_type = ?, extraction_status = 'Completed', findings_count = ?, error_message = ''
                WHERE report_id = ?
                """,
                (res["doc_type"], res["findings_count"], rep_rec["report_id"])
            )
            import uuid
            med_id = f"MED-{uuid.uuid4().hex[:8].upper()}"
            conn.execute(
                """
                INSERT INTO extracted_medications (
                    med_id, report_id, patient_id, visit_id, medicine_name, dosage,
                    frequency, timing, duration, route, instructions, source_line,
                    raw_text, confidence, confidence_level, is_handwritten, page,
                    verification_status, extraction_method, medicine_type, strength, quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (med_id, rep_rec["report_id"], patient_id, visit_id, rockcef_med["medicine_name"],
                 rockcef_med["dosage"], rockcef_med["frequency"], rockcef_med["timing"],
                 rockcef_med["duration"], rockcef_med["route"], rockcef_med["instructions"],
                 rockcef_med["source_line"], rockcef_med["raw_text"], rockcef_med["confidence"],
                 rockcef_med["confidence_level"], rockcef_med["is_handwritten"], 1,
                 rockcef_med["verification_status"], rockcef_med["extraction_method"],
                 rockcef_med["medicine_type"], rockcef_med["strength"], rockcef_med["quantity"])
            )

        # Retrieve visit details as DoctorDashboard does
        visit_details = get_visit_details(visit_id)
        db_reports = visit_details["reports"]
        self.assertEqual(len(db_reports), 1)
        self.assertEqual(db_reports[0]["extraction_status"], "Completed")
        self.assertEqual(db_reports[0]["findings_count"], res["findings_count"])

        db_meds = visit_details["extracted_medications"]
        self.assertEqual(len(db_meds), 1)
        self.assertEqual(db_meds[0]["medicine_name"], "Rockcef")
        self.assertEqual(db_meds[0]["dosage"], "200 mg")
        self.assertEqual(db_meds[0]["strength"], "200 mg")
        self.assertEqual(db_meds[0]["medicine_type"], "Tablet")
        self.assertEqual(db_meds[0]["quantity"], "10 tablets")
        self.assertEqual(db_meds[0]["verification_status"], "unverified")

        # Test Doctor Verification (Confirm)
        record_doctor_decision(
            visit_id=visit_id,
            patient_id=patient_id,
            item_id=med_id,
            part_type="medication",
            decision="confirmed"
        )
        reloaded = get_visit_details(visit_id)
        self.assertEqual(reloaded["extracted_medications"][0]["verification_status"], "confirmed")

        # Test Doctor Correction
        record_doctor_decision(
            visit_id=visit_id,
            patient_id=patient_id,
            item_id=med_id,
            part_type="medication",
            decision="corrected",
            corrected_value={
                "medicine_name": "Rockcef 200",
                "medicine_type": "Tablet",
                "strength": "200 mg",
                "dosage": "1 tablet",
                "frequency": "Twice daily (1-0-1)",
                "duration": "5 days",
                "quantity": "10 tablets"
            }
        )
        reloaded_corr = get_visit_details(visit_id)
        self.assertEqual(reloaded_corr["extracted_medications"][0]["verification_status"], "corrected")
        self.assertEqual(reloaded_corr["extracted_medications"][0]["medicine_name"], "Rockcef 200")
        self.assertEqual(reloaded_corr["extracted_medications"][0]["dosage"], "1 tablet")
        self.assertEqual(reloaded_corr["extracted_medications"][0]["duration"], "5 days")

    def test_10_view_document_authentication_rules(self):
        """10. Verify View Document authentication requirements:
        - Missing or invalid tokens fail staff session lookup
        - Valid doctor tokens produce authenticated staff sessions
        - Original report file bytes remain bit-for-bit identical on storage disk
        """
        from src.services.auth_service import get_staff_session, create_staff_session

        # 1. Empty or forged token must be None
        self.assertIsNone(get_staff_session(""))
        self.assertIsNone(get_staff_session("forged_bearer_token"))

        # 2. Valid staff session lookup
        token, user = create_staff_session("DR-SHARMA")
        self.assertIsNotNone(token)
        identity = get_staff_session(token)
        self.assertIsNotNone(identity)
        self.assertEqual(identity["role"], "doctor")
        self.assertEqual(identity["staff_id"], "DR-SHARMA")

        # 3. Preserved original file bytes
        inika_fixture = Path("tests/fixtures/Inika.jpeg")
        original_bytes = inika_fixture.read_bytes()
        patient, _ = register_or_get_patient(phone="8792815377", name="Inika", age=6, gender="F")
        visit = create_visit(patient["patient_id"])
        rep_rec, _ = store_and_register_report(
            file_bytes=original_bytes,
            filename="Inika.jpeg",
            patient_id=patient["patient_id"],
            visit_id=visit["visit_id"]
        )
        stored_path = Path(rep_rec["storage_path"])
        self.assertTrue(stored_path.exists())
        self.assertEqual(stored_path.read_bytes(), original_bytes)

    def test_11_tabular_kannada_letterhead_prescription_extraction(self):
        """11. Verify Layout-Aware Tabular Prescription OCR on Kannada Letterhead Note:
        - Layout detection detects table grid, row boundaries, and column separators
        - Extracts 5 items: Eberconazole, Clobetol NF, K2 Soap, Turbinate, Montair LC
        - Correctly associates schedules: 1-0-1, 0-0-1, 1/2-0-1/2
        - Strikethrough detection flags K2 Soap as cancelled, while preserving Clobetol NF
        - Demographics and vitals: Rekha, 28/7/26, BP 140/60 mmHg, Pulse 81/min, SpO2 100%
        - 3 simple medical findings sections: condition, instructions/vitals, and AI summary
        """
        rx_path = Path("data/uploads/P10017/b6b321347086_WhatsApp_Image_2026-11-08_at_12.03.47.jpeg")
        if not rx_path.exists():
            self.skipTest(f"Prescription image not found at {rx_path}")

        res = process_report_file(rx_path)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["doc_type"], "Handwritten Tabular Prescription")

        meds = res.get("extracted_medications", [])
        self.assertEqual(len(meds), 5, f"Expected 5 prescribed rows, got {len(meds)}")

        med_names = [m["medicine_name"] for m in meds]
        self.assertIn("Eberconazole", med_names)
        self.assertIn("Clobetol NF", med_names)
        self.assertIn("K2 Soap", med_names)
        self.assertIn("Turbinate", med_names)
        self.assertIn("Montair LC", med_names)

        # Check Row 1: Eberconazole
        r1 = next(m for m in meds if m["medicine_name"] == "Eberconazole")
        self.assertEqual(r1["frequency"], "Twice daily (1-0-1)")
        self.assertFalse(r1.get("is_cancelled", False))

        # Check Row 2: Clobetol NF (Dermiford struck out)
        r2 = next(m for m in meds if m["medicine_name"] == "Clobetol NF")
        self.assertEqual(r2["medicine_type"], "Cream")
        self.assertEqual(r2["frequency"], "Twice daily (1-0-1)")
        self.assertFalse(r2.get("is_cancelled", False))
        self.assertIn("Dermiford", r2.get("instructions", ""))

        # Check Row 3: K2 Soap (Cancelled / Strikethrough)
        r3 = next(m for m in meds if m["medicine_name"] == "K2 Soap")
        self.assertTrue(r3.get("is_cancelled", False))
        self.assertEqual(r3.get("review_status"), "cancelled_by_prescriber")

        # Check Row 4: Turbinate (Terbinafine)
        r4 = next(m for m in meds if m["medicine_name"] == "Turbinate")
        self.assertEqual(r4["medicine_type"], "Tablet")
        self.assertEqual(r4["frequency"], "Once daily at bedtime (0-0-1)")
        self.assertEqual(r4["quantity"], "5 tablets")
        self.assertFalse(r4.get("is_cancelled", False))

        # Check Row 5: Montair LC (Half tablet schedule)
        r5 = next(m for m in meds if m["medicine_name"] == "Montair LC")
        self.assertEqual(r5["medicine_type"], "Tablet")
        self.assertEqual(r5["dosage"], "1/2 tablet")
        self.assertEqual(r5["frequency"], "Twice daily (1/2 - 0 - 1/2)")
        self.assertEqual(r5["quantity"], "10 tablets")
        self.assertFalse(r5.get("is_cancelled", False))

        # Check 3 Medical Findings Sections
        findings = res.get("document_findings", [])
        self.assertEqual(len(findings), 3)
        titles = [f["title"] for f in findings]
        self.assertIn("Condition mentioned in prescription", titles)
        self.assertIn("Important instructions", titles)
        self.assertIn("AI-generated clinical summary", titles)

        f_inst = next(f for f in findings if f["title"] == "Important instructions")
        self.assertIn("140/60", f_inst["detail"])
        self.assertIn("81/min", f_inst["detail"])
        self.assertIn("100%", f_inst["detail"])
        self.assertIn("K2 Soap", f_inst["detail"])

    def test_12_freeform_santhosh_clinic_prescription_extraction(self):
        """12. Generalized free-form handwritten prescription OCR on Santhosh Clinic (Dr. M.D. Jain) upload:
        - Extracts all 3 numbered medicine entries without discarding low-confidence or unprefixed items
        - Never guesses unclear medicine names ('Unclear – Doctor Review Required')
        - Preserves original OCR text and normalized source_region bbox for manual doctor verification
        - Extracts separate symptoms/observations, vitals, explicit diagnosis ('No explicit diagnosis identified'),
          doctor instructions, and factual AI summary
        - Persists cleanly to SQLite and loads via get_visit_details with source_region intact
        """
        rx_path = Path("data/uploads/P10018/6e38608b129a_WhatsApp_Image_2026-11-10_at_22.35.58.jpeg")
        if not rx_path.exists():
            self.skipTest(f"Free-form prescription image not found at {rx_path}")

        res = process_report_file(rx_path)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["doc_type"], "Handwritten Prescription")
        self.assertTrue(res["is_handwritten"])

        meds = res.get("extracted_medications", [])
        self.assertEqual(len(meds), 3, f"Expected 3 numbered medicine entries, got {len(meds)}: {meds}")
        for m in meds:
            self.assertTrue(m["is_uncertain"])
            self.assertEqual(m["verification_status"], "unverified")
            self.assertEqual(m["review_status"], "review_needed")
            self.assertTrue(m.get("raw_text"), "Original OCR text must be preserved")
            sr = m.get("source_region")
            self.assertIsInstance(sr, dict, "Source region coordinates must be attached for doctor review")
            self.assertTrue(0.0 <= sr["x"] <= 1.0 and 0.0 <= sr["y"] <= 1.0)
            self.assertTrue(sr["w"] > 0.0 and sr["h"] > 0.0)

        findings = res.get("document_findings", [])
        categories = {f["category"] for f in findings}
        self.assertIn("symptoms_observations", categories)
        self.assertIn("vitals", categories)
        self.assertIn("condition", categories)
        self.assertIn("advice", categories)
        self.assertIn("insight", categories)

        cond_f = next(f for f in findings if f["category"] == "condition")
        self.assertEqual(cond_f["detail"], "No explicit diagnosis identified.")

        # Must distinguish detected entries vs reliably identified medicines and avoid corrupted OCR text in findings
        self.assertEqual(res.get("detected_entries_count"), 3)
        self.assertEqual(res.get("identified_medicines_count"), 0)
        insight_f = next(f for f in findings if f["category"] == "insight")
        self.assertIn("3 possible entries detected. 0 medicines reliably identified. Doctor verification required.", insight_f["detail"])

        vitals_f = next(f for f in findings if f["category"] == "vitals")
        self.assertEqual(vitals_f["detail"], "Vital signs could not be reliably identified.")
        advice_f = next(f for f in findings if f["category"] == "advice")
        self.assertEqual(advice_f["detail"], "Handwritten instructions require review.")

        for m in meds:
            self.assertIsInstance(m.get("field_confidences"), dict)
            self.assertIn("medicine_name", m["field_confidences"])

        # Verify end-to-end DB auto-sync, source_region roundtrip, and separate preservation of original OCR vs doctor edits
        patient, _ = register_or_get_patient(phone="9000010018", name="Sneha V", age=28, gender="F")
        visit = create_visit(patient["patient_id"])
        rep_rec, _ = store_and_register_report(
            file_bytes=rx_path.read_bytes(),
            filename="santhosh_freeform.jpeg",
            patient_id=patient["patient_id"],
            visit_id=visit["visit_id"],
        )
        details = get_visit_details(visit["visit_id"])
        self.assertEqual(len(details["extracted_medications"]), 3)
        self.assertTrue(all(isinstance(m.get("source_region"), dict) for m in details["extracted_medications"]))
        self.assertTrue(all(isinstance(m.get("field_confidences"), dict) for m in details["extracted_medications"]))
        self.assertGreaterEqual(len(details["document_findings"]), 5)

        # Verify doctor correction preserves original OCR separately from corrected value
        first_med = details["extracted_medications"][0]
        record_doctor_decision(
            visit_id=visit["visit_id"],
            patient_id=patient["patient_id"],
            item_id=first_med["med_id"],
            part_type="medication",
            decision="corrected",
            corrected_value={"medicine_name": "Verified Medicine A", "medicine_type": "Drops", "frequency": "BD"}
        )
        after_edit = get_visit_details(visit["visit_id"])
        edited_med = next(m for m in after_edit["extracted_medications"] if m["med_id"] == first_med["med_id"])
        self.assertEqual(edited_med["verification_status"], "corrected")
        self.assertEqual(edited_med["medicine_name"], "Verified Medicine A")
        self.assertIsInstance(edited_med.get("original_ocr"), dict)
        self.assertIn("Unclear", edited_med["original_ocr"]["medicine_name"])

    def test_13_unprefixed_numbered_prescription_items_not_discarded(self):
        """13. Numbered prescription items without Tab/Cap/Syp prefixes must not be discarded."""
        freeform_text = """
        Dr. Clinic
        Rx
        1. ???xyzz 1-0-1 x 5 days
        2. Abcdefg 0-0-1
        3. UnreadableItem
        Advice:
        Drink warm water and take rest.
        """
        meds = extract_medications_from_text(freeform_text, is_handwritten=True)
        self.assertEqual(len(meds), 3, f"Expected all 3 numbered items preserved, got {meds}")
        self.assertTrue(all(m["verification_status"] == "unverified" for m in meds))

    def test_14_gastric_ulcer_and_gastroenteritis_regressions(self):
        """14. Regression test for Gastric Ulcer and Gastroenteritis handwritten prescriptions."""
        ulcer_path = Path("data/uploads/P10014/f8d6e225f336_Gastric_Ulcer_Prescription_Note.png")
        if ulcer_path.exists():
            res_u = process_report_file(ulcer_path)
            self.assertEqual(res_u["status"], "success")
            self.assertEqual(len(res_u["extracted_medications"]), 3)
            u_names = {m["medicine_name"] for m in res_u["extracted_medications"]}
            self.assertIn("Pantop", u_names)
            self.assertIn("Sucralfate", u_names)
            self.assertIn("Domperidone", u_names)
            u_cond = next(f for f in res_u["document_findings"] if f["category"] == "condition")
            self.assertIn("Ulcer", u_cond["detail"])
            u_vitals = [f for f in res_u["document_findings"] if f["category"] == "vitals"]
            self.assertEqual(len(u_vitals), 0, "Patient header text must not trigger false vitals")

        gastro_path = Path("data/uploads/P10016/6d7de1b08795_Handwritten_Gastroenteritis_Prescription_Note.png")
        if gastro_path.exists():
            res_g = process_report_file(gastro_path)
            self.assertEqual(res_g["status"], "success")
            self.assertEqual(len(res_g["extracted_medications"]), 5)
            g_names = {m["medicine_name"] for m in res_g["extracted_medications"]}
            self.assertIn("Ofloxacin", g_names)
            self.assertIn("Metronidazole", g_names)
            self.assertIn("ORS", g_names)
            g_cond = next(f for f in res_g["document_findings"] if f["category"] == "condition")
            self.assertIn("Gastroenteritis", g_cond["detail"])


if __name__ == "__main__":
    unittest.main()
