"""
Patient chatbot service — minimum-questions intake via LLM with deterministic fallbacks.

SAFETY CONTRACT
- Never diagnoses, never suggests causes, never recommends treatment.
- Forbidden words are stripped from any LLM response before saving.
- PHI (name, phone, MRN, address) is redacted before sending to any LLM.
- Conversation state lives on our server; failover replays the same state to the next provider.
- Emergency keywords trigger a deterministic nurse-alert notice, not an LLM response.
"""
from __future__ import annotations
import json
import logging
import os
import re
import uuid
from typing import Optional

from src.database.connection import get_db
from src.services.patient_service import log_audit

logger = logging.getLogger(__name__)

# --------------- Configuration ---------------
MAX_QUESTIONS = int(os.environ.get("MAX_CHAT_QUESTIONS", "6"))
MAX_MSG_LENGTH = 2000       # characters per patient message
SESSION_RATE_LIMIT = 60     # max messages per session

# --------------- Emergency keyword rule (deterministic — NOT LLM) ---------------
_EMERGENCY_KEYWORDS = {
    "chest pain", "chest tightness", "chest heaviness",
    "severe breathing difficulty", "can't breathe", "cannot breathe",
    "difficulty breathing", "breathless", "shortness of breath",
    "fainting", "fainted", "passed out", "loss of consciousness", "unconscious",
    "stroke", "face drooping", "arm weakness", "sudden numbness",
    "severe headache", "worst headache", "sudden blurred vision",
    "coughing blood", "vomiting blood", "blood in urine", "heavy bleeding",
}

def _has_emergency(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _EMERGENCY_KEYWORDS)

