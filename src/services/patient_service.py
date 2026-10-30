"""Patient and visit management service with token assignment and vitals recording."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from src.database.connection import get_db


class PatientNameConflictError(ValueError):
    """Raised when a phone number is registered under a different patient name."""
    def __init__(self, message, existing_patient):
        super().__init__(message)
        self.existing_patient = existing_patient


def normalize_phone(phone: str) -> str:
    """Normalize phone number to 10 standard digits by stripping country codes and special chars."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    # Handle Indian country code prefix +91 or 91 (12 digits)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    # Handle leading zero prefix (11 digits)
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def normalize_name(name: str) -> str:
    """Clean and normalize patient name for robust matching across visits."""
    if not name:
        return ""
    clean = name.strip().lower()
    # Strip common salutations/honorifics
    clean = re.sub(r"^(mr\.|mrs\.|ms\.|dr\.|master\s+|shri\s+|smt\s+|prof\.)\s*", "", clean)
    clean = re.sub(r"^(mr|mrs|ms|dr)\s+", "", clean)
    # Remove non-word characters
    clean = re.sub(r"[^\w\s]", " ", clean)
    # Collapse multiple whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def names_are_consistent(name1: str, name2: str) -> bool:
    """Determine whether two names refer to the same individual (case, title, subset, order invariant)."""
    s1 = normalize_name(name1)
    s2 = normalize_name(name2)
    if not s1 or not s2:
        return False
    if s1 == s2:
        return True
    
    words1 = set(s1.split())
    words2 = set(s2.split())
    # Exact word set match (e.g. "Patel Ramesh" vs "Ramesh Patel")
    if words1 == words2:
        return True
    # Subset match (e.g. "Ramesh" vs "Ramesh Patel", or "Ramesh Kumar Patel")
    if words1 and words2 and (words1.issubset(words2) or words2.issubset(words1)):
        return True
    # Substring match if length is sufficiently specific
    if len(s1) >= 4 and len(s2) >= 4 and (s1 in s2 or s2 in s1):
        return True
    return False


def generate_patient_id(conn=None, db_path=None):
    """Generate a short, memorable, human-readable patient identifier (e.g. P10482).
    Allocates sequentially after the highest existing P-series ID in the database.
    Concurrency-safe and falls back to safe retry if candidate collision occurs.
    """
    def _do_gen(c):
        rows = c.execute("SELECT patient_id FROM patients WHERE patient_id LIKE 'P%'").fetchall()
        max_num = 10000
        for r in rows:
            pid = r[0] if isinstance(r, (tuple, list)) else r["patient_id"]
            if pid and pid.startswith("P") and pid[1:].isdigit():
                try:
                    val = int(pid[1:])
                    if val > max_num:
                        max_num = val
                except ValueError:
                    pass
        candidate = f"P{max_num + 1}"
        while c.execute("SELECT 1 FROM patients WHERE patient_id = ?", (candidate,)).fetchone():
            max_num += 1
            candidate = f"P{max_num + 1}"
        return candidate

    if conn is not None:
        return _do_gen(conn)
    with get_db(db_path) as c:
        return _do_gen(c)


def generate_visit_id():
    """Generate a unique hospital visit identifier."""
    date_str = datetime.now().strftime("%Y%m%d")
    short_uid = uuid.uuid4().hex[:5].upper()
    return f"VIS-{date_str}-{short_uid}"


def log_audit(actor_role, action, patient_id=None, visit_id=None, details=None, actor_id="system", db_path=None, conn=None):
    """Log access and mutations for privacy and security compliance."""
    try:
        if conn is not None:
            conn.execute(
                """
                INSERT INTO audit_logs (actor_role, actor_id, action, patient_id, visit_id, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (actor_role, actor_id, action, patient_id, visit_id, details)
            )
        else:
            with get_db(db_path) as c:
                c.execute(
                    """
                    INSERT INTO audit_logs (actor_role, actor_id, action, patient_id, visit_id, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (actor_role, actor_id, action, patient_id, visit_id, details)
                )
    except Exception:
        pass


def find_patient_by_phone(phone, db_path=None):
    """Find patient records matching a normalized phone number."""
    phone_clean = normalize_phone(phone)
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM patients WHERE phone = ? ORDER BY registered_at DESC",
            (phone_clean,)
        ).fetchall()
        return [dict(r) for r in rows]


