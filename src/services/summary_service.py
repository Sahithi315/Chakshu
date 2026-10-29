"""Pre-consultation clinical summary generator with single-card 10-15s brief matching clinical PRD design."""
from datetime import datetime
import json
from src.database.connection import get_db
from src.services.patient_service import log_audit


def _detect_red_flags(symptoms_lower, vitals, conditions_lower):
    """Detect acute clinical red flag combinations requiring prioritized doctor review."""
    red_flags = []
    has_chest = any(w in symptoms_lower for w in ["chest pain", "chest tightness", "chest heaviness", "angina"])
    has_exertion = any(w in symptoms_lower for w in ["walking", "stairs", "exertion", "running"])
    has_sweat = any(w in symptoms_lower for w in ["sweat", "sweating", "diaphoresis"])
    has_sob = any(w in symptoms_lower for w in ["breathlessness", "shortness of breath", "dyspnea"])

    if has_chest and (has_exertion or has_sweat or has_sob):
        red_flags.append("Chest pain / heaviness with exertion or autonomic symptoms -> prioritize cardiovascular review.")

    if any(w in symptoms_lower for w in ["fever", "high fever"]) and any(w in symptoms_lower for w in ["stiff neck", "neck stiffness", "confusion", "altered mental"]):
        red_flags.append("High fever with neurological signs -> urgent meningeal evaluation.")

    if vitals:
        sys_bp = vitals.get("bp_systolic")
        dia_bp = vitals.get("bp_diastolic")
        if sys_bp and sys_bp >= 160:
            red_flags.append(f"Severe Hypertension recorded (BP: {sys_bp}/{dia_bp} mmHg).")
        spo2 = vitals.get("spo2")
        if spo2 and spo2 < 93:
            red_flags.append(f"Hypoxia noted (SpO2 {spo2}%). Immediate oxygenation check advised.")

    return " ".join(red_flags) if red_flags else None


