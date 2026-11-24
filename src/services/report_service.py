"""Medical report upload, validation, secure storage, and deduplication service."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import os
import re
import uuid
from src.database.connection import get_db
from src.services.patient_service import log_audit

ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = ROOT / "data" / "uploads"
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

MAGIC_SIGNATURES = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}


class ReportValidationError(ValueError):
    """Raised when an uploaded report fails validation checks."""
    pass


def validate_file(file_bytes, filename):
    """Validate file size, extension, and binary header magic bytes."""
    if not file_bytes:
        raise ReportValidationError("The uploaded file is empty (0 bytes).")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ReportValidationError(
            f"File exceeds the 15 MB size limit ({len(file_bytes) / (1024 * 1024):.1f} MB)."
        )

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ReportValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: PDF, JPG, JPEG, PNG."
        )

    signatures = MAGIC_SIGNATURES.get(ext, [])
    matches = any(file_bytes.startswith(sig) for sig in signatures)
    if not matches:
        raise ReportValidationError(
            f"File content does not match the expected format for '{ext}'. Please upload a valid document or image."
        )
    return ext


def sanitize_filename(filename):
    """Sanitize filename to prevent directory traversal or filesystem injection."""
    name = Path(filename).name
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
    return clean[:80] if clean else "document"


def store_and_register_report(file_bytes, filename, patient_id, visit_id, group_id=None, db_path=None, conn=None):
    """Validate, deduplicate, securely store on disk, and register report in the database."""
    ext = validate_file(file_bytes, filename)
    clean_name = sanitize_filename(filename)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_type = "pdf" if ext == ".pdf" else "image"

    def _do_store(c):
        existing = c.execute(
            """
            SELECT * FROM reports WHERE patient_id = ? AND file_hash = ?
            """,
            (patient_id, file_hash)
        ).fetchone()

        if existing:
            rep = dict(existing)
            log_audit(
                "patient", "report_reused", patient_id, visit_id=visit_id,
                details=f"Identical report already on file: {rep['filename']} (Hash: {file_hash[:8]})",
                conn=c
            )
            return rep, False

        cloud = getattr(c, "is_postgres", False)
        storage_path = ""
        if not cloud:
            target_path = UPLOAD_DIR / patient_id / f"{file_hash[:12]}_{clean_name}"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(file_bytes)
            storage_path = str(target_path)

        report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        logical_group = group_id or f"GRP-{uuid.uuid4().hex[:6].upper()}"

        page_count = 1
        if ext == ".pdf":
            try:
                import pdfplumber
                from io import BytesIO
                with pdfplumber.open(BytesIO(file_bytes)) as p:
                    page_count = len(p.pages)
            except Exception:
                page_count = 1

        c.execute(
            """
            INSERT INTO reports (report_id, patient_id, visit_id, group_id, filename, file_type, file_hash, storage_path, page_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (report_id, patient_id, visit_id, logical_group, clean_name, file_type, file_hash, storage_path, page_count)
        )

        if cloud:
            c.execute("INSERT INTO report_files (report_id, content) VALUES (?, ?)", (report_id, file_bytes))

        log_audit(
            "patient", "report_uploaded", patient_id, visit_id=visit_id,
            details=f"Uploaded {clean_name} ({file_type}, {len(file_bytes)} bytes)",
            conn=c
        )

        created = c.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        return dict(created), True

    if conn is not None:
        return _do_store(conn)
    else:
        with get_db(db_path) as c:
            return _do_store(c)


def get_reports_for_visit(visit_id, db_path=None):
    """Retrieve all reports associated with a specific visit."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE visit_id = ? ORDER BY created_at ASC",
            (visit_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_reports_for_patient(patient_id, db_path=None):
    """Retrieve all historical reports for a patient across all visits."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_report_by_id(report_id, db_path=None):
    """Retrieve report metadata by unique report identifier."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE report_id = ?",
            (report_id.strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_cloud_report_content(report_id, conn=None):
    with get_db(conn=conn) as db:
        if not getattr(db, "is_postgres", False):
            return None
        row = db.execute("SELECT content FROM report_files WHERE report_id = ?", (report_id,)).fetchone()
        return bytes(row["content"]) if row else None


@contextmanager
def report_processing_path(report, conn=None):
    if report["storage_path"]:
        yield Path(report["storage_path"])
        return

    content = get_cloud_report_content(report["report_id"], conn=conn)
    if content is None:
        raise FileNotFoundError("Report content is missing")
    with TemporaryDirectory() as directory:
        path = Path(directory) / sanitize_filename(report["filename"])
        path.write_bytes(content)
        yield path
