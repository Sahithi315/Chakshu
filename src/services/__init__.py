"""Services package for patient management, reports, OCR, summary generation, and doctor reviews."""
from .patient_service import (
    register_or_get_patient, find_patient_by_phone, find_patient_by_id,
    create_visit, get_active_visits, get_visit_details, get_patient_history,
    record_vitals, save_intake, log_audit
)
from .report_service import (
    validate_file, sanitize_filename, store_and_register_report,
    get_reports_for_visit, get_reports_for_patient, ReportValidationError
)
from .ocr_service import (
    is_tesseract_available, preprocess_image, ocr_image,
    parse_lab_lines, process_report_file
)
from .summary_service import generate_clinical_summary, save_summary
from .doctor_service import (
    record_doctor_decision, save_doctor_notes, get_longitudinal_labs
)

__all__ = [
    "register_or_get_patient", "find_patient_by_phone", "find_patient_by_id",
    "create_visit", "get_active_visits", "get_visit_details", "get_patient_history",
    "record_vitals", "save_intake", "log_audit",
    "validate_file", "sanitize_filename", "store_and_register_report",
    "get_reports_for_visit", "get_reports_for_patient", "ReportValidationError",
    "is_tesseract_available", "preprocess_image", "ocr_image",
    "parse_lab_lines", "process_report_file",
    "generate_clinical_summary", "save_summary",
    "record_doctor_decision", "save_doctor_notes", "get_longitudinal_labs"
]
