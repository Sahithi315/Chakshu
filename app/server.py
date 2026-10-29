"""Fast and robust ASGI backend server for Team 404 Vision platform.
Uses Starlette and Uvicorn. Exposes REST API and serves the React frontend.
"""
from pathlib import Path
import json
import os
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from src.database.connection import get_db
from src.database.schema import init_db
from src.services.patient_service import (
    register_or_get_patient, find_patient_by_phone, find_patient_by_id,
    create_visit, get_active_visits, get_visit_details, get_patient_history,
    record_vitals, save_intake, PatientNameConflictError, normalize_phone,
    checkin_returning_patient, lookup_patient_by_phone_and_name,
    get_patient_complete_timeline, verify_and_get_returning_patient,
    normalize_patient_id
)
from src.services.report_service import (
    store_and_register_report, get_reports_for_visit, get_reports_for_patient,
    get_report_by_id, ReportValidationError
)
from src.services.ocr_service import process_report_file, is_tesseract_available
from src.services.summary_service import generate_clinical_summary, save_summary
from src.services.doctor_service import (
    record_doctor_decision, save_doctor_notes, get_longitudinal_labs
)
# Cached symptom extractor
_extractor = None

def get_extractor():
    global _extractor
    if _extractor is None:
        from src.symptoms.infer import Extractor
        model_path = ROOT / "models" / "modernbert_f100_s1"
        if model_path.is_dir():
            _extractor = Extractor(str(model_path), fallback_to_baseline=True)
        else:
            _extractor = Extractor(fallback_to_baseline=True)
    return _extractor


# ---------------- API HANDLERS ----------------

async def health(request):
    return JSONResponse({
        "status": "healthy",
        "tesseract_available": is_tesseract_available(),
        "model_mode": get_extractor().mode,
        "database": "sqlite_connected"
    })


async def list_visits(request):
    """Retrieve active visit queue."""
    visits = get_active_visits()
    return JSONResponse(visits)


async def get_visit(request):
    """Get complete details for a specific visit."""
    visit_id = request.path_params["visit_id"]
    data = get_visit_details(visit_id)
    if not data:
        return JSONResponse({"error": "Visit not found"}, status_code=404)
    return JSONResponse(data)


async def search_patients(request):
    """Search patients by query (phone, name, patient_id) with normalization for hyphens and smart dashes."""
    q = request.query_params.get("q", "").strip()
    with get_db() as conn:
        if not q:
            rows = conn.execute("SELECT * FROM patients ORDER BY registered_at DESC LIMIT 25").fetchall()
            return JSONResponse([dict(r) for r in rows])

        q_norm = normalize_patient_id(q)
        q_phone = normalize_phone(q)
        compact_q = q_norm.replace("-", "").replace(" ", "").lower()

        rows = conn.execute(
            """
            SELECT * FROM patients
            WHERE phone LIKE ?
               OR phone LIKE ?
               OR LOWER(name) LIKE ?
               OR LOWER(patient_id) LIKE ?
               OR LOWER(patient_id) LIKE ?
            ORDER BY registered_at DESC LIMIT 25
            """,
            (f"%{q}%", f"%{q_phone}%", f"%{q.lower()}%", f"%{q.lower()}%", f"%{q_norm.lower()}%")
        ).fetchall()

        results = [dict(r) for r in rows]
        # If no direct matches, attempt fuzzy compact match on patient ID
        if not results and compact_q:
            all_rows = conn.execute("SELECT * FROM patients ORDER BY registered_at DESC LIMIT 50").fetchall()
            for r in all_rows:
                db_compact = str(r["patient_id"] or "").replace("-", "").replace(" ", "").lower()
                if compact_q in db_compact:
                    results.append(dict(r))

        return JSONResponse(results)


async def get_patient(request):
    """Retrieve patient details and prior visit history safely."""
    try:
        raw_id = request.path_params.get("patient_id", "")
        patient_id = urllib.parse.unquote(raw_id).strip()
        p = find_patient_by_id(patient_id)
        if not p:
            return JSONResponse({"error": f"Patient record '{patient_id}' not found"}, status_code=404)
        canonical_id = p["patient_id"]
        history = get_patient_history(canonical_id)
        trends = get_longitudinal_labs(canonical_id)
        return JSONResponse({
            "patient": p,
            "history": history,
            "longitudinal_labs": trends
        })
    except Exception as e:
        return JSONResponse({"error": "Failed to retrieve patient details"}, status_code=500)


