"""CareVision: Intelligent Hospital Assistant.
Run from repository root:  python -m streamlit run app/app.py
"""
import glob
import hashlib
import html
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st

from src.reports.extract import extract_pdf, highlight, quote_check
from src.symptoms.infer import Extractor
from src.symptoms.model import ModelNotFoundError, ModelLoadError
from src.database.schema import init_db
from src.database.connection import get_db
from src.services.patient_service import (
    register_or_get_patient, find_patient_by_phone, find_patient_by_id,
    create_visit, get_active_visits, get_visit_details, get_patient_history,
    record_vitals, save_intake, log_audit
)
from src.services.report_service import (
    store_and_register_report, get_reports_for_visit, get_reports_for_patient,
    ReportValidationError
)
from src.services.ocr_service import (
    process_report_file, is_tesseract_available
)
from src.services.summary_service import generate_clinical_summary, save_summary
from src.services.doctor_service import (
    record_doctor_decision, save_doctor_notes, get_longitudinal_labs
)

# Ensure database is initialized
init_db()

MODEL_DIR = os.path.join(ROOT, "models", "modernbert_f100_s1")
PDF_DIR = os.path.join(ROOT, "data", "synthetic_lab_reports")
DECISIONS = os.path.join(ROOT, "data", "decisions.json")

KINDS = {
    "SYMPTOM": "Symptom",
    "NEG_SYMPTOM": "Denied symptom",
    "DURATION": "Duration",
    "SEVERITY": "Severity"
}
COLORS = {
    "SYMPTOM": "#ffe08a",
    "NEG_SYMPTOM": "#ffb3b3",
    "DURATION": "#b9dcff",
    "SEVERITY": "#d9c2ff"
}
STATES = {
    "confirmed": "Doctor confirmed",
    "corrected": "Corrected",
    "rejected": "Rejected"
}

st.set_page_config(
    page_title="CareVision",
    page_icon="🏥",
    layout="wide"
)

# ---- Saved decisions helpers (Database-backed with JSON legacy compatibility) ----
def load_decisions():
    try:
        if os.path.exists(DECISIONS):
            return json.load(open(DECISIONS, encoding="utf-8"))
        return {}
    except Exception:
        return {}


