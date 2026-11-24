"""SQLite schema definition, database initialization, and indexing."""
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "hospital.db"


def get_db_path():
    """Return the resolved path to the SQLite database file."""
    p = DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone);
CREATE INDEX IF NOT EXISTS idx_patients_pid ON patients(patient_id);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT UNIQUE NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    token_number TEXT NOT NULL,
    status TEXT DEFAULT 'waiting', -- 'waiting', 'in_consultation', 'completed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_visits_patient ON visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_visits_token ON visits(token_number);

CREATE TABLE IF NOT EXISTS vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT UNIQUE NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    bp_systolic INTEGER,
    bp_diastolic INTEGER,
    heart_rate INTEGER,
    temperature REAL,
    spo2 REAL,
    blood_sugar REAL,
    recorded_by TEXT DEFAULT 'nurse',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vitals_visit ON vitals(visit_id);

CREATE TABLE IF NOT EXISTS intakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intake_id TEXT UNIQUE NOT NULL,
    visit_id TEXT UNIQUE NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    reason_for_visit TEXT,
    symptoms_text TEXT,
    duration TEXT,
    severity TEXT,
    associated_symptoms TEXT,
    medical_conditions TEXT,
    current_medications TEXT,
    known_allergies TEXT,
    previous_history TEXT,
    submitted_by TEXT DEFAULT 'patient', -- 'patient' or 'nurse'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intakes_visit ON intakes(visit_id);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT UNIQUE NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    group_id TEXT, -- For grouping multi-page physical report photos
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'pdf', 'image'
    file_hash TEXT NOT NULL, -- SHA-256 for deduplication
    storage_path TEXT NOT NULL,
    page_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_hash_patient ON reports(patient_id, file_hash);

CREATE TABLE IF NOT EXISTS extracted_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extract_id TEXT UNIQUE NOT NULL,
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    test_name TEXT NOT NULL,
    test_value TEXT NOT NULL,
    unit TEXT,
    reference_range TEXT,
    range_note TEXT,
    page INTEGER DEFAULT 1,
    bbox_json TEXT,
    source_line TEXT,
    quote_ok INTEGER DEFAULT 1,
    extraction_method TEXT DEFAULT 'pdfplumber', -- 'pdfplumber' or 'ocr'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_extracted_patient ON extracted_results(patient_id, test_name);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id TEXT UNIQUE NOT NULL,
    visit_id TEXT UNIQUE NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    summary_json TEXT NOT NULL,
    model_mode TEXT DEFAULT 'structured_synthesis',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_visit ON summaries(visit_id);

CREATE TABLE IF NOT EXISTS doctor_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    part_type TEXT NOT NULL, -- 'symptom', 'lab', or 'medication'
    decision TEXT NOT NULL, -- 'confirmed', 'corrected', 'rejected'
    corrected_value_json TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(visit_id, item_id)
);