async def register_patient_endpoint(request):
    """Register patient and issue an OPD visit token with conflict handling."""
    body = await request.json()
    phone = body.get("phone", "").strip()
    name = body.get("name", "").strip()
    age = body.get("age")
    gender = body.get("gender")
    force_new = bool(body.get("force_new", False))
    confirm_existing = bool(body.get("confirm_existing", False))

    if not phone or not name:
        return JSONResponse({"error": "Phone and Name are required"}, status_code=400)

    try:
        patient, is_new = register_or_get_patient(
            phone=phone,
            name=name,
            age=age,
            gender=gender,
            force_new=force_new,
            confirm_existing=confirm_existing
        )
    except PatientNameConflictError as err:
        return JSONResponse({
            "status": "name_conflict",
            "error": str(err),
            "existing_patient": err.existing_patient
        }, status_code=409)

    visit = create_visit(patient["patient_id"])
    past_visits = get_patient_history(patient["patient_id"], exclude_visit_id=visit["visit_id"])

    # Generate initial single summary card immediately (incorporates past doctor notes & records)
    initial_summary = generate_clinical_summary(
        intake_data={},
        vitals_data={},
        extracted_labs=[],
        returning_history=past_visits,
        patient_info=patient
    )
    save_summary(visit["visit_id"], patient["patient_id"], initial_summary)
    visit["summary"] = initial_summary

    return JSONResponse({
        "status": "success",
        "patient": patient,
        "visit": visit,
        "is_new": is_new,
        "past_visits": past_visits
    })


async def save_intake_endpoint(request):
    """Save patient intake form and generate single summary card."""
    body = await request.json()
    visit_id = body.get("visit_id")
    patient_id = body.get("patient_id")

    if not visit_id or not patient_id:
        return JSONResponse({"error": "visit_id and patient_id are required"}, status_code=400)

    intake_id = save_intake(
        visit_id=visit_id,
        patient_id=patient_id,
        reason_for_visit=body.get("reason_for_visit", ""),
        symptoms_text=body.get("symptoms_text", ""),
        duration=body.get("duration", ""),
        severity=body.get("severity", ""),
        associated_symptoms=body.get("associated_symptoms", ""),
        conditions=body.get("medical_conditions", ""),
        medications=body.get("current_medications", ""),
        allergies=body.get("known_allergies", ""),
        history=body.get("previous_history", ""),
        submitted_by=body.get("submitted_by", "patient")
    )

    # Re-generate and save clinical summary card
    visit_data = get_visit_details(visit_id)
    patient_data = find_patient_by_id(patient_id)
    prior_history = get_patient_history(patient_id, exclude_visit_id=visit_id)

    summary_payload = generate_clinical_summary(
        intake_data=visit_data.get("intake"),
        vitals_data=visit_data.get("vitals"),
        extracted_labs=visit_data.get("extracted_results"),
        returning_history=prior_history,
        patient_info=patient_data
    )
    save_summary(visit_id, patient_id, summary_payload)

    return JSONResponse({
        "status": "success",
        "intake_id": intake_id,
        "summary": summary_payload
    })


async def save_vitals_endpoint(request):
    """Record nurse vitals and re-generate clinical summary card."""
    body = await request.json()
    visit_id = body.get("visit_id")
    patient_id = body.get("patient_id")

    if not visit_id or not patient_id:
        return JSONResponse({"error": "visit_id and patient_id are required"}, status_code=400)

    record_vitals(
        visit_id=visit_id,
        patient_id=patient_id,
        bp_systolic=body.get("bp_systolic"),
        bp_diastolic=body.get("bp_diastolic"),
        heart_rate=body.get("heart_rate"),
        temperature=body.get("temperature"),
        spo2=body.get("spo2"),
        blood_sugar=body.get("blood_sugar"),
        recorded_by=body.get("recorded_by", "nurse")
    )

    # Re-generate and save clinical summary card
    visit_data = get_visit_details(visit_id)
    patient_data = find_patient_by_id(patient_id)
    prior_history = get_patient_history(patient_id, exclude_visit_id=visit_id)

    summary_payload = generate_clinical_summary(
        intake_data=visit_data.get("intake"),
        vitals_data=visit_data.get("vitals"),
        extracted_labs=visit_data.get("extracted_results"),
        returning_history=prior_history,
        patient_info=patient_data
    )
    save_summary(visit_id, patient_id, summary_payload)

    return JSONResponse({
        "status": "success",
        "summary": summary_payload
    })