def _format_ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def generate_clinical_summary(intake_data, vitals_data=None, extracted_labs=None, returning_history=None, patient_info=None):
    """
    Generate the 10-15 second concise single summary card (matching Team 404 Vision PRD design),
    plus full structured evidence.
    """
    intake = intake_data or {}
    vitals = vitals_data or {}
    labs = extracted_labs or []
    history = returning_history or []
    pinfo = patient_info or {}

    # Patient demographics
    name = pinfo.get("name") or intake.get("patient_name") or "Patient"
    age = pinfo.get("age") or intake.get("patient_age") or "-"
    patient_id = pinfo.get("patient_id") or intake.get("patient_id") or "MRN-PENDING"
    visit_count = len(history) + 1
    visit_ordinal = _format_ordinal(visit_count)

    # 1. Header line
    header = f"PATIENT: {name}, {age} | MRN {patient_id} | {visit_ordinal} visit"

    # 2. TODAY section
    reason = intake.get("reason_for_visit", "").strip()
    symptoms_text = intake.get("symptoms_text", "").strip()
    duration = intake.get("duration", "").strip()
    severity = intake.get("severity", "").strip()
    associated = intake.get("associated_symptoms", "").strip()

    today_lines = []
    if symptoms_text:
        today_lines.append(f"{symptoms_text}" + (f" for {duration}" if duration and duration.lower() not in symptoms_text.lower() else "") + ".")
    elif reason:
        today_lines.append(f"{reason}" + (f" for {duration}" if duration else "") + ".")
    elif history:
        today_lines.append(f"Follow-up consultation ({visit_ordinal} visit). Patient checked in; triage intake questionnaire pending.")
    else:
        today_lines.append("Initial consultation. Patient registered; triage intake questionnaire pending.")

    if associated:
        today_lines.append(f"Associated: {associated}.")
    today_text = " ".join(today_lines)

    # 3. RELEVANT HISTORY section
    conditions = intake.get("medical_conditions", "").strip()
    medications = intake.get("current_medications", "").strip()

    # If current intake has no chronic conditions or medications, inherit from past visits / doctor records
    if (not conditions or conditions.lower() in ("none", "none declared")) and history:
        for pv in history:
            pv_in = pv.get("intake") or {}
            pv_cond = pv_in.get("medical_conditions", "").strip()
            if pv_cond and pv_cond.lower() not in ("none", "none declared"):
                conditions = f"{pv_cond} (on hospital record)"
                break

    if (not medications or medications.lower() in ("none", "none declared")) and history:
        for pv in history:
            pv_in = pv.get("intake") or {}
            pv_med = pv_in.get("current_medications", "").strip()
            pv_doc = pv.get("doctor_notes") or {}
            pv_plan = pv_doc.get("plan", "").strip()
            if pv_med and pv_med.lower() not in ("none", "none declared"):
                medications = f"{pv_med} (prior hospital record)"
                break
            elif pv_plan and any(w in pv_plan.lower() for w in ["tab", "mg", "continue", "daily", "bd", "od"]):
                medications = f"{pv_plan} (prescribed at prior visit)"
                break

    history_bullets = []
    if conditions and conditions.lower() not in ("none declared", "none"):
        history_bullets.append(conditions)
    if medications and medications.lower() not in ("none declared", "none"):
        history_bullets.append(f"On {medications}")

    # Prior diagnostics from current labs or past visit labs
    if labs:
        key_labs = [f"{l.get('test_name', l.get('test', 'Test'))} {l.get('test_value', l.get('value', ''))} {l.get('unit','')}".strip() for l in labs[:2]]
        history_bullets.append(f"Recent lab findings: {', '.join(key_labs)}")
    elif history:
        # Check past labs
        for pv in history:
            pv_labs = pv.get("extracted_results") or []
            if pv_labs:
                past_key_labs = [f"{l.get('test_name', l.get('test', 'Test'))} {l.get('test_value', l.get('value', ''))} {l.get('unit','')}".strip() for l in pv_labs[:2]]
                p_date = pv.get("created_at", "")[:10]
                history_bullets.append(f"Previous lab findings ({p_date}): {', '.join(past_key_labs)}")
                break

    if not history_bullets:
        history_bullets.append("No significant chronic conditions or routine medications declared.")

    # 4. SAME COMPLAINT BEFORE section (Longitudinal past visit data including doctor writings & problems)
    same_complaint_bullets = []
    if history:
        for idx, pv in enumerate(history[:3], 1):
            p_date = pv.get("created_at", "")[:10]
            p_token = pv.get("token_number", "")
            p_intake = pv.get("intake") or {}
            p_notes = pv.get("doctor_notes") or {}
            p_reason = p_intake.get("reason_for_visit") or p_intake.get("symptoms_text") or "General medical consultation"
            p_dur = p_intake.get("duration", "")
            p_exam = p_notes.get("clinical_notes", "").strip()
            p_plan = p_notes.get("plan", "").strip()

            header_part = f"{p_date}" + (f" (Token {p_token})" if p_token else "") + f": Presented with \"{p_reason}\"" + (f" ({p_dur})" if p_dur else "")
            same_complaint_bullets.append(header_part)

            if p_exam:
                same_complaint_bullets.append(f"  - Prior Doctor Exam: {p_exam}")
            if p_plan:
                same_complaint_bullets.append(f"  - Prior Doctor Advice & Rx: {p_plan}")

            # Include lab reports recorded at that past visit
            pv_labs = pv.get("extracted_results") or []
            if pv_labs:
                labs_summary = ", ".join(f"{l.get('test_name', l.get('test', ''))}: {l.get('test_value', l.get('value', ''))} {l.get('unit', '')}".strip() for l in pv_labs[:2])
                same_complaint_bullets.append(f"  - Prior Lab Evidence: {labs_summary}")
    else:
        same_complaint_bullets.append("First recorded presentation for this complaint in this hospital.")

    # 5. RED FLAG section
    sym_all = f"{reason} {symptoms_text} {associated}".lower()
    red_flag_text = _detect_red_flags(sym_all, vitals, (conditions or "").lower())

    # 6. CONFIRM IN ROOM section (and information gaps)
    confirm_in_room = []
    allergies = intake.get("known_allergies", "").strip()
    if not allergies or allergies.lower() in ("unknown", "not sure", "not provided"):
        # Check past visits for recorded allergy
        past_allergy = None
        for pv in history:
            pv_al = (pv.get("intake") or {}).get("known_allergies", "").strip()
            if pv_al and pv_al.lower() not in ("unknown", "not sure", "not provided", ""):
                past_allergy = pv_al
                break
        if past_allergy:
            confirm_in_room.append(f"Known allergy check from prior record: {past_allergy}")
        else:
            confirm_in_room.append("Confirm Allergy status before prescribing (currently unrecorded).")
    else:
        confirm_in_room.append(f"Known allergy check: {allergies}")

    # Longitudinal verification questions
    if history:
        most_recent_pv = history[0]
        recent_plan = (most_recent_pv.get("doctor_notes") or {}).get("plan", "").strip()
        recent_reason = (most_recent_pv.get("intake") or {}).get("reason_for_visit", "").strip()
        if recent_plan:
            plan_brief = recent_plan[:70] + ("..." if len(recent_plan) > 70 else "")
            confirm_in_room.append(f"Check adherence to previous advice: \"{plan_brief}\"")
        if recent_reason:
            confirm_in_room.append(f"Assess whether prior symptom (\"{recent_reason[:45]}\") has resolved, improved, or recurred.")

    if not duration or duration.lower() in ("unknown", "not sure"):
        confirm_in_room.append("Confirm Duration/onset of current symptoms.")

    if medications and medications.lower() not in ("none", "none declared"):
        confirm_in_room.append("Current medicine adherence and dosage timing.")
    else:
        confirm_in_room.append("Clarify any over-the-counter or unlisted medications.")

    if any(w in sym_all for w in ["pain", "heaviness", "ache"]):
        confirm_in_room.append("Any pain at rest or nocturnal aggravation?")

    # Format into complete text card (Image 4 exact format!)
    raw_card_parts = [
        header,
        "",
        "TODAY",
        today_text,
        "",
        "RELEVANT HISTORY",
        "\n".join(f"- {b}" for b in history_bullets),
        "",
        "SAME COMPLAINT BEFORE",
        "\n".join(f"- {b}" for b in same_complaint_bullets)
    ]
    if red_flag_text:
        raw_card_parts.extend(["", "⚠️ RED FLAG", red_flag_text])
    raw_card_parts.extend(["", "CONFIRM IN ROOM", "\n".join(f"- {c}" for c in confirm_in_room)])

    raw_card_text = "\n".join(raw_card_parts)

    # 7. Lab categorization
    abnormal_labs = []
    normal_labs = []
    for l in labs:
        test = l.get("test", "Test")
        val = l.get("value", "")
        unit = l.get("unit", "")
        rng = l.get("reference_range", "")
        note = l.get("range_note", "")
        item_repr = {
            "test": test,
            "value": f"{val} {unit}".strip(),
            "reference_range": rng,
            "range_note": note,
            "source_line": l.get("source_line", "")
        }
        if note or "high" in str(l.get("source_line", "")).lower() or "low" in str(l.get("source_line", "")).lower():
            abnormal_labs.append(item_repr)
        else:
            normal_labs.append(item_repr)

    # Nurse vitals summary text for backward compatibility
    nurse_vitals_summary = []
    if vitals:
        if vitals.get("bp_systolic") and vitals.get("bp_diastolic"):
            nurse_vitals_summary.append(f"Blood Pressure: {vitals['bp_systolic']}/{vitals['bp_diastolic']} mmHg")
        if vitals.get("heart_rate"):
            nurse_vitals_summary.append(f"Heart Rate: {vitals['heart_rate']} bpm")
        if vitals.get("temperature"):
            nurse_vitals_summary.append(f"Temperature: {vitals['temperature']} °F" + (" (Febrile)" if float(vitals['temperature']) >= 100.4 else ""))
        if vitals.get("spo2"):
            nurse_vitals_summary.append(f"SpO2: {vitals['spo2']}%")
        if vitals.get("blood_sugar"):
            nurse_vitals_summary.append(f"Blood Sugar: {vitals['blood_sugar']} mg/dL")

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_mode": "evidence_linked_single_card",
        "disclaimer": "AI-Assisted Pre-Consultation Summary Card. Designed for 10-15s clinical situational awareness. Not for autonomous diagnosis.",
        "single_card": {
            "header": header,
            "today": today_text,
            "relevant_history": history_bullets,
            "same_complaint_before": same_complaint_bullets,
            "red_flag": red_flag_text,
            "confirm_in_room": confirm_in_room,
            "raw_text": raw_card_text
        },
        "patient_reported": {
            "reason_for_visit": reason,
            "symptoms_description": symptoms_text,
            "duration": duration or "Unspecified",
            "severity": severity or "Unspecified",
            "associated_symptoms": associated or "None",
            "chronic_conditions": conditions or "None",
            "current_medications": medications or "None",
            "known_allergies": allergies or "Not provided"
        },
        "nurse_vitals": nurse_vitals_summary or ["Vitals not yet recorded by nursing staff"],
        "lab_evidence": {
            "abnormal_results": abnormal_labs,
            "in_range_results": normal_labs,
            "total_extracted": len(labs)
        },
        "information_gaps": confirm_in_room,
        "concise_brief": today_text
    }
    return payload


def save_summary(visit_id, patient_id, summary_payload, db_path=None, conn=None):
    """Persist generated pre-consultation summary in database."""
    summary_id = f"SUM-{visit_id}"
    summary_json = json.dumps(summary_payload, indent=2)

    def _do_save(c):
        c.execute(
            """
            INSERT INTO summaries (summary_id, visit_id, patient_id, summary_json, model_mode)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(visit_id) DO UPDATE SET
                summary_json = excluded.summary_json,
                model_mode = excluded.model_mode,
                created_at = CURRENT_TIMESTAMP
            """,
            (summary_id, visit_id, patient_id, summary_json, summary_payload.get("model_mode", "single_card"))
        )
        log_audit("system", "summary_generated", patient_id, visit_id=visit_id, details="Single-card summary generated", conn=c)

    if conn is not None:
        _do_save(conn)
    else:
        with get_db(db_path) as c:
            _do_save(c)
    return summary_id