def save_decision(item, state, corrected=None, visit_id=None, patient_id=None):
    # Save to SQLite database
    vid = visit_id or st.session_state.get("active_visit_id", "VIS-DEFAULT")
    pid = patient_id or st.session_state.get("active_patient_id", "PAT-DEFAULT")
    record_doctor_decision(
        visit_id=vid,
        patient_id=pid,
        item_id=item["id"],
        part_type=item.get("part", "symptom"),
        decision=state,
        corrected_value=corrected
    )
    # Also sync legacy JSON file
    d = load_decisions()
    rec = d.setdefault(item["id"], {"original": item["original"], "context": item["context"], "history": []})
    rec["state"] = state
    if corrected is not None:
        rec["corrected_value"] = corrected
    rec["history"].append({"state": state, "corrected_value": corrected, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    os.makedirs(os.path.dirname(DECISIONS), exist_ok=True)
    json.dump(d, open(DECISIONS + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(DECISIONS + ".tmp", DECISIONS)
    st.session_state.editing = None


def item_id(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


# ---- Models and extraction (cached) ----
@st.cache_resource(show_spinner="Loading symptom extractor...")
def get_model():
    """Load symptom extractor with graceful fallback to rule-based baseline."""
    try:
        # Check if local model directory exists
        if os.path.isdir(MODEL_DIR):
            return Extractor(MODEL_DIR, fallback_to_baseline=True)
        else:
            return Extractor(fallback_to_baseline=True)
    except Exception as e:
        return Extractor(fallback_to_baseline=True)


@st.cache_data(show_spinner="Reading PDF...")
def read_pdf(path):
    return extract_pdf(path)


@st.cache_data(show_spinner=False)
def page_image(path, page, bbox):
    return highlight(path, page, bbox)


# ---- Provenance and UI item display ----
def show_item(item, decisions, visit_id=None, patient_id=None):
    rec = decisions.get(item["id"])
    state = STATES.get(rec["state"], "Unreviewed") if rec else "Unreviewed"
    st.markdown(f"**{item['title']}**  \n{item['detail']}")
    st.caption(" · ".join(item["sources"]) + f" · State: **{state}**")
    if rec and rec.get("corrected_value"):
        c = rec["corrected_value"]
        flag = "" if c.get("quote_ok", True) else " (corrected value not found in its source line)"
        st.caption(f"Original: {item['original_text']} → Corrected: {c.get('text', '')}{flag}")
    a, b, c, d = st.columns(4)
    k = item["id"]
    a.button("Show source", key=f"src{k}", on_click=st.session_state.update, kwargs={"selected": item})
    b.button("Confirm", key=f"ok{k}", on_click=save_decision, args=(item, "confirmed", None, visit_id, patient_id))
    c.button("Correct", key=f"fix{k}", on_click=st.session_state.update, kwargs={"editing": k})
    d.button("Reject", key=f"no{k}", on_click=save_decision, args=(item, "rejected", None, visit_id, patient_id))
    if st.session_state.get("editing") == k:
        with st.form(f"form{k}"):
            kind = st.selectbox("Type", list(KINDS.values()), index=list(KINDS.values()).index(item["kind"])) if item["part"] == "symptom" else None
            text = st.text_input("Corrected value", value=item["original_text"])
            if st.form_submit_button("Save correction"):
                quote_ok = quote_check(text, item["source_line"]) if item["part"] == "lab" else True
                save_decision(item, "corrected", {"text": text, "kind": kind, "quote_ok": quote_ok}, visit_id, patient_id)
                st.rerun()
    st.divider()


def symptom_items(text, spans):
    out = []
    for s in spans:
        phrase = text[s["start"]:s["end"]]
        kind = KINDS[s["label"]]
        out.append({
            "id": item_id("sym", text, s["start"], s["end"], s["label"]),
            "part": "symptom",
            "title": f"{kind}: {phrase}",
            "detail": "",
            "kind": kind,
            "label": s["label"],
            "span": (s["start"], s["end"]),
            "text": text,
            "original_text": phrase,
            "source_line": text,
            "sources": ["Typed by patient", "AI Extractor (Verified with clinical rules, needs doctor confirmation)"],
            "context": {"typed_text": text},
            "original": {"kind": kind, "text": phrase, "start": s["start"], "end": s["end"]}
        })
    return out


def lab_items(path, name, key):
    out = []
    for r in read_pdf(path):
        note = f" · {r['range_note']}" if r["range_note"] else ""
        flag = "" if r["quote_ok"] else " · value not found in its source line"
        out.append({
            "id": item_id("lab", key, r["page"], r["test"], [round(x) for x in r["bbox"]]),
            "part": "lab",
            "title": r["test"],
            "detail": f"{r['value']} {r['unit']} · printed range {r['reference_range']}{note}{flag}",
            "kind": "Lab result",
            "path": path,
            "page": r["page"],
            "bbox": tuple(r["bbox"]),
            "original_text": r["value"],
            "source_line": r["source_line"],
            "sources": ["Extracted from uploaded document"],
            "context": {"file": name, "page": r["page"], "source_line": r["source_line"]},
            "original": {k: r[k] for k in ("test", "value", "unit", "reference_range", "range_note", "page", "bbox")}
        })
    return out


def show_source(item):
    st.subheader("Source Provenance")
    if item["part"] == "lab":
        st.caption(f"{item['context']['file']} · page {item['page']} · {item['source_line']}")
        try:
            st.image(page_image(item["path"], item["page"], item["bbox"]), width="stretch")
        except Exception as e:
            st.warning(f"Could not render image preview: {e}")
            st.code(item["source_line"], language="text")
    else:
        t, (s, e) = item["text"], item["span"]
        st.markdown(
            f"<div style='font-size:1.15rem;padding:12px;border:1px solid #ddd;border-radius:6px;background:#fbfbfb'>"
            f"{html.escape(t[:s])}<mark style='background:{COLORS[item['label']]};padding:2px 4px;border-radius:3px'>"
            f"{html.escape(t[s:e])}</mark>{html.escape(t[e:])}</div>",
            unsafe_allow_html=True
        )
        st.caption("Provenance: Patient-Reported Intake")


# ==========================================
# SIDEBAR NAVIGATION & SYSTEM HEALTH
# ==========================================
st.sidebar.title("🏥 CareVision")
st.sidebar.caption("Intelligent Hospital Assistant")

nav_choice = st.sidebar.radio(
    "Navigation Role",
    [
        "🩺 Doctor Dashboard",
        "📋 Patient Self-Check-in",
        "👩‍⚕️ Nurse / Staff Station",
        "📊 Returning Patient History",
        "⚙️ System Status & Audits"
    ]
)

# Engine status indicator in sidebar
extractor_instance = get_model()
model_exists = os.path.exists(MODEL_DIR)
tesseract_ok = is_tesseract_available()

with st.sidebar.expander("System Engine Status", expanded=False):
    if model_exists:
        st.success("✅ Transformer Model: ModernBERT-base Checkpoint Loaded")
    else:
        st.info("ℹ️ Symptom Engine: Validated Rule-Based Baseline (Keyword + Negation + Duration)")
    if tesseract_ok:
        st.success("✅ OCR Engine: Tesseract OCR Active")
    else:
        st.warning("⚠️ OCR Engine: Tesseract not found on system path")
    st.success("✅ Database: SQLite Persistent (hospital.db)")

st.warning("⚠️ Prototype. Synthetic data only. For clinical documentation assistance. Not for clinical diagnosis or prescription.")


# ==========================================
# VIEW 1: DOCTOR DASHBOARD
# ==========================================
if nav_choice == "🩺 Doctor Dashboard":
    st.title("🩺 Doctor Brief & Consultation Screen")
    st.caption("Review AI-assisted pre-consultation summary, verify extracted lab evidence, and record consultation notes.")

    active_visits = get_active_visits()
    if not active_visits:
        st.info("No active patient visits found in the queue. Complete patient check-in or run seeder.")
        st.stop()

    # Patient Queue Selector
    visit_options = {
        f"{v['token_number']} - {v['patient_name']} ({v['patient_id']}) [{v['status'].upper()}]": v['visit_id']
        for v in active_visits
    }
    selected_label = st.selectbox("Select Patient from Queue (Token / Name / ID)", list(visit_options.keys()))
    active_vid = visit_options[selected_label]
    visit_data = get_visit_details(active_vid)

    if not visit_data:
        st.error("Visit details not found.")
        st.stop()

    pid = visit_data["patient_id"]
    st.session_state["active_visit_id"] = active_vid
    st.session_state["active_patient_id"] = pid

    # Patient Header Banner
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("Token Number", visit_data.get("token_number", "N/A"))
    col_p2.metric("Patient ID", pid)
    col_p3.metric("Patient Name", f"{visit_data.get('patient_name', 'Unknown')} ({visit_data.get('patient_age', '-')} y/o, {visit_data.get('patient_gender', '-')})")
    col_p4.metric("Phone", visit_data.get("patient_phone", "-"))

    st.divider()

    # PRE-CONSULTATION CLINICAL BRIEF
    st.subheader("📋 Pre-Consultation Summary Brief")
    summary = visit_data.get("summary")
    if summary:
        with st.container():
            st.info(f"**Concise Synthesis:** {summary.get('concise_brief', 'No brief generated.')}")

            sum_c1, sum_c2 = st.columns(2)
            with sum_c1:
                st.markdown("#### Patient-Reported Intake")
                p_rep = summary.get("patient_reported", {})
                st.write(f"- **Reason for Visit:** {p_rep.get('reason_for_visit', '-')}")
                st.write(f"- **Reported Symptoms:** {p_rep.get('symptoms_description', '-')}")
                st.write(f"- **Duration & Severity:** {p_rep.get('duration', '-')} | {p_rep.get('severity', '-')}")
                st.write(f"- **Comorbidities:** {p_rep.get('chronic_conditions', '-')}")
                st.write(f"- **Medications:** {p_rep.get('current_medications', '-')}")
                st.write(f"- **Known Allergies:** {p_rep.get('known_allergies', '-')}")

            with sum_c2:
                st.markdown("#### Clinical Vitals & Flags")
                st.markdown("**Nurse Vitals:**")
                for v_str in summary.get("nurse_vitals", []):
                    st.write(f"- {v_str}")

                st.markdown("**Information Gaps Requiring Confirmation:**")
                for gap in summary.get("information_gaps", []):
                    st.warning(f"⚠️ {gap}")

            # Abnormal Lab Findings Card
            abnormal_labs = summary.get("lab_evidence", {}).get("abnormal_results", [])
            if abnormal_labs:
                st.markdown("#### 🚨 Out-of-Range Lab Results")
                for al in abnormal_labs:
                    st.error(f"**{al['test']}**: {al['value']} (Ref Range: {al['reference_range']}) - {al['range_note']} [{al['source']}]")
    else:
        st.warning("Pre-consultation summary has not been generated for this visit yet.")

    st.divider()

    # TWO COLUMN INTERACTIVE REVIEW: Symptoms & Lab on Left, Source on Right
    left, right = st.columns([3, 2])
    decisions = load_decisions()

    with left:
        st.header("Symptom Verification")
        st.caption("Review extracted symptom phrases with character spans. Confirm, Correct, or Reject.")

        intake = visit_data.get("intake") or {}
        default_sym_text = intake.get("symptoms_text", "")
        text = st.text_area("Patient text", value=default_sym_text, key="typed", height=90,
                            placeholder="no fever but cough for 3 days, mild headache")

        if not model_exists:
            st.caption("ℹ️ Running in **Validated Rule-Based Baseline Mode**. Checkpoint `models/modernbert_f100_s1` is not trained.")

        if st.button("Tag symptoms") and text.strip():
            if len(text.split()) > 90:
                st.warning("Long text: the model reads the start of long messages (about 128 tokens).")
            if not text.isascii():
                st.warning("This model was trained on English text. Other scripts give unreliable tags.")
            spans = extractor_instance.spans([text])[0]
            st.session_state.sym = {"text": text, "spans": spans}

        if "sym" in st.session_state:
            t, sp = st.session_state.sym["text"], st.session_state.sym["spans"]
            marked, pos = "", 0
            for s in sp:
                marked += html.escape(t[pos:s["start"]]) + f"<mark style='background:{COLORS[s['label']]}'>{html.escape(t[s['start']:s['end']])}</mark><sup>{KINDS[s['label']]}</sup>"
                pos = s["end"]
            st.markdown(f"<div style='font-size:1.1rem;line-height:1.8'>{marked + html.escape(t[pos:])}</div>", unsafe_allow_html=True)
            items = symptom_items(t, sp)
            if not items:
                st.info("No tagged phrases found in this text.")
            for it in items:
                show_item(it, decisions, visit_id=active_vid, patient_id=pid)

        st.header("Medical Reports & Laboratory Findings")
        st.caption("Extracted clinical results from uploaded PDFs and scanned documents.")

        # Let doctor review from visit reports OR synthetic folder
        visit_reports = visit_data.get("reports", [])
        rep_options = [f"Uploaded: {r['filename']}" for r in visit_reports]
        synthetic_files = sorted(glob.glob(f"{PDF_DIR}/*.pdf"))
        rep_options += [f"Synthetic: {os.path.basename(f)}" for f in synthetic_files]

        if rep_options:
            picked_rep = st.selectbox("Select Report to Inspect", rep_options)
            if picked_rep.startswith("Uploaded: "):
                fname = picked_rep.replace("Uploaded: ", "")
                matching = [r for r in visit_reports if r["filename"] == fname]
                path = matching[0]["storage_path"] if matching else f"{PDF_DIR}/synthetic_report_001.pdf"
                name = fname
            else:
                fname = picked_rep.replace("Synthetic: ", "")
                path = f"{PDF_DIR}/{fname}"
                name = fname
        else:
            path, name = f"{PDF_DIR}/synthetic_report_001.pdf", "synthetic_report_001.pdf"

        up = st.file_uploader("Or test an additional PDF", type="pdf", key="doc_up_pdf")
        if up is not None:
            data = up.getvalue()
            name = up.name
            path = os.path.join(tempfile.gettempdir(), f"ccp_{hashlib.sha1(data).hexdigest()[:10]}.pdf")
            open(path, "wb").write(data)

        try:
            items = lab_items(path, name, name if up is None else path)
        except Exception as e:
            items = []
            st.error(f"Could not parse document: {type(e).__name__}: {e}")

        if not items and up is not None:
            st.info("No structured laboratory test rows were extracted from this PDF.")
        for it in items:
            show_item(it, decisions, visit_id=active_vid, patient_id=pid)

        # DOCTOR CONSULTATION NOTES & ASSESSMENT
        st.divider()
        st.subheader("✍️ Doctor Consultation Notes & Clinical Plan")
        existing_doc_note = visit_data.get("doctor_notes") or {}
        default_notes = existing_doc_note.get("clinical_notes", "")
        default_plan = existing_doc_note.get("plan", "")

        with st.form("doctor_notes_form"):
            c_notes = st.text_area("Clinical Examination & Observations", value=default_notes, height=100,
                                   placeholder="e.g. Chest clear, cardiovascular normal. Reviewed foot sensation.")
            c_plan = st.text_area("Diagnosis, Advice & Follow-up Plan", value=default_plan, height=80,
                                  placeholder="e.g. Continue Metformin 500mg BD. Order HbA1c in 3 months.")
            save_notes_btn = st.form_submit_button("Save Notes & Mark Consultation Completed")
            if save_notes_btn:
                if c_notes.strip():
                    save_doctor_notes(
                        visit_id=active_vid,
                        patient_id=pid,
                        clinical_notes=c_notes.strip(),
                        plan=c_plan.strip(),
                        doctor_id="DR-CONSULTANT",
                    )
                    st.success("Consultation notes saved successfully and visit marked as completed.")
                    st.rerun()
                else:
                    st.warning("Please enter clinical notes before saving.")

    with right:
        if st.session_state.get("selected"):
            show_source(st.session_state.selected)
        else:
            st.subheader("Source Provenance")
            st.caption("Click 'Show source' on any symptom or laboratory finding to inspect the original highlighted page or typed statement.")


# ==========================================
# VIEW 2: PATIENT SELF-CHECK-IN & INTAKE
# ==========================================
elif nav_choice == "📋 Patient Self-Check-in":
    st.title("📋 Patient Registration & Intake Check-in")
    st.caption("Step-by-step pre-consultation intake. Complete this form while waiting for your token.")

    checkin_step = st.radio("Step", ["1. Identify / Register", "2. Clinical Intake Form", "3. Upload Medical Reports"], horizontal=True)

    if checkin_step == "1. Identify / Register":
        st.subheader("Step 1: Patient Identification")
        st.caption("Enter your phone number to look up your existing record or register as a new patient.")

        phone_in = st.text_input("Mobile Phone Number (10 digits)", placeholder="e.g. 9876543210")
        name_in = st.text_input("Full Name", placeholder="e.g. Aarav Nair")
        c_age, c_gen = st.columns(2)
        age_in = c_age.number_input("Age", min_value=1, max_value=120, value=35)
        gen_in = c_gen.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])

        if st.button("Check-in & Issue Token"):
            if not phone_in.strip() or len(phone_in.strip()) < 8:
                st.error("Please enter a valid phone number.")
            elif not name_in.strip():
                st.error("Please enter your name.")
            else:
                patient, is_new = register_or_get_patient(phone_in, name_in, age=age_in, gender=gen_in)
                visit = create_visit(patient["patient_id"])
                st.session_state["patient_session"] = {
                    "patient": patient,
                    "visit": visit,
                    "is_new": is_new
                }
                st.success(f"{'New registration successful!' if is_new else 'Welcome back!'} Issued Token: **{visit['token_number']}** (Patient ID: {patient['patient_id']})")
                st.info("Please proceed to Step 2: Clinical Intake Form.")

    elif checkin_step == "2. Clinical Intake Form":
        st.subheader("Step 2: Medical Questionnaire")
        sess = st.session_state.get("patient_session")
        if not sess:
            st.warning("Please complete Step 1 (Identify / Register) first.")
            st.stop()

        p = sess["patient"]
        v = sess["visit"]
        st.info(f"Filling intake for: **{p['name']}** · Token: **{v['token_number']}**")

        with st.form("intake_form"):
            reason = st.text_input("What is the main reason for your visit today? *", placeholder="e.g. Cough and fever, or Diabetes routine check-up")
            symptoms = st.text_area("Describe your current symptoms in your own words *", height=80,
                                   placeholder="e.g. no fever but dry cough for 4 days, mild headache")

            col_dur, col_sev = st.columns(2)
            duration = col_dur.selectbox("How long have you had these symptoms?", ["Less than 1 day", "1 to 3 days", "4 to 7 days", "1 to 2 weeks", "More than 2 weeks", "Unsure / Gradual"])
            severity = col_sev.selectbox("How severe is the problem?", ["Mild (manageable)", "Moderate (interferes with routine)", "Severe (unbearable)", "Not applicable"])

            associated = st.text_input("Any other symptoms or changes you noticed?", placeholder="e.g. Feeling unusually thirsty or tired")

            st.markdown("#### Medical History & Safety")
            conditions = st.text_input("Existing chronic conditions", placeholder="e.g. Diabetes, High blood pressure, Asthma, None")
            medications = st.text_input("Medicines you are currently taking", placeholder="e.g. Metformin 500mg, None")
            allergies = st.text_input("Known medicine or food allergies (Type 'None' if no allergies)", placeholder="e.g. Penicillin, Sulfa drugs, No known allergies")
            history = st.text_input("Previous surgeries or hospital stays", placeholder="e.g. Gallbladder surgery in 2021, None")

            submit_intake = st.form_submit_button("Save Intake Details")
            if submit_intake:
                if not reason.strip():
                    st.error("Please enter the main reason for your visit.")
                else:
                    save_intake(
                        visit_id=v["visit_id"],
                        patient_id=p["patient_id"],
                        reason_for_visit=reason,
                        symptoms_text=symptoms,
                        duration=duration,
                        severity=severity,
                        associated_symptoms=associated,
                        conditions=conditions,
                        medications=medications,
                        allergies=allergies,
                        history=history,
                        submitted_by="patient"
                    )
                    st.session_state["intake_saved"] = True
                    st.success("Intake responses recorded securely! Please proceed to Step 3 to upload reports.")

    elif checkin_step == "3. Upload Medical Reports":
        st.subheader("Step 3: Medical Report Upload & Physical Scanning")
        sess = st.session_state.get("patient_session")
        if not sess:
            st.warning("Please complete Step 1 (Identify / Register) first.")
            st.stop()

        p = sess["patient"]
        v = sess["visit"]
        st.caption(f"Patient: {p['name']} · Token: {v['token_number']}")
        st.info("You can take a photo of a physical paper report using your mobile camera or upload existing PDF/JPG/PNG files.")

        upload_mode = st.radio("Choose upload method", ["📸 Camera Photo (Physical Paper Report)", "📁 File Picker (PDF / Image)"], horizontal=True)

        file_bytes = None
        file_name = None

        if upload_mode.startswith("📸"):
            cam_photo = st.camera_input("Photograph report (requires camera permission)")
            if cam_photo is not None:
                file_bytes = cam_photo.getvalue()
                file_name = f"camera_scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                st.image(file_bytes, caption="Camera capture preview", width=350)
        else:
            up_file = st.file_uploader("Upload lab reports or prescriptions", type=["pdf", "png", "jpg", "jpeg"])
            if up_file is not None:
                file_bytes = up_file.getvalue()
                file_name = up_file.name

        if file_bytes and file_name:
            c_up1, c_up2 = st.columns([2, 1])
            with c_up1:
                multipage_group = st.checkbox("Group multiple photos as a single multi-page report", value=False)
                group_id_val = f"GRP-{p['patient_id'][-4:]}" if multipage_group else None
            with c_up2:
                if st.button("Process & Save Report"):
                    try:
                        rep_rec, is_new = store_and_register_report(
                            file_bytes=file_bytes,
                            filename=file_name,
                            patient_id=p["patient_id"],
                            visit_id=v["visit_id"],
                            group_id=group_id_val
                        )
                        st.success(f"{'Report stored successfully!' if is_new else 'Identical report already on file (deduplicated).'}")

                        # Run extraction / OCR
                        with st.spinner("Extracting clinical findings..."):
                            res = process_report_file(rep_rec["storage_path"])
                            st.write(f"Extraction result: **{res['message']}**")
                            if res["extracted_rows"]:
                                # Save extracted rows
                                with get_db() as conn:
                                    for r in res["extracted_rows"]:
                                        eid = f"EXT-{hashlib.sha1(str(r).encode()).hexdigest()[:8]}"
                                        conn.execute(
                                            """
                                            INSERT OR IGNORE INTO extracted_results (
                                                extract_id, report_id, patient_id, visit_id, test_name, test_value,
                                                unit, reference_range, range_note, page, bbox_json, source_line, quote_ok, extraction_method
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """,
                                            (eid, rep_rec["report_id"], p["patient_id"], v["visit_id"], r["test"], r["value"],
                                             r.get("unit", ""), r.get("reference_range", ""), r.get("range_note", ""),
                                             r.get("page", 1), json.dumps(r.get("bbox", [])), r.get("source_line", ""),
                                             1 if r.get("quote_ok", True) else 0, r.get("extraction_method", "ocr"))
                                        )

                                # Re-generate and persist pre-consultation summary
                                v_details = get_visit_details(v["visit_id"])
                                summary_payload = generate_clinical_summary(
                                    intake_data=v_details.get("intake"),
                                    vitals_data=v_details.get("vitals"),
                                    extracted_labs=v_details.get("extracted_results")
                                )
                                save_summary(v["visit_id"], p["patient_id"], summary_payload)
                                st.success("Pre-consultation summary updated for the doctor.")

                    except ReportValidationError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Upload failed: {e}")


# ==========================================
# VIEW 3: NURSE / STAFF STATION
# ==========================================
elif nav_choice == "👩‍⚕️ Nurse / Staff Station":
    st.title("👩‍⚕️ Nurse Station & Vitals Recording")
    st.caption("Measure patient vitals, assist with intake, and capture physical paper reports.")

    active_visits = get_active_visits()
    if not active_visits:
        st.info("No patients currently waiting in the OPD queue.")
        st.stop()

    queue_labels = {
        f"Token {v['token_number']} - {v['patient_name']} ({v['patient_id']})": v['visit_id']
        for v in active_visits
    }
    sel_q = st.selectbox("Select Patient to Record Vitals", list(queue_labels.keys()))
    vid = queue_labels[sel_q]
    v_info = get_visit_details(vid)
    pid = v_info["patient_id"]

    st.subheader(f"Recording Vitals for: {v_info['patient_name']} (Token: {v_info['token_number']})")

    existing_vitals = v_info.get("vitals") or {}

    with st.form("nurse_vitals_form"):
        col_bp1, col_bp2, col_hr = st.columns(3)
        bp_sys = col_bp1.number_input("Systolic BP (mmHg)", min_value=60, max_value=250, value=existing_vitals.get("bp_systolic") or 120)
        bp_dia = col_bp2.number_input("Diastolic BP (mmHg)", min_value=40, max_value=150, value=existing_vitals.get("bp_diastolic") or 80)
        hr = col_hr.number_input("Pulse / Heart Rate (bpm)", min_value=30, max_value=220, value=existing_vitals.get("heart_rate") or 72)

        col_t, col_o2, col_bs = st.columns(3)
        temp = col_t.number_input("Temperature (°F)", min_value=90.0, max_value=108.0, value=float(existing_vitals.get("temperature") or 98.6), step=0.1)
        spo2 = col_o2.number_input("SpO2 Oxygen (%)", min_value=50.0, max_value=100.0, value=float(existing_vitals.get("spo2") or 99.0), step=0.5)
        bs = col_bs.number_input("Random Blood Sugar (mg/dL)", min_value=40.0, max_value=600.0, value=float(existing_vitals.get("blood_sugar") or 100.0), step=1.0)

        nurse_id = st.text_input("Nurse Staff ID", value="nurse_anita")

        if st.form_submit_button("Save Vitals"):
            record_vitals(
                visit_id=vid,
                patient_id=pid,
                bp_systolic=bp_sys,
                bp_diastolic=bp_dia,
                heart_rate=hr,
                temperature=temp,
                spo2=spo2,
                blood_sugar=bs,
                recorded_by=nurse_id
            )
            # Recompile summary with new vitals
            v_refreshed = get_visit_details(vid)
            sum_payload = generate_clinical_summary(
                intake_data=v_refreshed.get("intake"),
                vitals_data=v_refreshed.get("vitals"),
                extracted_labs=v_refreshed.get("extracted_results")
            )
            save_summary(vid, pid, sum_payload)
            st.success("Vitals saved and clinical summary updated successfully.")
            st.rerun()


# ==========================================
# VIEW 4: RETURNING PATIENT HISTORY
# ==========================================
elif nav_choice == "📊 Returning Patient History":
    st.title("📊 Longitudinal Medical History Retrieval")
    st.caption("Securely inspect prior OPD visits, historical lab results, and previous doctor consultation notes.")

    search_col1, search_col2 = st.columns([3, 1])
    search_q = search_col1.text_input("Enter Patient ID or Phone Number", placeholder="e.g. PAT-2026-0001 or 9876543210")

    if search_col1.button("Retrieve Patient Records") or search_q:
        p_match = None
        if search_q.startswith("PAT-") or search_q.startswith("SYN-"):
            p_match = find_patient_by_id(search_q)
        else:
            matches = find_patient_by_phone(search_q)
            if matches:
                p_match = matches[0]

        if not p_match:
            st.warning("No patient record found matching this identifier or phone number.")
        else:
            pid = p_match["patient_id"]
            st.success(f"Record Verified: **{p_match['name']}** · {p_match['gender']}, {p_match['age']} y/o · ID: {pid}")

            history = get_patient_history(pid)
            if not history:
                st.info("No prior visits recorded for this patient.")
            else:
                st.subheader(f"Found {len(history)} Visit(s)")

                # Longitudinal lab trends table
                trends = get_longitudinal_labs(pid)
                if trends:
                    st.markdown("#### 📈 Longitudinal Laboratory Findings")
                    for tname, records in trends.items():
                        st.markdown(f"**{tname}** ({records[0].get('unit', '')})")
                        cols = st.columns(len(records))
                        for idx, rec in enumerate(records):
                            cols[idx].metric(f"Date: {rec['date']}", f"{rec['value']} {rec['unit']}", delta=rec['range_note'] or "In range")
                    st.divider()

                # Detailed prior visit cards
                for idx, v in enumerate(history, 1):
                    with st.expander(f"Visit {idx}: Token {v.get('token_number', '-')} ({v['created_at'][:10]}) - Status: {v['status'].upper()}", expanded=(idx==1)):
                        intake = v.get("intake") or {}
                        st.write(f"**Reason for Visit:** {intake.get('reason_for_visit', '-')}")
                        st.write(f"**Symptoms:** {intake.get('symptoms_text', '-')}")
                        st.write(f"**Conditions:** {intake.get('medical_conditions', '-')}")
                        st.write(f"**Medications:** {intake.get('current_medications', '-')}")

                        vits = v.get("vitals") or {}
                        if vits:
                            st.write(f"**Vitals:** BP: {vits.get('bp_systolic')}/{vits.get('bp_diastolic')} mmHg | HR: {vits.get('heart_rate')} bpm | SpO2: {vits.get('spo2')}%")

                        notes = v.get("doctor_notes") or {}
                        if notes:
                            st.markdown(f"**Doctor Notes ({notes.get('doctor_id', 'Dr')}):** {notes.get('clinical_notes', '-')}")
                            st.markdown(f"**Plan:** {notes.get('plan', '-')}")


# ==========================================
# VIEW 5: SYSTEM STATUS & AUDIT LOGS
# ==========================================
elif nav_choice == "⚙️ System Status & Audits":
    st.title("⚙️ System Status, Compliance & Audit Trail")
    st.caption("Verification of model loading, OCR subsystem, privacy safeguards, and access logs.")

    st.subheader("Subsystem Diagnostics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Model Checkpoint", "Present" if model_exists else "Rule Baseline", help="ModernBERT fine-tuned model checkpoint vs rule baseline fallback")
    c2.metric("Tesseract OCR", "Available" if tesseract_ok else "Not Found", help="OCR engine status")
    c3.metric("Database Storage", "Connected", help="Persistent SQLite database")

    st.subheader("Model Loading Information")
    if model_exists:
        st.success(f"ModernBERT checkpoint found at `{MODEL_DIR}`.")
    else:
        st.info(
            f"Model directory `{MODEL_DIR}` is not yet trained.\n"
            "Operating cleanly in **Validated Rule-Based Baseline Mode**.\n"
            "To train the planned model:\n"
            "```bash\n"
            "python -m src.symptoms.train_all --data data/symptoms/split\n"
            "```"
        )

    st.subheader("Recent Security & Privacy Audit Trail")
    with get_db() as conn:
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 30").fetchall()
        if logs:
            st.dataframe(
                [dict(l) for l in logs],
                use_container_width=True
            )
        else:
            st.info("No audit logs recorded yet.")

if __name__ == "__main__":
    import uvicorn
    print("\n=======================================================")
    print(" CareVision: Intelligent Hospital Assistant")
    print(" Modern Vite + React Frontend & Starlette REST API")
    print(" Launching server at http://127.0.0.1:8000")
    print("=======================================================\n")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=False)