async def upload_report_endpoint(request):
    """Handle multipart file upload for medical reports (PDF/JPG/PNG)."""
    form = await request.form()
    file = form.get("file")
    patient_id = form.get("patient_id")
    visit_id = form.get("visit_id")
    group_id = form.get("group_id")

    if not file or not patient_id or not visit_id:
        return JSONResponse({"error": "file, patient_id, and visit_id are required"}, status_code=400)

    filename = file.filename
    content = await file.read()

    try:
        rep_rec, is_new = store_and_register_report(
            file_bytes=content,
            filename=filename,
            patient_id=patient_id,
            visit_id=visit_id,
            group_id=group_id
        )

        # Extract lab records via structured PDF or OCR
        extraction_res = process_report_file(rep_rec["storage_path"])

        # Insert extracted results into DB
        with get_db() as conn:
            for r in extraction_res.get("extracted_rows", []):
                eid = f"EXT-{os.urandom(4).hex()}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO extracted_results (
                        extract_id, report_id, patient_id, visit_id, test_name, test_value,
                        unit, reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (eid, rep_rec["report_id"], patient_id, visit_id, r["test"], r["value"],
                     r.get("unit", ""), r.get("reference_range", ""), r.get("range_note", ""),
                     r.get("page", 1), json.dumps(r.get("bbox", [])), r.get("source_line", ""),
                     1 if r.get("quote_ok", True) else 0, r.get("extraction_method", "ocr"))
                )

        # Recompile summary card
        visit_data = get_visit_details(visit_id)
        patient_data = find_patient_by_id(patient_id)
        prior_history = get_patient_history(patient_id, exclude_visit_id=visit_id)

        summary_payload = generate_clinical_summary(
            intake_data=visit_data.get("intake"),
            vitals_data=visit_data.get("vitals"),
            extracted_labs=visit_data.get("extracted_results"),
            returning_history=prior_history,
            patient_info=patient_data
        )
        save_summary(visit_id, patient_id, summary_payload)

        return JSONResponse({
            "status": "success",
            "report": rep_rec,
            "is_new": is_new,
            "extraction": extraction_res,
            "summary": summary_payload
        })
    except ReportValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Failed to upload report: {str(e)}"}, status_code=500)


async def tag_symptoms_endpoint(request):
    """Run symptom extractor on patient text."""
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"symptoms": [], "durations": [], "severities": []})

    extractor = get_extractor()
    spans = extractor.spans([text])[0]
    extracted = extractor.extract(text)
    return JSONResponse(extracted)


async def save_decision_endpoint(request):
    """Record doctor decision: confirm, correct, or reject."""
    body = await request.json()
    visit_id = body.get("visit_id")
    patient_id = body.get("patient_id")
    item_id = body.get("item_id")
    part_type = body.get("part_type", "symptom")
    decision = body.get("decision")  # confirmed, corrected, rejected
    corrected_value = body.get("corrected_value")

    if not visit_id or not patient_id or not item_id or not decision:
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    record_doctor_decision(
        visit_id=visit_id,
        patient_id=patient_id,
        item_id=item_id,
        part_type=part_type,
        decision=decision,
        corrected_value=corrected_value
    )
    return JSONResponse({"status": "success"})


async def save_notes_endpoint(request):
    """Save doctor consultation notes and complete visit."""
    body = await request.json()
    visit_id = body.get("visit_id")
    patient_id = body.get("patient_id")
    clinical_notes = body.get("clinical_notes", "").strip()
    plan = body.get("plan", "").strip()
    doctor_id = body.get("doctor_id", "DR-CONSULTANT")

    if not visit_id or not patient_id or not clinical_notes:
        return JSONResponse({"error": "visit_id, patient_id, and clinical_notes are required"}, status_code=400)

    save_doctor_notes(
        visit_id=visit_id,
        patient_id=patient_id,
        clinical_notes=clinical_notes,
        plan=plan,
        doctor_id=doctor_id
    )

    # Re-generate and save updated summary for this visit reflecting completed doctor evaluation
    visit_data = get_visit_details(visit_id)
    patient_data = find_patient_by_id(patient_id)
    prior_history = get_patient_history(patient_id, exclude_visit_id=visit_id)

    summary_payload = generate_clinical_summary(
        intake_data=visit_data.get("intake") or {},
        vitals_data=visit_data.get("vitals") or {},
        extracted_labs=visit_data.get("extracted_results") or [],
        returning_history=prior_history,
        patient_info=patient_data
    )
    save_summary(visit_id, patient_id, summary_payload)

    return JSONResponse({
        "status": "success",
        "visit_status": "completed",
        "summary": summary_payload
    })