def normalize_patient_id(patient_id):
    """Safely decode and normalize patient identifier handling hyphens, dashes, URL encoding, quotes and case."""
    if not patient_id:
        return ""
    import urllib.parse
    cleaned = urllib.parse.unquote(str(patient_id)).strip()
    # Strip any leading/trailing surrounding quotes, punctuation or brackets
    cleaned = cleaned.strip(" \t\r\n\"'`[]():;,.")
    # Normalize unicode dash and hyphen variants to standard ASCII hyphen '-'
    dash_variants = [
        "\u2010",  # Hyphen
        "\u2011",  # Non-breaking hyphen
        "\u2012",  # Figure dash
        "\u2013",  # En dash
        "\u2014",  # Em dash
        "\u2015",  # Horizontal bar
        "\u2212",  # Minus sign
        "\uFE58",  # Small em dash
        "\uFE63",  # Small hyphen-minus
        "\uFF0D",  # Fullwidth hyphen-minus
    ]
    for d in dash_variants:
        cleaned = cleaned.replace(d, "-")
    cleaned = re.sub(r"\s*-\s*", "-", cleaned)
    return cleaned.strip(" \t\r\n\"'`[]():;,.")


def find_patient_by_id(patient_id, db_path=None):
    """Find patient record by unique patient identifier (supports both short P-series and legacy PAT-).
    Resolves variations with dashes, encoding, quotes, spaces, and case, returning the canonical database record.
    """
    if not patient_id:
        return None
    norm_id = normalize_patient_id(patient_id)
    if not norm_id:
        return None
    with get_db(db_path) as conn:
        # 1. Exact match (case-insensitive) on normalized ID
        row = conn.execute(
            "SELECT * FROM patients WHERE LOWER(patient_id) = LOWER(?)",
            (norm_id,)
        ).fetchone()
        if row:
            return dict(row)

        # 2. Try raw un-normalized ID stripped of outer quotes
        raw_clean = str(patient_id).strip(" \t\r\n\"'`[]():;,.")
        if raw_clean and raw_clean != norm_id:
            row = conn.execute(
                "SELECT * FROM patients WHERE LOWER(patient_id) = LOWER(?)",
                (raw_clean,)
            ).fetchone()
            if row:
                return dict(row)

        # 3. Fuzzy match ignoring hyphens/spaces/underscores/quotes (e.g. PAT20262123D6 -> PAT-2026-2123D6)
        compact_query = re.sub(r"[\s\-_\.'\"`]+", "", norm_id).lower()
        if compact_query:
            all_patients = conn.execute("SELECT * FROM patients").fetchall()
            for p in all_patients:
                p_compact = re.sub(r"[\s\-_\.'\"`]+", "", str(p["patient_id"] or "")).lower()
                if p_compact == compact_query:
                    return dict(p)

        return None