CREATE TABLE IF NOT EXISTS doctor_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT UNIQUE NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id TEXT DEFAULT 'DOC-01',
    clinical_notes TEXT NOT NULL,
    plan TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_doctor_notes_visit ON doctor_notes(visit_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_role TEXT NOT NULL, -- 'patient', 'nurse', 'doctor', 'system'
    actor_id TEXT,
    action TEXT NOT NULL,
    patient_id TEXT,
    visit_id TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS staff_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('doctor', 'nurse')),
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    staff_id TEXT NOT NULL REFERENCES staff_users(staff_id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staff_sessions_token ON staff_sessions(token_hash);

CREATE TABLE IF NOT EXISTS patient_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_sessions_token ON patient_sessions(token_hash);

CREATE TABLE IF NOT EXISTS nurse_queue_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT UNIQUE NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    recorded_by TEXT NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nurse_queue_completed_visit
    ON nurse_queue_completions(visit_id);

CREATE TABLE IF NOT EXISTS extracted_medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    med_id TEXT UNIQUE NOT NULL,
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    medicine_name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    timing TEXT,
    duration TEXT,
    route TEXT,
    instructions TEXT,
    medicine_type TEXT DEFAULT 'Not specified',
    strength TEXT DEFAULT 'Not specified',
    quantity TEXT DEFAULT 'Not specified',
    source_line TEXT,
    raw_text TEXT,
    confidence REAL DEFAULT 0.0,
    confidence_level TEXT DEFAULT 'medium',
    is_handwritten INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT 'unverified',
    verified_by TEXT,
    verified_at TIMESTAMP,
    corrected_data_json TEXT,
    page INTEGER DEFAULT 1,
    extraction_method TEXT DEFAULT 'ocr',
    source_region_json TEXT,
    field_confidences_json TEXT,
    original_ocr_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_extracted_meds_visit ON extracted_medications(visit_id);
CREATE INDEX IF NOT EXISTS idx_extracted_meds_patient ON extracted_medications(patient_id);

CREATE TABLE IF NOT EXISTS document_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT UNIQUE NOT NULL,
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    severity TEXT DEFAULT 'info',
    is_automated INTEGER DEFAULT 1,
    source_line TEXT,
    source_region_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_findings_visit ON document_findings(visit_id);
CREATE INDEX IF NOT EXISTS idx_doc_findings_patient ON document_findings(patient_id);
"""


def init_postgres():
    from src.database.postgres import Database, connect, settings
    from src.services.auth_service import seed_demo_staff

    with connect() as connection:
        db = Database(connection)
        db.lock(408011)
        db.execute("CREATE SCHEMA IF NOT EXISTS chakshu")
        db.execute("REVOKE ALL ON SCHEMA chakshu FROM PUBLIC")
        schema = SCHEMA_SQL.replace("PRAGMA foreign_keys = ON;", "")
        schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
        for statement in schema.split(";"):
            if statement.strip():
                db.execute(statement)
        db.execute("""
            CREATE TABLE IF NOT EXISTS report_files (
                report_id TEXT PRIMARY KEY REFERENCES reports(report_id) ON DELETE CASCADE,
                content BYTEA NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS namcs_archive (
                survey_id INTEGER PRIMARY KEY,
                record BYTEA NOT NULL
            )
        """)
        for definition in (
            "doc_type TEXT DEFAULT 'Medical Report'",
            "extraction_status TEXT DEFAULT 'Completed'",
            "findings_count INTEGER DEFAULT 0",
            "error_message TEXT",
        ):
            db.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS " + definition)
        # These fields are present in hospital databases from earlier Chakshu builds.
        for table, fields in {
            "reports": ("document_type", "extraction_message", "ocr_engine", "processed_at", "raw_text"),
            "extracted_results": ("abnormality_status", "interpretation"),
            "extracted_medications": ("medication_id", "strength"),
        }.items():
            for field in fields:
                db.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {field} TEXT")
        config = settings()
        passwords = (config.get("CHAKSHU_DOCTOR_PASSWORD"), config.get("CHAKSHU_NURSE_PASSWORD"))
        if all(passwords) and not any(password in {"Doctor123!", "Nurse123!"} for password in passwords):
            seed_demo_staff(db, passwords=passwords)

def init_db(db_path=None):
    """Initialize SQLite database schema and enable WAL mode for safe concurrency."""
    from src.database.postgres import database_url

    if db_path is None and database_url():
        return init_postgres()
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA_SQL)
    try:
        report_cols = [c[1] for c in conn.execute("PRAGMA table_info(reports)").fetchall()]
        if "doc_type" not in report_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN doc_type TEXT DEFAULT 'Medical Report'")
        if "extraction_status" not in report_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN extraction_status TEXT DEFAULT 'Completed'")
        if "findings_count" not in report_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN findings_count INTEGER DEFAULT 0")
        if "error_message" not in report_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN error_message TEXT")

        # Auto-migrate extracted_medications columns
        med_cols = [c[1] for c in conn.execute("PRAGMA table_info(extracted_medications)").fetchall()]
        if "confidence" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN confidence REAL DEFAULT 0.0")
        if "confidence_level" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN confidence_level TEXT DEFAULT 'medium'")
        if "is_handwritten" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN is_handwritten INTEGER DEFAULT 0")
        if "verification_status" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN verification_status TEXT DEFAULT 'unverified'")
        if "verified_by" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN verified_by TEXT")
        if "verified_at" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN verified_at TIMESTAMP")
        if "corrected_data_json" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN corrected_data_json TEXT")
        if "raw_text" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN raw_text TEXT")
        if "page" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN page INTEGER DEFAULT 1")
        if "medicine_type" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN medicine_type TEXT DEFAULT 'Not specified'")
        if "strength" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN strength TEXT DEFAULT 'Not specified'")
        if "quantity" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN quantity TEXT DEFAULT 'Not specified'")
        if "source_region_json" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN source_region_json TEXT")
        if "field_confidences_json" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN field_confidences_json TEXT")
        if "original_ocr_json" not in med_cols:
            conn.execute("ALTER TABLE extracted_medications ADD COLUMN original_ocr_json TEXT")

        finding_cols = [c[1] for c in conn.execute("PRAGMA table_info(document_findings)").fetchall()]
        if "source_region_json" not in finding_cols:
            conn.execute("ALTER TABLE document_findings ADD COLUMN source_region_json TEXT")
    except Exception:
        pass
    from src.services.auth_service import seed_demo_staff
    seed_demo_staff(conn)
    conn.commit()
    conn.close()
    return path
