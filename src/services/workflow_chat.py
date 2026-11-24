"""Gemini answers to fixed questions about the Chakshu workflow."""

import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import dotenv_values

from src.database.postgres import ROOT


TOPICS = {
    "intake": "Open Patient Check-in, register or verify the MRN, then complete the intake questions and select Save & Proceed to Report Upload.",
    "reports": "After saving intake, use the Reports step to upload a PDF or photo. Wait for the upload result, then select Finish Check-in.",
    "queue": "Sign in as nurse to record vitals or as doctor to open the visit queue and review a patient's intake and summary.",
    "records": "In the doctor workspace, open Patient Records and search by MRN or name. Select the patient to review their visit history.",
}


def workflow_answer(topic):
    settings = {**dotenv_values(ROOT / ".env"), **os.environ}
    key = settings.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini is not configured")
    model = quote(settings.get("GEMINI_MODEL") or "gemini-3.5-flash-lite", safe="")
    payload = {
        "contents": [{"parts": [{"text": (
            "Rewrite these Chakshu navigation directions as a friendly, concise answer. "
            "Keep the steps and labels accurate. Use plain text and only the information provided. "
            + TOPICS[topic]
        )}]}],
        "generationConfig": {"maxOutputTokens": 256},
    }
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urlopen(request, timeout=12) as response:
        data = json.load(response)
    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    answer = " ".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not answer:
        raise ValueError("Gemini returned an empty answer")
    return answer