def register_or_get_patient(phone, name, age=None, gender=None, force_new=False, confirm_existing=False, db_path=None):
    """Register a new patient or retrieve existing patient with phone normalization and name conflict handling."""
    phone_clean = normalize_phone(phone)
    name_clean = name.strip()

    with get_db(db_path) as conn:
        existing_records = [
            dict(r) for r in conn.execute(
                "SELECT * FROM patients WHERE phone = ? ORDER BY registered_at DESC",
                (phone_clean,)
            ).fetchall()
        ]

        if existing_records:
            # 1. If user explicitly confirmed "Yes, I am [Existing Name]"
            if confirm_existing:
                existing = existing_records[0]
                log_audit("system", "patient_retrieved", existing["patient_id"],
                          details=f"Confirmed existing patient: {existing['name']}", conn=conn)
                return existing, False

            # 2. Check if name is consistent with an existing record unless user requested a forced new registration
            if not force_new:
                for rec in existing_records:
                    if names_are_consistent(rec["name"], name_clean):
                        log_audit("system", "patient_retrieved", rec["patient_id"],
                                  details=f"Returning patient identified: {rec['name']} (input: '{name_clean}')", conn=conn)
                        return rec, False

                # 3. Phone matched an existing patient but name conflicts and force_new was not requested
                primary = existing_records[0]
                raise PatientNameConflictError(
                    f"Phone {phone} is already registered to '{primary['name']}'. Please confirm if this is you or register as a family member.",
                    existing_patient=primary
                )

        # 4. New patient registration (or forced new patient for shared family phone)
        new_pid = generate_patient_id(conn=conn)
        conn.execute(
            """
            INSERT INTO patients (patient_id, phone, name, age, gender)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_pid, phone_clean, name_clean, int(age) if age else None, gender)
        )
        log_audit("system", "patient_registered", new_pid, details=f"New patient: {name_clean} (phone: {phone_clean})", conn=conn)

        created = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (new_pid,)).fetchone()
        return dict(created), True


def create_visit(patient_id, allow_duplicate_today=False, db_path=None):
    """Create a new hospital visit and assign the next sequential daily token number.
    Reuses today's active waiting visit by default to prevent duplicate visits on page refresh or double-click.
    """
    with get_db(db_path) as conn:
        if not allow_duplicate_today:
            existing_visit = conn.execute(
                """
                SELECT * FROM visits
                WHERE patient_id = ? AND date(created_at) = date('now') AND status = 'waiting'
                ORDER BY created_at DESC LIMIT 1
                """,
                (patient_id,)
            ).fetchone()
            if existing_visit:
                return dict(existing_visit)

        # Calculate next monotonic sequential token for today
        token_rows = conn.execute(
            "SELECT token_number FROM visits WHERE date(created_at) = date('now')"
        ).fetchall()
        max_num = 100
        for r in token_rows:
            tn = r["token_number"] or ""
            if tn.startswith("T-") and tn[2:].isdigit():
                num = int(tn[2:])
                if num > max_num:
                    max_num = num
        token_num = max_num + 1
        token_str = f"T-{token_num}"

        visit_id = generate_visit_id()
        conn.execute(
            """
            INSERT INTO visits (visit_id, patient_id, token_number, status)
            VALUES (?, ?, ?, 'waiting')
            """,
            (visit_id, patient_id, token_str)
        )
        log_audit("system", "visit_created", patient_id, visit_id=visit_id, details=f"Issued token {token_str}", conn=conn)

        visit_row = conn.execute("SELECT * FROM visits WHERE visit_id = ?", (visit_id,)).fetchone()
        return dict(visit_row)


def get_active_visits(db_path=None, needs_vitals=False):
    """Retrieve visits, optionally limited to waiting patients without vitals."""
    with get_db(db_path) as conn:
        queue_filter = """WHERE v.status != 'completed'"""
        if needs_vitals:
            queue_filter += """
              AND NOT EXISTS (
                  SELECT 1 FROM nurse_queue_completions nqc
                  WHERE nqc.visit_id = v.visit_id
              )
            """
        rows = conn.execute(
            f"""
            SELECT v.*, p.name as patient_name, p.phone as patient_phone, p.age as patient_age, p.gender as patient_gender
            FROM visits v
            JOIN patients p ON v.patient_id = p.patient_id
            {queue_filter}
            ORDER BY v.created_at DESC, v.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]



