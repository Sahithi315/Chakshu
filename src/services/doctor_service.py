"""Doctor review, decision tracking, consultation notes, and longitudinal lab queries."""
from datetime import datetime
from pathlib import Path
import json
import os
import time
from src.database.connection import get_db
from src.services.patient_service import log_audit

ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY_DECISIONS = ROOT / "data" / "decisions.json"


def record_doctor_decision(visit_id, patient_id, item_id, part_type, decision, corrected_value=None, db_path=None, conn=None):
    """
    Record Confirm, Correct, or Reject for a symptom or lab finding.
    Persists to database table `doctor_reviews` and updates legacy decisions.json.
    """
    corrected_json = json.dumps(corrected_value) if corrected_value else None

    def _do_record(c):
        c.execute(
            """
            INSERT INTO doctor_reviews (visit_id, patient_id, item_id, part_type, decision, corrected_value_json, reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(visit_id, item_id) DO UPDATE SET
                decision = excluded.decision,
                corrected_value_json = excluded.corrected_value_json,
                reviewed_at = CURRENT_TIMESTAMP
            """,
            (visit_id, patient_id, item_id, part_type, decision, corrected_json)
        )

        # Synchronize verification status directly on extracted_medications if reviewing a medication
        if part_type == "medication" or str(item_id).startswith("MED-"):
            if decision == "confirmed":
                c.execute(
                    """
                    UPDATE extracted_medications
                    SET verification_status = 'confirmed', verified_at = CURRENT_TIMESTAMP
                    WHERE med_id = ?
                    """,
                    (item_id,)
                )
            elif decision == "rejected":
                c.execute(
                    """
                    UPDATE extracted_medications
                    SET verification_status = 'rejected', verified_at = CURRENT_TIMESTAMP
                    WHERE med_id = ?
                    """,
                    (item_id,)
                )
            elif decision == "corrected":
                # Snapshot original OCR fields separately before applying doctor corrections (only once)
                existing_med = c.execute(
                    """
                    SELECT medicine_name, medicine_type, strength, dosage, frequency, timing,
                           duration, quantity, route, instructions, raw_text, confidence,
                           original_ocr_json
                    FROM extracted_medications WHERE med_id = ?
                    """,
                    (item_id,)
                ).fetchone()
                orig_ocr_snapshot = None
                if existing_med and not existing_med["original_ocr_json"]:
                    orig_ocr_snapshot = json.dumps({
                        "medicine_name": existing_med["medicine_name"],
                        "medicine_type": existing_med["medicine_type"],
                        "strength": existing_med["strength"],
                        "dosage": existing_med["dosage"],
                        "frequency": existing_med["frequency"],
                        "timing": existing_med["timing"],
                        "duration": existing_med["duration"],
                        "quantity": existing_med["quantity"],
                        "route": existing_med["route"],
                        "instructions": existing_med["instructions"],
                        "raw_text": existing_med["raw_text"],
                        "confidence": existing_med["confidence"],
                    })

                corr_name = None
                corr_dosage = None
                corr_freq = None
                corr_timing = None
                corr_duration = None
                corr_route = None
                corr_inst = None
                corr_type = None
                corr_strength = None
                corr_qty = None
                if isinstance(corrected_value, dict):
                    corr_name = corrected_value.get("medicine_name")
                    corr_dosage = corrected_value.get("dosage")
                    corr_freq = corrected_value.get("frequency")
                    corr_timing = corrected_value.get("timing")
                    corr_duration = corrected_value.get("duration")
                    corr_route = corrected_value.get("route")
                    corr_inst = corrected_value.get("instructions")
                    corr_type = corrected_value.get("medicine_type")
                    corr_strength = corrected_value.get("strength")
                    corr_qty = corrected_value.get("quantity")
                c.execute(
                    """
                    UPDATE extracted_medications
                    SET verification_status = 'corrected',
                        corrected_data_json = ?,
                        original_ocr_json = COALESCE(original_ocr_json, ?),
                        medicine_name = COALESCE(?, medicine_name),
                        dosage = COALESCE(?, dosage),
                        frequency = COALESCE(?, frequency),
                        timing = COALESCE(?, timing),
                        duration = COALESCE(?, duration),
                        route = COALESCE(?, route),
                        instructions = COALESCE(?, instructions),
                        medicine_type = COALESCE(?, medicine_type),
                        strength = COALESCE(?, strength),
                        quantity = COALESCE(?, quantity),
                        verified_at = CURRENT_TIMESTAMP
                    WHERE med_id = ?
                    """,
                    (corrected_json, orig_ocr_snapshot, corr_name, corr_dosage, corr_freq, corr_timing, corr_duration, corr_route, corr_inst, corr_type, corr_strength, corr_qty, item_id)
                )

        log_audit(
            "doctor", f"decision_{decision}", patient_id, visit_id=visit_id,
            details=f"Item {item_id} ({part_type}) marked {decision}",
            conn=c
        )

    if conn is not None:
        _do_record(conn)
    else:
        with get_db(db_path) as c:
            _do_record(c)

    # Legacy file sync
    try:
        decisions = {}
        if LEGACY_DECISIONS.exists():
            try:
                decisions = json.loads(LEGACY_DECISIONS.read_text(encoding="utf-8"))
            except Exception:
                decisions = {}
        rec = decisions.setdefault(item_id, {"history": []})
        rec["state"] = decision
        if corrected_value is not None:
            rec["corrected_value"] = corrected_value
        rec["history"].append({
            "state": decision,
            "corrected_value": corrected_value,
            "at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        LEGACY_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
        LEGACY_DECISIONS.write_text(json.dumps(decisions, indent=1), encoding="utf-8")
    except Exception:
        pass


def save_doctor_notes(visit_id, patient_id, clinical_notes, plan=None, doctor_id="DOC-01", db_path=None, conn=None):
    """Save doctor's consultation notes and clinical assessment."""
    def _do_save(c):
        c.execute(
            """
            INSERT INTO doctor_notes (visit_id, patient_id, doctor_id, clinical_notes, plan, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(visit_id) DO UPDATE SET
                clinical_notes = excluded.clinical_notes,
                plan = excluded.plan,
                doctor_id = excluded.doctor_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (visit_id, patient_id, doctor_id, clinical_notes, plan)
        )
        c.execute(
            "UPDATE visits SET status = 'completed' WHERE visit_id = ?",
            (visit_id,)
        )
        log_audit(
            "doctor", "save_consultation_notes", patient_id, visit_id=visit_id,
            details="Recorded clinical notes and marked visit completed",
            conn=c
        )

    if conn is not None:
        _do_save(conn)
    else:
        with get_db(db_path) as c:
            _do_save(c)


def get_longitudinal_labs(patient_id, db_path=None):
    """
    Retrieve historical lab test results grouped by test name across visits.
    Returns: dict mapping test_name -> list of {visit_id, date, value, unit, reference_range, range_note}
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.test_name, e.test_value, e.unit, e.reference_range, e.range_note, v.visit_id, v.created_at
            FROM extracted_results e
            JOIN visits v ON e.visit_id = v.visit_id
            WHERE e.patient_id = ?
            ORDER BY v.created_at ASC
            """,
            (patient_id,)
        ).fetchall()

        by_test = {}
        for r in rows:
            tname = r["test_name"].strip()
            if tname not in by_test:
                by_test[tname] = []
            by_test[tname].append({
                "visit_id": r["visit_id"],
                "date": r["created_at"][:10],
                "value": r["test_value"],
                "unit": r["unit"] or "",
                "reference_range": r["reference_range"] or "",
                "range_note": r["range_note"] or ""
            })
        return by_test