async def checkin_returning_endpoint(request):
    """Check in a returning patient by permanent MRN with phone verification."""
    body = await request.json()
    patient_id = body.get("patient_id", "").strip()
    phone = body.get("verification_phone", "").strip()

    if not patient_id:
        return JSONResponse({"error": "Permanent Patient ID (MRN) is required"}, status_code=400)

    try:
        result = checkin_returning_patient(patient_id, verification_phone=phone or None)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Failed to check in returning patient: {str(e)}"}, status_code=500)


async def lookup_patient_endpoint(request):
    """Lookup patient MRN when patient forgot their ID."""
    body = await request.json()
    phone = body.get("phone", "").strip()
    name = body.get("name", "").strip()

    if not phone:
        return JSONResponse({"error": "Registered phone number is required for lookup"}, status_code=400)

    results = lookup_patient_by_phone_and_name(phone, name=name)
    return JSONResponse({"patients": results})


async def get_patient_records_endpoint(request):
    """Retrieve full longitudinal profile and chronological visit timeline for Patient Records tab safely."""
    try:
        raw_id = request.path_params.get("patient_id", "")
        patient_id = urllib.parse.unquote(raw_id).strip()
        if not patient_id:
            return JSONResponse({"error": "Patient identifier is required"}, status_code=400)

        profile = get_patient_complete_timeline(patient_id)
        if not profile:
            return JSONResponse({"error": f"Patient record '{patient_id}' was not found in the hospital system"}, status_code=404)
        return JSONResponse(profile)
    except Exception as e:
        return JSONResponse(
            {"error": "An error occurred while retrieving medical records. Please try again or contact hospital administration."},
            status_code=500
        )


async def download_report_endpoint(request):
    """Securely serve uploaded report file for viewing or download."""
    report_id = request.path_params["report_id"]
    rep = get_report_by_id(report_id)
    if not rep:
        return JSONResponse({"error": "Report not found"}, status_code=404)
    path = Path(rep["storage_path"])
    if not path.exists():
        return JSONResponse({"error": "Report file is missing from storage disk"}, status_code=404)
    return FileResponse(path=str(path), filename=rep["filename"])


# ---------------- ROUTE SETUP ----------------

routes = [
    Route("/api/health", health, methods=["GET"]),
    Route("/api/visits", list_visits, methods=["GET"]),
    Route("/api/visits/{visit_id}", get_visit, methods=["GET"]),
    Route("/api/patients", search_patients, methods=["GET"]),
    Route("/api/patients/register", register_patient_endpoint, methods=["POST"]),
    Route("/api/patients/checkin-returning", checkin_returning_endpoint, methods=["POST"]),
    Route("/api/patients/lookup", lookup_patient_endpoint, methods=["POST"]),
    Route("/api/patients/{patient_id}/records", get_patient_records_endpoint, methods=["GET"]),
    Route("/api/patients/{patient_id}", get_patient, methods=["GET"]),
    Route("/api/intake", save_intake_endpoint, methods=["POST"]),
    Route("/api/vitals", save_vitals_endpoint, methods=["POST"]),
    Route("/api/reports/upload", upload_report_endpoint, methods=["POST"]),
    Route("/api/reports/{report_id}/file", download_report_endpoint, methods=["GET"]),
    Route("/api/symptoms/tag", tag_symptoms_endpoint, methods=["POST"]),
    Route("/api/doctor/decision", save_decision_endpoint, methods=["POST"]),
    Route("/api/doctor/notes", save_notes_endpoint, methods=["POST"]),
]

# Static frontend files mount if production build exists
dist_dir = ROOT / "frontend" / "dist"
if dist_dir.is_dir():
    routes.append(Mount("/", app=StaticFiles(directory=str(dist_dir), html=True), name="static"))

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == "__main__":
    import uvicorn
    print("Starting Clinical Context Platform API on http://127.0.0.1:8000")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=False)
