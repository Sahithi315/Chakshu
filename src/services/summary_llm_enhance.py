"""
LLM-enhanced summary generation with strict output validation.
Only phrases bullets from provided facts. Every bullet must have source_ids.
Deterministic abnormal-value section is built in abnormal_flags.py.
"""
from __future__ import annotations
import copy
import json
import logging
import re
from typing import Optional

from src.services.abnormal_flags import flag_abnormal_labs, compute_lab_trends

logger = logging.getLogger(__name__)

# Hard safety forbidden wording
_FORBIDDEN_PATTERNS = [
    r"\bsuggests?\b",
    r"\bindicates?\b",
    r"\blikely\b",
    r"\bprobably\b",
    r"\bconsistent with\b",
    r"\bmay be due to\b",
    r"\bdiagnosis\b",
    r"\byou should take\b",
    r"\bdose[ -]change\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)

# Pattern for medicine-like tokens
_MEDICINE_SUFFIXES = re.compile(
    r"\b[a-zA-Z]{3,}(?:statin|pril|sartan|cillin|mycin|olol|dipine|prazole|formin|gliflozin|gliptin|mab|tide|zide|pam|lam|xacin|profen|cetamol|aspirin|paracetamol|metformin|insulin|atorvastatin|amlodipine|losartan|enalapril|pantoprazole|omeprazole)\b",
    re.IGNORECASE,
)

_SUMMARY_SYSTEM = """You are a clinical documentation assistant.
Your ONLY job is to phrase short bullet points from the supplied facts for a doctor pre-consultation card.

STRICT RULES — NEVER violate:
1. Only state facts explicitly present in the INPUT FACTS. Never add, infer, or interpret.
2. Never use: "suggests", "indicates", "likely", "probably", "consistent with", "may be due to", "diagnosis", "you should take", or dose-change advice.
3. Every bullet MUST end with a source_id reference in brackets, e.g. [intake_1], [vitals_1], [lab_3].
4. Keep each bullet under 20 words.
5. Return ONLY a JSON object with keys: today_bullets, history_bullets, same_complaint_bullets, confirm_bullets.
   Each key maps to a list of strings.
6. Do NOT include an abnormal_values section — that is handled separately."""


def _extract_allowed_facts(input_facts: dict) -> tuple[set[str], set[str], set[str]]:
    """Extract sets of allowed numbers, dates, and medicine words from input facts."""
    facts_str = json.dumps(input_facts)

    # Allowed numbers
    allowed_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", facts_str))

    # Allowed dates (e.g. 2026-10-15)
    allowed_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", facts_str))

    # Allowed medicine words (words in input facts in lowercase)
    allowed_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", facts_str)}

    return allowed_numbers, allowed_dates, allowed_words


def _validate_llm_summary(text: str, fact_ids: set, input_facts: dict) -> Optional[dict]:
    """
    Parse LLM output. Reject if:
    - Contains forbidden interpretive wording
    - Any bullet has no valid source_id
    - Any number in generated text does not exist in input facts
    - Any medicine name in generated text does not exist in input facts
    Returns parsed dict or None.
    """
    if _FORBIDDEN_RE.search(text):
        logger.warning("[SummaryLLM] Forbidden wording detected in LLM output, rejecting")
        return None

    # Extract JSON
    match = re.search(r"\{[\s\S]+\}", text)
    if not match:
        return None
    raw_json = match.group()
    try:
        obj = json.loads(raw_json)
    except json.JSONDecodeError:
        # Repair: strip trailing commas
        repaired = re.sub(r",\s*([}\]])", r"\1", raw_json)
        try:
            obj = json.loads(repaired)
        except json.JSONDecodeError:
            return None

    expected_keys = {"today_bullets", "history_bullets", "same_complaint_bullets", "confirm_bullets"}
    if not expected_keys.issubset(obj.keys()):
        return None

    # Validate each bullet has at least one valid source_id
    source_id_re = re.compile(r"\[([^\]]+)\]")
    all_bullets = []
    for key in expected_keys:
        for bullet in obj.get(key, []):
            all_bullets.append((key, bullet))

    allowed_numbers, allowed_dates, allowed_words = _extract_allowed_facts(input_facts)

    for key, bullet in all_bullets:
        ids = source_id_re.findall(bullet)
        if not ids:
            logger.warning("[SummaryLLM] Bullet missing source_id: %r", bullet[:60])
            return None
        if not any(sid in fact_ids for sid in ids):
            logger.warning("[SummaryLLM] Bullet has no valid source_id: %r", bullet[:60])
            return None

        # Check for forbidden wording in bullet
        if _FORBIDDEN_RE.search(bullet):
            logger.warning("[SummaryLLM] Bullet contains forbidden wording: %r", bullet[:60])
            return None

        # Strip source tags before checking numbers and tokens
        stripped = source_id_re.sub("", bullet)

        # Validate numbers: every number in stripped text must be in allowed_numbers
        bullet_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", stripped)
        for num in bullet_numbers:
            if num not in allowed_numbers:
                logger.warning("[SummaryLLM] Bullet contains invented number %r not in facts: %r", num, bullet[:60])
                return None

        # Validate medicine names: any medicine-like term must be in allowed_words
        med_matches = _MEDICINE_SUFFIXES.findall(stripped)
        for med in med_matches:
            if med.lower() not in allowed_words:
                logger.warning("[SummaryLLM] Bullet contains invented medicine %r not in facts: %r", med, bullet[:60])
                return None

    return obj


def _build_facts(intake: dict, vitals: dict, labs: list, history: list) -> tuple[dict, set]:
    """
    Build a structured fact dictionary with IDs for the LLM to reference.
    Returns (facts_dict, fact_id_set).
    """
    facts = {}
    ids = set()

    if intake:
        facts["intake_1"] = {
            "type": "intake",
            "chief_complaint": intake.get("reason_for_visit") or intake.get("symptoms_text", ""),
            "duration": intake.get("duration", ""),
            "severity": intake.get("severity", ""),
            "associated": intake.get("associated_symptoms", ""),
            "conditions": intake.get("medical_conditions", ""),
            "medications": intake.get("current_medications", ""),
            "allergies": intake.get("known_allergies", ""),
        }
        ids.add("intake_1")

    if vitals:
        facts["vitals_1"] = {
            "type": "vitals",
            "bp": f"{vitals.get('bp_systolic','')}/{vitals.get('bp_diastolic','')} mmHg" if vitals.get("bp_systolic") else "",
            "hr": f"{vitals.get('heart_rate','')} bpm" if vitals.get("heart_rate") else "",
            "temp": f"{vitals.get('temperature','')} F" if vitals.get("temperature") else "",
            "spo2": f"{vitals.get('spo2','')}%" if vitals.get("spo2") else "",
            "bsugar": f"{vitals.get('blood_sugar','')} mg/dL" if vitals.get("blood_sugar") else "",
        }
        ids.add("vitals_1")

    for i, lab in enumerate(labs[:10]):
        fid = f"lab_{i+1}"
        facts[fid] = {
            "type": "lab",
            "test": lab.get("test_name") or lab.get("test", ""),
            "value": lab.get("test_value") or lab.get("value", ""),
            "unit": lab.get("unit", ""),
            "range": lab.get("reference_range", ""),
        }
        ids.add(fid)

    for i, visit in enumerate(history[:3]):
        fid = f"prior_{i+1}"
        v_intake = visit.get("intake") or {}
        v_notes = visit.get("doctor_notes") or {}
        facts[fid] = {
            "type": "prior_visit",
            "date": str(visit.get("created_at", ""))[:10],
            "complaint": v_intake.get("reason_for_visit") or v_intake.get("symptoms_text", ""),
            "plan": v_notes.get("plan", ""),
            "exam": v_notes.get("clinical_notes", ""),
        }
        ids.add(fid)

    return facts, ids


def build_deterministic_template_summary(
    base_summary: dict,
    intake: dict,
    vitals: dict,
    labs: list,
    history: list,
) -> dict:
    """Fallback: build short bullet points deterministically directly from the facts."""
    result = copy.deepcopy(base_summary)
    sc = result.get("single_card", {})

    today_bullets = []
    reason = (intake.get("reason_for_visit") or intake.get("symptoms_text") or "").strip()
    duration = (intake.get("duration") or "").strip()
    severity = (intake.get("severity") or "").strip()
    associated = (intake.get("associated_symptoms") or "").strip()
    if reason:
        b = f"Reason: {reason}"
        if duration:
            b += f" for {duration}"
        if severity:
            b += f" ({severity})"
        today_bullets.append(f"{b} [intake_1]")
    if associated:
        today_bullets.append(f"Associated symptoms: {associated} [intake_1]")
    if vitals:
        v_parts = []
        if vitals.get("bp_systolic") and vitals.get("bp_diastolic"):
            v_parts.append(f"BP {vitals['bp_systolic']}/{vitals['bp_diastolic']} mmHg")
        if vitals.get("heart_rate"):
            v_parts.append(f"HR {vitals['heart_rate']} bpm")
        if vitals.get("temperature"):
            v_parts.append(f"Temp {vitals['temperature']} F")
        if vitals.get("spo2"):
            v_parts.append(f"SpO2 {vitals['spo2']}%")
        if vitals.get("blood_sugar"):
            v_parts.append(f"Sugar {vitals['blood_sugar']} mg/dL")
        if v_parts:
            today_bullets.append(f"Vitals: {', '.join(v_parts)} [vitals_1]")

    history_bullets = []
    cond = (intake.get("medical_conditions") or "").strip()
    meds = (intake.get("current_medications") or "").strip()
    allergies = (intake.get("known_allergies") or "").strip()
    if cond and cond.lower() not in ("none", "none declared"):
        history_bullets.append(f"Conditions: {cond} [intake_1]")
    if meds and meds.lower() not in ("none", "none declared"):
        history_bullets.append(f"Medications: {meds} [intake_1]")
    if allergies and allergies.lower() not in ("none", "not provided", "unknown"):
        history_bullets.append(f"Allergies: {allergies} [intake_1]")

    same_complaint_bullets = []
    for i, pv in enumerate(history[:3]):
        fid = f"prior_{i+1}"
        p_date = str(pv.get("created_at", ""))[:10]
        p_in = pv.get("intake") or {}
        p_complaint = p_in.get("reason_for_visit") or p_in.get("symptoms_text") or "Consultation"
        same_complaint_bullets.append(f"{p_date}: {p_complaint} [{fid}]")

    confirm_bullets = list(sc.get("confirm_in_room") or [])
    confirm_bullets_with_ids = [
        f"{c} [intake_1]" if not re.search(r"\[[^\]]+\]", c) else c
        for c in confirm_bullets
    ]

    sc["today_llm_bullets"] = today_bullets
    sc["history_llm_bullets"] = history_bullets
    sc["same_complaint_llm_bullets"] = same_complaint_bullets
    sc["confirm_llm_bullets"] = confirm_bullets_with_ids
    result["single_card"] = sc
    return result


def enhance_summary_with_llm(
    base_summary: dict,
    intake: dict,
    vitals: dict,
    labs: list,
    history: list,
) -> dict:
    """
    Augment the deterministic summary with:
    1. Deterministic abnormal-value section (always from code, never LLM).
    2. LLM-phrased bullets (with source_ids) — or deterministic template fallback.
    Returns updated summary dict.
    """
    result = copy.deepcopy(base_summary)

    # --- DETERMINISTIC: Abnormal values section (Rule B.3) ---
    all_labs = list(labs)
    prior_labs = []
    for visit in history[:1]:
        prior_labs.extend(visit.get("extracted_results") or [])

    flagged = flag_abnormal_labs(all_labs)
    trends = compute_lab_trends(all_labs, prior_labs)

    trend_map: dict[str, dict] = {}
    for t in trends:
        trend_map[t["test_name"].strip().lower()] = t

    abnormal_section = []
    abnormal_card_bullets = []
    for item in flagged:
        if item["is_abnormal"]:
            test_key = item["test_name"].strip().lower()
            trend = trend_map.get(test_key)
            entry = {
                "test_name": item["test_name"],
                "value": item["value"],
                "unit": item["unit"],
                "reference_range": item["reference_range"],
                "flag": item["flag"],
                "report_date": item["report_date"],
                "report_id": item["report_id"],
                "source_line": item["source_line"],
            }
            change_str = ""
            if trend:
                entry["previous_value"] = trend["previous_value"]
                entry["current_value"] = trend["current_value"]
                entry["delta"] = trend["delta"]
                entry["trend_direction"] = trend["direction"]
                change_str = f" ({trend['previous_value']} -> {trend['current_value']})"

            bullet = f"{item['test_name']} {item['value']} {item['unit']} (Ref: {item['reference_range']}, {item['flag']}) [Date: {item['report_date']} / Report: {item['report_id']}]{change_str}"
            abnormal_section.append(entry)
            abnormal_card_bullets.append(bullet)

    result["abnormal_values"] = abnormal_section
    result["all_lab_flags"] = flagged

    # Include abnormal_values in single_card and update raw_text
    sc = result.get("single_card", {})
    sc["abnormal_values"] = abnormal_card_bullets

    raw_card_parts = [
        sc.get("header", ""),
        "",
        "TODAY",
        sc.get("today", ""),
        "",
        "RELEVANT HISTORY",
        "\n".join(f"- {b}" for b in (sc.get("relevant_history") or [])),
        "",
        "SAME COMPLAINT BEFORE",
        "\n".join(f"- {b}" for b in (sc.get("same_complaint_before") or [])),
        "",
        "ABNORMAL VALUES",
        "\n".join(f"- {b}" for b in abnormal_card_bullets) if abnormal_card_bullets else "- No abnormal lab values detected.",
    ]
    if sc.get("red_flag"):
        raw_card_parts.extend(["", "⚠️ RED FLAG", sc.get("red_flag")])
    raw_card_parts.extend(["", "CONFIRM IN ROOM", "\n".join(f"- {c}" for c in (sc.get("confirm_in_room") or []))])
    sc["raw_text"] = "\n".join(raw_card_parts)
    result["single_card"] = sc

    # --- LLM: Phrased bullets with source_ids (Rule B.4 & B.5) ---
    facts, fact_ids = _build_facts(intake, vitals, labs, history)
    facts_json = json.dumps(facts, indent=2)

    llm_bullets = None
    provider_used = "deterministic"
    fallback_used = True

    try:
        from src.llm.router import get_router
        router = get_router()
        prompt = (
            "INPUT FACTS (use ONLY these for bullets, reference by ID in brackets):\n"
            f"{facts_json}\n\n"
            "Generate a JSON summary with keys: today_bullets, history_bullets, same_complaint_bullets, confirm_bullets.\n"
            "Each bullet must end with the fact ID(s) it came from, e.g. [intake_1].\n"
            "Return JSON only."
        )

        def _val_cb(res):
            parsed = _validate_llm_summary(res.text, fact_ids, facts)
            return parsed is not None

        llm_result = router.generate(
            prompt=prompt,
            system=_SUMMARY_SYSTEM,
            max_tokens=600,
            temperature=0.2,
            validator=_val_cb,
        )
        if llm_result:
            validated = _validate_llm_summary(llm_result.text, fact_ids, facts)
            if validated:
                llm_bullets = validated
                provider_used = llm_result.provider
                fallback_used = False
    except Exception as e:
        logger.error("[SummaryLLM] LLM error: %s", e)

    if llm_bullets:
        sc["today_llm_bullets"] = llm_bullets.get("today_bullets", [])
        sc["history_llm_bullets"] = llm_bullets.get("history_bullets", [])
        sc["same_complaint_llm_bullets"] = llm_bullets.get("same_complaint_bullets", [])
        sc["confirm_llm_bullets"] = llm_bullets.get("confirm_bullets", [])
        result["single_card"] = sc
    else:
        result = build_deterministic_template_summary(result, intake, vitals, labs, history)
        provider_used = "deterministic"
        fallback_used = True

    result["generated_by"] = provider_used
    result["fallback_used"] = fallback_used

    return result