def sync_unprocessed_reports(visit_id, conn):
    """Ensure any uploaded report for visit has been processed for labs, meds, and findings."""
    try:
        from src.services.ocr_service import process_report_file
        rep_rows = conn.execute("SELECT * FROM reports WHERE visit_id = ?", (visit_id,)).fetchall()
        for r in rep_rows:
            r_dict = dict(r)
            rid = r_dict["report_id"]
            storage_path = Path(r_dict.get("storage_path", ""))
            if not storage_path.exists():
                continue

            has_labs = conn.execute("SELECT 1 FROM extracted_results WHERE report_id = ? LIMIT 1", (rid,)).fetchone()
            has_meds = conn.execute("SELECT 1 FROM extracted_medications WHERE report_id = ? LIMIT 1", (rid,)).fetchone()

            if not has_labs and not has_meds:
                res = process_report_file(str(storage_path))
                doc_type = res.get("doc_type", "Medical Report")
                status = res.get("status", "completed").capitalize()
                findings_count = res.get("findings_count", 0)

                conn.execute(
                    """
                    UPDATE reports SET doc_type = ?, extraction_status = ?, findings_count = ?, error_message = ?
                    WHERE report_id = ?
                    """,
                    (doc_type, status, findings_count, res.get("message", ""), rid)
                )

                for lab in res.get("extracted_rows", []):
                    eid = f"EXT-{os.urandom(4).hex()}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO extracted_results (
                            extract_id, report_id, patient_id, visit_id, test_name, test_value,
                            unit, reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (eid, rid, r_dict["patient_id"], visit_id, lab["test"], lab["value"],
                         lab.get("unit", ""), lab.get("reference_range", ""), lab.get("range_note", ""),
                         lab.get("page", 1), json.dumps(lab.get("bbox", [])), lab.get("source_line", ""),
                         1 if lab.get("quote_ok", True) else 0, lab.get("extraction_method", "ocr"))
                    )

                for med in res.get("extracted_medications", []):
                    mid = f"MED-{uuid.uuid4().hex[:8].upper()}"
                    conn.execute(
                        """
                        INSERT INTO extracted_medications (
                            med_id, report_id, patient_id, visit_id, medicine_name, dosage,
                            frequency, timing, duration, route, instructions, source_line, extraction_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (mid, rid, r_dict["patient_id"], visit_id, med["medicine_name"],
                         med.get("dosage", "Not specified"), med.get("frequency", "Not specified"),
                         med.get("timing", "Not specified"), med.get("duration", "Not specified"),
                         med.get("route", "Not specified"), med.get("instructions", "Not specified"),
                         med.get("source_line", ""), med.get("extraction_method", "ocr"))
                    )

                for f_item in res.get("document_findings", []):
                    fid = f"FND-{uuid.uuid4().hex[:8].upper()}"
                    conn.execute(
                        """
                        INSERT INTO document_findings (
                            finding_id, report_id, patient_id, visit_id, category, title, detail,
                            severity, is_automated, source_line
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (fid, rid, r_dict["patient_id"], visit_id, f_item.get("category", "diagnostic_observation"),
                         f_item.get("title", "Clinical Finding"), f_item.get("detail", ""), f_item.get("severity", "info"),
                         1 if f_item.get("is_automated", 1) else 0, f_item.get("source_line", ""))
                    )
    except Exception:
        pass


def get_visit_details(visit_id, db_path=None):
    """Retrieve complete details for a specific visit."""
    with get_db(db_path) as conn:
        v_row = conn.execute(
            """
            SELECT v.*, p.name as patient_name, p.phone as patient_phone, p.age as patient_age, p.gender as patient_gender
            FROM visits v
            JOIN patients p ON v.patient_id = p.patient_id
            WHERE v.visit_id = ?
            """,
            (visit_id,)
        ).fetchone()
        if not v_row:
            return None
        visit = dict(v_row)

        intake_row = conn.execute("SELECT * FROM intakes WHERE visit_id = ?", (visit_id,)).fetchone()
        visit["intake"] = dict(intake_row) if intake_row else None

        vitals_row = conn.execute("SELECT * FROM vitals WHERE visit_id = ?", (visit_id,)).fetchone()
        visit["vitals"] = dict(vitals_row) if vitals_row else None

        sync_unprocessed_reports(visit_id, conn)

        rep_rows = conn.execute("SELECT * FROM reports WHERE visit_id = ? ORDER BY created_at ASC", (visit_id,)).fetchall()
        v_reports = []
        for r in rep_rows:
            rd = dict(r)
            rd["download_url"] = f"/api/reports/{rd['report_id']}/file"
            if not rd.get("doc_type"):
                rd["doc_type"] = "Medical Report"
            if not rd.get("extraction_status"):
                rd["extraction_status"] = "Completed"
            v_reports.append(rd)
        visit["reports"] = v_reports

        ext_rows = conn.execute(
            """
            SELECT er.*, r.filename as source_document
            FROM extracted_results er
            LEFT JOIN reports r ON er.report_id = r.report_id
            WHERE er.visit_id = ?
            ORDER BY er.id ASC
            """,
            (visit_id,)
        ).fetchall()
        visit["extracted_results"] = [dict(r) for r in ext_rows]

        med_rows = conn.execute(
            """
            SELECT em.*, r.filename as source_document
            FROM extracted_medications em
            LEFT JOIN reports r ON em.report_id = r.report_id
            WHERE em.visit_id = ?
            ORDER BY em.id ASC
            """,
            (visit_id,)
        ).fetchall()
        visit["extracted_medications"] = [dict(r) for r in med_rows]

        find_rows = conn.execute(
            """
            SELECT df.*, r.filename as source_document
            FROM document_findings df
            LEFT JOIN reports r ON df.report_id = r.report_id
            WHERE df.visit_id = ?
            ORDER BY df.id ASC
            """,
            (visit_id,)
        ).fetchall()
        visit["document_findings"] = [dict(r) for r in find_rows]

        sum_row = conn.execute("SELECT * FROM summaries WHERE visit_id = ?", (visit_id,)).fetchone()
        visit["summary"] = json.loads(sum_row["summary_json"]) if sum_row else None

        doc_row = conn.execute("SELECT * FROM doctor_notes WHERE visit_id = ?", (visit_id,)).fetchone()
        visit["doctor_notes"] = dict(doc_row) if doc_row else None

        dec_rows = conn.execute("SELECT * FROM doctor_reviews WHERE visit_id = ?", (visit_id,)).fetchall()
        visit["decisions"] = {
            r["item_id"]: {
                "decision": r["decision"],
                "part_type": r["part_type"],
                "corrected_value": json.loads(r["corrected_value_json"]) if r["corrected_value_json"] else None,
                "reviewed_at": r["reviewed_at"]
            }
            for r in dec_rows
        }

    # Attach longitudinal past visits (prior consultations with doctor notes, problems, and labs)
    past = get_patient_history(visit["patient_id"], exclude_visit_id=visit_id, db_path=db_path)
    visit["past_visits"] = past

    # If summary is missing, generate initial card using demographics, past visits & doctor notes
    if not visit.get("summary"):
        try:
            from src.services.summary_service import generate_clinical_summary, save_summary
            p_info = {
                "name": visit["patient_name"],
                "age": visit["patient_age"],
                "gender": visit["patient_gender"],
                "patient_id": visit["patient_id"],
                "phone": visit["patient_phone"]
            }
            initial_sum = generate_clinical_summary(
                intake_data=visit.get("intake") or {},
                vitals_data=visit.get("vitals") or {},
                extracted_labs=visit.get("extracted_results") or [],
                returning_history=past,
                patient_info=p_info
            )
            save_summary(visit_id, visit["patient_id"], initial_sum, db_path=db_path)
            visit["summary"] = initial_sum
        except Exception:
            pass

    return visit


def get_patient_history(patient_id, exclude_visit_id=None, db_path=None):
    """Retrieve all prior visits and medical history for a returning patient."""
    with get_db(db_path) as conn:
        query = "SELECT * FROM visits WHERE patient_id = ?"
        params = [patient_id]
        if exclude_visit_id:
            query += " AND visit_id != ?"
            params.append(exclude_visit_id)
        query += " ORDER BY created_at DESC, id DESC"

        visits = [dict(r) for r in conn.execute(query, params).fetchall()]
        for v in visits:
            vid = v["visit_id"]
            intake = conn.execute("SELECT * FROM intakes WHERE visit_id = ?", (vid,)).fetchone()
            v["intake"] = dict(intake) if intake else None

            vitals = conn.execute("SELECT * FROM vitals WHERE visit_id = ?", (vid,)).fetchone()
            v["vitals"] = dict(vitals) if vitals else None

            notes = conn.execute("SELECT * FROM doctor_notes WHERE visit_id = ?", (vid,)).fetchone()
            v["doctor_notes"] = dict(notes) if notes else None

            rep_rows = conn.execute("SELECT * FROM reports WHERE visit_id = ? ORDER BY created_at ASC", (vid,)).fetchall()
            v["reports"] = [dict(r) for r in rep_rows]

            labs = conn.execute(
                """
                SELECT er.*, r.filename as source_document
                FROM extracted_results er
                LEFT JOIN reports r ON er.report_id = r.report_id
                WHERE er.visit_id = ?
                ORDER BY er.id ASC
                """,
                (vid,)
            ).fetchall()
            v["extracted_results"] = [dict(r) for r in labs]

            meds = conn.execute(
                """
                SELECT em.*, r.filename as source_document
                FROM extracted_medications em
                LEFT JOIN reports r ON em.report_id = r.report_id
                WHERE em.visit_id = ?
                ORDER BY em.id ASC
                """,
                (vid,)
            ).fetchall()
            v["extracted_medications"] = [dict(r) for r in meds]

            findings = conn.execute(
                """
                SELECT df.*, r.filename as source_document
                FROM document_findings df
                LEFT JOIN reports r ON df.report_id = r.report_id
                WHERE df.visit_id = ?
                ORDER BY df.id ASC
                """,
                (vid,)
            ).fetchall()
            v["document_findings"] = [dict(r) for r in findings]

            summary = conn.execute("SELECT * FROM summaries WHERE visit_id = ?", (vid,)).fetchone()
            v["summary"] = json.loads(summary["summary_json"]) if summary else None

        log_audit("doctor", "view_patient_history", patient_id, details="Retrieved longitudinal history", conn=conn)
        return visits


def record_vitals(visit_id, patient_id, bp_systolic=None, bp_diastolic=None, heart_rate=None,
                   temperature=None, spo2=None, blood_sugar=None, recorded_by="nurse", db_path=None, conn=None):
    """Record nurse-measured patient vital signs."""
    def _do_record(c):
        c.execute(
            """
            INSERT INTO vitals (visit_id, patient_id, bp_systolic, bp_diastolic, heart_rate,
                                temperature, spo2, blood_sugar, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(visit_id) DO UPDATE SET
                bp_systolic = excluded.bp_systolic,
                bp_diastolic = excluded.bp_diastolic,
                heart_rate = excluded.heart_rate,
                temperature = excluded.temperature,
                spo2 = excluded.spo2,
                blood_sugar = excluded.blood_sugar,
                recorded_by = excluded.recorded_by,
                created_at = CURRENT_TIMESTAMP
            """,
            (visit_id, patient_id, bp_systolic, bp_diastolic, heart_rate, temperature, spo2, blood_sugar, recorded_by)
        )
        log_audit(recorded_by, "record_vitals", patient_id, visit_id=visit_id,
                  details=f"BP={bp_systolic}/{bp_diastolic}, HR={heart_rate}, SpO2={spo2}%", conn=c)

    if conn is not None:
        _do_record(conn)
    else:
        with get_db(db_path) as c:
            _do_record(c)


def save_intake(visit_id, patient_id, reason_for_visit, symptoms_text, duration=None,
                severity=None, associated_symptoms=None, conditions=None, medications=None,
                allergies=None, history=None, submitted_by="patient", db_path=None, conn=None):
    """Save patient or nurse-assisted intake questionnaire responses."""
    intake_id = f"INT-{uuid.uuid4().hex[:8]}"

    def _do_save(c):
        c.execute(
            """
            INSERT INTO intakes (intake_id, visit_id, patient_id, reason_for_visit, symptoms_text,
                                 duration, severity, associated_symptoms, medical_conditions,
                                 current_medications, known_allergies, previous_history, submitted_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(visit_id) DO UPDATE SET
                reason_for_visit = excluded.reason_for_visit,
                symptoms_text = excluded.symptoms_text,
                duration = excluded.duration,
                severity = excluded.severity,
                associated_symptoms = excluded.associated_symptoms,
                medical_conditions = excluded.medical_conditions,
                current_medications = excluded.current_medications,
                known_allergies = excluded.known_allergies,
                previous_history = excluded.previous_history,
                submitted_by = excluded.submitted_by,
                created_at = CURRENT_TIMESTAMP
            """,
            (intake_id, visit_id, patient_id, reason_for_visit, symptoms_text, duration,
             severity, associated_symptoms, conditions, medications, allergies, history, submitted_by)
        )
        log_audit(submitted_by, "submit_intake", patient_id, visit_id=visit_id,
                  details=f"Reason: {reason_for_visit[:40] if reason_for_visit else 'None'}", conn=c)

    if conn is not None:
        _do_save(conn)
    else:
        with get_db(db_path) as c:
            _do_save(c)
    return intake_id


def verify_and_get_returning_patient(patient_id, verification_phone=None, db_path=None):
    """Verify patient identity and retrieve record by MRN.
    Prevents unauthorized access by checking registered phone number if provided.
    """
    if not patient_id:
        return None, "Patient ID (MRN) is required."

    patient = find_patient_by_id(patient_id.strip(), db_path=db_path)
    if not patient:
        return None, f"No patient found with MRN '{patient_id}'. Please check your ID or look up with your registered phone number."

    if verification_phone:
        v_clean = normalize_phone(verification_phone)
        p_clean = normalize_phone(patient.get("phone", ""))
        if v_clean != p_clean:
            return None, f"Identity verification failed: The mobile number entered does not match hospital records for {patient_id}."

    log_audit("patient", "patient_verified", patient["patient_id"], details=f"Identity verified for MRN {patient_id}", db_path=db_path)
    return patient, None


def checkin_returning_patient(patient_id, verification_phone=None, db_path=None):
    """Check in a verified returning patient for a new hospital visit.
    Reuses existing patient record & MRN, creates a new visit and token for today.
    """
    patient, error = verify_and_get_returning_patient(patient_id, verification_phone=verification_phone, db_path=db_path)
    if error:
        raise ValueError(error)

    visit = create_visit(patient["patient_id"], db_path=db_path)
    past_visits = get_patient_history(patient["patient_id"], exclude_visit_id=visit["visit_id"], db_path=db_path)

    # Prefill information from most recent consultation
    prefill = {}
    if past_visits:
        last_pv = past_visits[0]
        last_intake = last_pv.get("intake") or {}
        prefill = {
            "medical_conditions": last_intake.get("medical_conditions") or "",
            "current_medications": last_intake.get("current_medications") or "",
            "known_allergies": last_intake.get("known_allergies") or "",
            "previous_history": last_intake.get("previous_history") or ""
        }

    # Generate initial clinical summary card for current visit
    try:
        from src.services.summary_service import generate_clinical_summary, save_summary
        initial_summary = generate_clinical_summary(
            intake_data={},
            vitals_data={},
            extracted_labs=[],
            returning_history=past_visits,
            patient_info=patient
        )
        save_summary(visit["visit_id"], patient["patient_id"], initial_summary, db_path=db_path)
        visit["summary"] = initial_summary
    except Exception:
        pass

    log_audit("patient", "returning_patient_checkin", patient["patient_id"], visit_id=visit["visit_id"],
              details=f"Returning check-in with token {visit['token_number']}", db_path=db_path)

    return {
        "status": "success",
        "patient": patient,
        "visit": visit,
        "past_visits": past_visits,
        "prefill": prefill
    }


def lookup_patient_by_phone_and_name(phone, name=None, db_path=None):
    """Lookup patient MRN when patient forgot their ID."""
    phone_clean = normalize_phone(phone)
    if not phone_clean:
        return []
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT patient_id, name, phone, age, gender, registered_at FROM patients WHERE phone = ? ORDER BY registered_at DESC",
            (phone_clean,)
        ).fetchall()
        results = [dict(r) for r in rows]
        if name and name.strip():
            filtered = [r for r in results if names_are_consistent(r["name"], name.strip())]
            return filtered if filtered else results
        return results