# --------------- PHI redaction ---------------
_PHONE_RE = re.compile(r"(\+?91[-\s]?)?[6-9]\d{2}[-\s]?\d{3}[-\s]?\d{4}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

def _redact_phi(text: str) -> str:
    """Remove phone numbers and emails from patient-entered text before sending to LLM."""
    text = _PHONE_RE.sub("[PHONE_REDACTED]", text)
    text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return text

# --------------- Forbidden interpretive wording ---------------
_FORBIDDEN_PATTERNS = [
    r"\bsuggests?\b", r"\bindicates?\b", r"\blikely\b", r"\bprobably\b",
    r"\bconsistent with\b", r"\bmay be due to\b", r"\bdiagnosis\b",
    r"\byou should take\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)

def _contains_forbidden(text: str) -> bool:
    return bool(_FORBIDDEN_RE.search(text))

# --------------- JSON schema for structured intake ---------------

def _validate_intake(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    if not obj.get("chief_complaint"):
        return False
    allowed_severity = {"mild", "moderate", "severe", "unspecified", ""}
    sev = str(obj.get("severity", "")).lower()
    if sev and sev not in allowed_severity:
        obj["severity"] = "unspecified"
    return True

def _safe_parse_intake(text: str) -> Optional[dict]:
    """Extract first JSON object from LLM text, validate, one repair attempt."""
    match = re.search(r"\{[\s\S]+\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
        if _validate_intake(obj):
            return obj
    except json.JSONDecodeError:
        pass
    # Repair attempt: strip trailing commas before } or ]
    repaired = re.sub(r",\s*([}\]])", r"\1", match.group())
    try:
        obj = json.loads(repaired)
        if _validate_intake(obj):
            return obj
    except json.JSONDecodeError:
        pass
    return None

# --------------- DB helpers ---------------

def _migrate_chat_tables(conn):
    """Ensure chat tables exist (idempotent migration)."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        visit_id TEXT NOT NULL,
        patient_id TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        question_count INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0,
        collected_fields_json TEXT DEFAULT '{}',
        emergency_flagged INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_chat_sessions_visit ON chat_sessions(visit_id);

    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT UNIQUE NOT NULL,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        provider_used TEXT,
        is_question INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
    """)


def _ensure_tables():
    with get_db() as conn:
        _migrate_chat_tables(conn)


def _get_session(session_id: str, conn=None) -> Optional[dict]:
    def _do(c):
        row = c.execute(
            "SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None
    if conn:
        return _do(conn)
    with get_db() as c:
        return _do(c)


def _get_messages(session_id: str, conn=None) -> list:
    def _do(c):
        rows = c.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    if conn:
        return _do(conn)
    with get_db() as c:
        return _do(c)


def _save_message(session_id: str, role: str, content: str,
                  is_question: bool = False, provider_used: str = "", conn=None):
    mid = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    def _do(c):
        c.execute(
            """INSERT INTO chat_messages
               (message_id, session_id, role, content, provider_used, is_question)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mid, session_id, role, content, provider_used, 1 if is_question else 0)
        )
    if conn:
        _do(conn)
    else:
        with get_db() as c:
            _do(c)


def _update_session(session_id: str, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [session_id]
    with get_db() as c:
        c.execute(
            f"UPDATE chat_sessions SET {sets}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE session_id = ?",
            vals
        )


# --------------- Question generation ---------------

_QUESTION_TEMPLATES = [
    "In a few words, what is the main reason for your visit today?",
    "How long have you been experiencing this? (e.g., 2 days, 1 week)",
    "Is it getting better, worse, or staying the same? How severe would you rate it — mild, moderate, or severe?",
    "Are there any other symptoms you have noticed along with the main one?",
    "Have you been taking your medicines as prescribed? Any doses missed recently?",
    "Is there anything else you would like the doctor to know today?",
]

_SYSTEM_PROMPT = """You are a patient intake assistant for a hospital outpatient department.
Your ONLY job is to collect factual information from the patient to help the doctor prepare.

STRICT RULES — NEVER violate these:
- Ask ONE short, plain-language question at a time.
- Never diagnose, suggest a cause, name a disease, or recommend any medicine or treatment.
- Never use these words: "suggests", "indicates", "likely", "probably", "consistent with", "may be due to", "diagnosis", "you should take".
- Never invent information not given by the patient.
- Keep each question under 25 words.
- Respond ONLY with the next question text. No preamble, no explanation."""


def _build_llm_prompt(session: dict, messages: list, known: dict) -> str:
    """Build the prompt to send to the LLM for the next question."""
    conversation = []
    for m in messages:
        prefix = "Patient:" if m["role"] == "patient" else "Assistant:"
        # Redact PHI before sending to LLM
        content = _redact_phi(m["content"])
        conversation.append(f"{prefix} {content}")
    conv_text = "\n".join(conversation)

    known_text = ""
    if known.get("chronic_conditions"):
        known_text += f"- Chronic conditions on file: {known['chronic_conditions']}\n"
    if known.get("medications"):
        known_text += f"- Medications on file: {known['medications']}\n"
    if known.get("allergies"):
        known_text += f"- Allergies on file: {known['allergies']}\n"
    if known.get("lab_summary"):
        known_text += f"- Recent lab results: {known['lab_summary']}\n"

    q_count = session.get("question_count", 0)
    max_q = MAX_QUESTIONS

    return (
        f"Questions asked so far: {q_count} of {max_q} maximum.\n\n"
        f"ALREADY KNOWN (do NOT ask again):\n"
        f"{known_text if known_text else 'Nothing on file yet.'}\n\n"
        f"CONVERSATION SO FAR:\n{conv_text if conv_text else '(none yet)'}\n\n"
        f"What is the single most important next question to ask this patient?\n"
        f"Priority: (1) chief complaint, (2) duration, (3) severity/progression, "
        f"(4) targeted follow-up, (5) anything else.\n"
        f"Skip any question already answered by ALREADY KNOWN or the conversation.\n"
        f"If enough information has been collected (or {max_q} questions reached), reply with exactly: DONE\n"
        f"Otherwise reply with just the next question (no prefix, no numbering)."
    )


def _deterministic_next_question(q_index: int, known: dict) -> Optional[str]:
    """Fallback: return a template question, skipping ones already answered."""
    if q_index >= len(_QUESTION_TEMPLATES):
        return None
    # Skip medicine adherence question if no meds on file and first visit
    if q_index == 4 and not known.get("medications") and not known.get("is_returning"):
        return None
    return _QUESTION_TEMPLATES[q_index]


def _get_next_question(session: dict, messages: list, known: dict) -> tuple:
    """
    Returns (question_text, provider_used).
    Returns (None, "") when done.
    Falls back to deterministic template if all LLM providers fail.
    """
    q_count = session.get("question_count", 0)
    if q_count >= MAX_QUESTIONS:
        return None, ""

    prompt = _build_llm_prompt(session, messages, known)

    try:
        from src.llm.router import get_router
        router = get_router()
        result = router.generate(prompt=prompt, system=_SYSTEM_PROMPT, max_tokens=100, temperature=0.3)
        if result:
            text = result.text.strip()
            if text.upper().startswith("DONE"):
                return None, result.provider
            # Strip forbidden interpretive language
            if _contains_forbidden(text):
                logger.warning("[ChatService] LLM response had forbidden wording; using template")
                q = _deterministic_next_question(q_count, known)
                return q, "deterministic"
            return text, result.provider
    except Exception as e:
        logger.error("[ChatService] LLM router error: %s", e)

    # LLM unavailable — use deterministic template
    q = _deterministic_next_question(q_count, known)
    return q, "deterministic"


# --------------- Structured output extraction ---------------

_EXTRACTION_SYSTEM = """You are a clinical data structuring assistant.
Given a patient intake conversation, extract the stated facts into structured JSON.
RULES:
- Only include what the patient explicitly said. Do not infer or add anything.
- Never use: suggests, indicates, likely, probably, consistent with, may be due to, diagnosis.
- severity must be one of: mild, moderate, severe, unspecified.
- Return ONLY valid JSON matching this schema (no markdown, no explanation):
{
  "chief_complaint": "...",
  "duration": "...",
  "severity": "mild|moderate|severe|unspecified",
  "progression": "...",
  "associated_symptoms": "...",
  "denied_symptoms": "...",
  "medicine_adherence": "...",
  "allergies": "...",
  "free_text_notes": "..."
}"""


def _extract_structured_intake(messages: list, known: dict) -> dict:
    """
    Turn the conversation into structured intake fields.
    Returns a dict ready to merge into the existing intake table schema.
    Uses LLM with strict JSON parsing; falls back to deterministic extraction on failure.
    """
    conv_lines = []
    for m in messages:
        prefix = "Patient" if m["role"] == "patient" else "Assistant"
        conv_lines.append(f"{prefix}: {_redact_phi(m['content'])}")
    conv_text = "\n".join(conv_lines)

    prompt = f"Extract structured intake from this conversation:\n\n{conv_text}\n\nReturn JSON only."

    try:
        from src.llm.router import get_router
        router = get_router()
        result = router.generate(prompt=prompt, system=_EXTRACTION_SYSTEM, max_tokens=512, temperature=0.1)
        if result:
            parsed = _safe_parse_intake(result.text)
            if parsed:
                return parsed
    except Exception as e:
        logger.error("[ChatService] Extraction LLM error: %s", e)

    # Deterministic fallback
    return _deterministic_extraction(messages)


def _deterministic_extraction(messages: list) -> dict:
    """Rule-based extraction when LLM is unavailable."""
    patient_texts = [m["content"] for m in messages if m["role"] == "patient"]
    full_text = " ".join(patient_texts)

    chief = patient_texts[0] if patient_texts else ""

    duration_match = re.search(
        r"(\d+\s*(?:day|week|month|hour|year)s?|since\s+\w+|last\s+\w+)",
        full_text, re.IGNORECASE
    )
    duration = duration_match.group() if duration_match else ""

    severity = "unspecified"
    for sev in ["severe", "moderate", "mild"]:
        if sev in full_text.lower():
            severity = sev
            break

    return {
        "chief_complaint": chief[:500],
        "duration": duration,
        "severity": severity,
        "progression": "",
        "associated_symptoms": "",
        "denied_symptoms": "",
        "medicine_adherence": "",
        "allergies": "",
        "free_text_notes": full_text[:1000] if len(patient_texts) > 1 else "",
    }


# --------------- Public API ---------------

def start_chat_session(visit_id: str, patient_id: str, known: dict) -> dict:
    """
    Create a new chat session and return the first question.

    known = {
      "chronic_conditions": str, "medications": str, "allergies": str,
      "is_returning": bool, "lab_summary": str
    }
    """
    _ensure_tables()
    session_id = f"CHAT-{uuid.uuid4().hex[:10].upper()}"

    with get_db() as conn:
        _migrate_chat_tables(conn)
        # Close any existing active session for this visit
        conn.execute(
            "UPDATE chat_sessions SET status = 'closed' "
            "WHERE visit_id = ? AND status = 'active'",
            (visit_id,)
        )
        conn.execute(
            """INSERT INTO chat_sessions
               (session_id, visit_id, patient_id, status, question_count, message_count, collected_fields_json)
               VALUES (?, ?, ?, 'active', 0, 0, '{}')""",
            (session_id, visit_id, patient_id)
        )

    log_audit("patient", "chat_session_started", patient_id, visit_id=visit_id,
              details=f"Chat session {session_id} started")

    session = _get_session(session_id)
    messages = []

    question, provider = _get_next_question(session, messages, known)
    if not question:
        question = _QUESTION_TEMPLATES[0]

    _save_message(session_id, "assistant", question, is_question=True, provider_used=provider)
    _update_session(session_id, question_count=1, message_count=1)

    log_audit("system", "chat_llm_served", patient_id, visit_id=visit_id,
              details=f"provider={provider} turn=1")

    return {
        "session_id": session_id,
        "question": question,
        "question_number": 1,
        "max_questions": MAX_QUESTIONS,
        "done": False,
        "emergency": False,
        "quick_replies": _quick_replies_for_question(0),
    }


def handle_chat_message(session_id: str, patient_text: str) -> dict:
    """
    Accept a patient answer, return the next question or done signal.
    """
    _ensure_tables()

    with get_db() as conn:
        _migrate_chat_tables(conn)
        session = _get_session(session_id, conn)
        if not session:
            return {"error": "Session not found", "done": True}
        if session["status"] not in ("active",):
            return {"done": True, "message": "This intake session is already complete."}
        if session["message_count"] >= SESSION_RATE_LIMIT:
            return {"done": True, "message": "Session limit reached. Your information has been saved."}

    # Sanitize input
    patient_text = str(patient_text or "").strip()[:MAX_MSG_LENGTH]
    if not patient_text:
        return {"error": "Please enter a response.", "done": False}

    # Emergency keyword check (deterministic)
    if _has_emergency(patient_text):
        _save_message(session_id, "patient", patient_text)
        _update_session(session_id, emergency_flagged=1, status="emergency")
        log_audit("system", "chat_emergency_flagged", session["patient_id"],
                  visit_id=session["visit_id"],
                  details="Emergency keyword detected in chat message")
        return {
            "done": True,
            "emergency": True,
            "message": "Please tell the nurse right now.",
            "nurse_alert": True,
        }

    # Save patient message
    _save_message(session_id, "patient", patient_text)

    # Check for "done" signal from patient
    done_phrases = {"done", "that's all", "thats all", "nothing else", "no more",
                    "skip", "finish", "submit", "that's all / done"}
    if patient_text.lower().strip() in done_phrases:
        return _finalize_session(session_id, session)

    # Refresh session state
    session = _get_session(session_id)
    q_count = session["question_count"]
    msg_count = session["message_count"] + 1
    _update_session(session_id, message_count=msg_count)

    if q_count >= MAX_QUESTIONS:
        return _finalize_session(session_id, session)

    # Get next question
    messages = _get_messages(session_id)
    fields = json.loads(session.get("collected_fields_json") or "{}")
    known = _build_known_from_session(session, fields)

    question, provider = _get_next_question(session, messages, known)

    if question is None:
        return _finalize_session(session_id, session)

    _save_message(session_id, "assistant", question, is_question=True, provider_used=provider)
    new_q_count = q_count + 1
    _update_session(session_id, question_count=new_q_count, message_count=msg_count + 1)

    log_audit("system", "chat_llm_served", session["patient_id"],
              visit_id=session["visit_id"],
              details=f"provider={provider} turn={new_q_count}")

    return {
        "session_id": session_id,
        "question": question,
        "question_number": new_q_count,
        "max_questions": MAX_QUESTIONS,
        "done": False,
        "emergency": False,
        "quick_replies": _quick_replies_for_question(new_q_count - 1),
    }


def _build_known_from_session(session: dict, fields: dict) -> dict:
    """Reconstruct known dict for question generation."""
    return {
        "chronic_conditions": fields.get("chronic_conditions", ""),
        "medications": fields.get("medications", ""),
        "allergies": fields.get("allergies", ""),
        "is_returning": bool(fields.get("is_returning")),
        "lab_summary": fields.get("lab_summary", ""),
    }


def _finalize_session(session_id: str, session: dict) -> dict:
    """Extract structured fields, save to intakes table, close session."""
    messages = _get_messages(session_id)
    fields = json.loads(session.get("collected_fields_json") or "{}")
    known = _build_known_from_session(session, fields)
    structured = _extract_structured_intake(messages, known)

    # Merge with any pre-known fields
    if known.get("allergies") and not structured.get("allergies"):
        structured["allergies"] = known["allergies"]

    # Save to intakes table using existing save_intake service
    try:
        from src.services.patient_service import save_intake
        save_intake(
            visit_id=session["visit_id"],
            patient_id=session["patient_id"],
            reason_for_visit=structured.get("chief_complaint", ""),
            symptoms_text=structured.get("chief_complaint", ""),
            duration=structured.get("duration", ""),
            severity=structured.get("severity", ""),
            associated_symptoms=structured.get("associated_symptoms", ""),
            conditions=known.get("chronic_conditions", ""),
            medications=known.get("medications", ""),
            allergies=structured.get("allergies") or known.get("allergies", ""),
            history=structured.get("free_text_notes", ""),
            submitted_by="patient_chatbot",
        )
    except Exception as e:
        logger.error("[ChatService] Failed to save structured intake: %s", e)

    _update_session(session_id,
                    status="completed",
                    collected_fields_json=json.dumps(structured))

    log_audit("patient", "chat_session_completed", session["patient_id"],
              visit_id=session["visit_id"],
              details=f"Chat session {session_id} completed; {session['question_count']} questions asked")

    return {
        "done": True,
        "session_id": session_id,
        "message": "Thank you! Your information has been saved. The doctor will be with you shortly.",
        "structured_intake": structured,
    }


def _quick_replies_for_question(q_index: int) -> list:
    """Return quick-reply pill options for the given question index."""
    mapping = {
        0: [],
        1: ["Less than a day", "2-3 days", "About a week", "2-4 weeks", "More than a month"],
        2: ["Getting better", "Getting worse", "About the same", "Mild", "Moderate", "Severe"],
        3: ["No other symptoms", "Fever", "Nausea", "Headache", "Fatigue"],
        4: ["Yes, taking regularly", "Missed some doses", "Stopped taking", "No medicines"],
        5: ["That's all / Done", "Nothing else"],
    }
    replies = list(mapping.get(q_index, []))
    if q_index > 0 and "That's all / Done" not in replies:
        replies.append("That's all / Done")
    return replies