def get_patient_complete_timeline(patient_id, db_path=None):
    """Retrieve full longitudinal profile and chronological visit timeline for Patient Records tab.
    Ensures safe identifier resolution and canonical database ID usage.
    """
    patient = find_patient_by_id(patient_id, db_path=db_path)
    if not patient:
        return None

    # CRITICAL: Always use the resolved patient's canonical database identifier
    canonical_patient_id = patient["patient_id"]

    with get_db(db_path) as conn:
        # All visits ordered by created_at DESC, id DESC (newest first)
        v_rows = conn.execute(
            "SELECT * FROM visits WHERE LOWER(patient_id) = LOWER(?) ORDER BY created_at DESC, id DESC",
            (canonical_patient_id,)
        ).fetchall()
        visits = [dict(r) for r in v_rows]

        all_reports = []
        for v in visits:
            vid = v["visit_id"]

            intake = conn.execute("SELECT * FROM intakes WHERE visit_id = ?", (vid,)).fetchone()
            v["intake"] = dict(intake) if intake else None

            vitals = conn.execute("SELECT * FROM vitals WHERE visit_id = ?", (vid,)).fetchone()
            v["vitals"] = dict(vitals) if vitals else None

            doc_notes = conn.execute("SELECT * FROM doctor_notes WHERE visit_id = ?", (vid,)).fetchone()
            v["doctor_notes"] = dict(doc_notes) if doc_notes else None

            rep_rows = conn.execute("SELECT * FROM reports WHERE visit_id = ? ORDER BY created_at ASC", (vid,)).fetchall()
            v_reports = []
            for r in rep_rows:
                rd = dict(r)
                rd["download_url"] = f"/api/reports/{rd['report_id']}/file"
                v_reports.append(rd)
                all_reports.append(rd)
            v["reports"] = v_reports

            labs = conn.execute(
                """
                SELECT er.*, r.filename as source_document
                FROM extracted_results er
                LEFT JOIN reports r ON er.report_id = r.report_id
                WHERE er.visit_id = ?
                ORDER BY er.id ASC
                """,
                (vid,)
            ).fetchall()
            v["extracted_results"] = [dict(l) for l in labs]

            meds = conn.execute(
                """
                SELECT em.*, r.filename as source_document
                FROM extracted_medications em
                LEFT JOIN reports r ON em.report_id = r.report_id
                WHERE em.visit_id = ?
                ORDER BY em.id ASC
                """,
                (vid,)
            ).fetchall()
            v["extracted_medications"] = [dict(m) for m in meds]

            findings = conn.execute(
                """
                SELECT df.*, r.filename as source_document
                FROM document_findings df
                LEFT JOIN reports r ON df.report_id = r.report_id
                WHERE df.visit_id = ?
                ORDER BY df.id ASC
                """,
                (vid,)
            ).fetchall()
            v["document_findings"] = [dict(f) for f in findings]

            summary_row = conn.execute("SELECT * FROM summaries WHERE visit_id = ?", (vid,)).fetchone()
            if summary_row and summary_row["summary_json"]:
                try:
                    v["summary"] = json.loads(summary_row["summary_json"])
                except Exception:
                    v["summary"] = None
            else:
                v["summary"] = None

    # Derive baseline medical profile from all recorded visits
    chronic_conditions = []
    current_medications = []
    known_allergies = []
    for v in visits:
        if v.get("intake"):
            in_data = v["intake"]
            cond = in_data.get("medical_conditions")
            if cond and cond.strip() and cond not in chronic_conditions:
                chronic_conditions.append(cond.strip())
            meds = in_data.get("current_medications")
            if meds and meds.strip() and meds not in current_medications:
                current_medications.append(meds.strip())
            allg = in_data.get("known_allergies")
            if allg and allg.strip() and allg not in known_allergies:
                known_allergies.append(allg.strip())

    profile = {
        "patient": patient,
        "visits_count": len(visits),
        "chronic_conditions": ", ".join(chronic_conditions) if chronic_conditions else "None declared",
        "current_medications": ", ".join(current_medications) if current_medications else "None declared",
        "known_allergies": ", ".join(known_allergies) if known_allergies else "No known drug allergies",
        "visits": visits,
        "all_reports": all_reports
    }

    log_audit("clinical_staff", "view_patient_records", canonical_patient_id,
              details=f"Retrieved complete timeline with {len(visits)} visits", db_path=db_path)
    return profile
