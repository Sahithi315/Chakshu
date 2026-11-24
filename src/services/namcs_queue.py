"""Replay NAMCS public-use encounters through the existing staff queues."""

import gzip
import logging
import os
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import dotenv_values

from src.database.connection import get_db

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "namcshc2024_stata.dta"
BUCKET = "namcs-datasets"
ARCHIVE = f"namcshc2024/{DATASET.name}.gz"
BATCH_SIZE = 4
INTERVAL_SECONDS = 3600
DEMO_PREFIX = "NAMCS-"
logger = logging.getLogger("uvicorn.error")


def storage_settings():
    server = dotenv_values(ROOT / ".env")
    frontend = dotenv_values(ROOT / "frontend" / ".env.local")
    url = os.environ.get("SUPABASE_URL") or server.get("SUPABASE_URL") or frontend.get("VITE_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or server.get("SUPABASE_SECRET_KEY")
    return url, key


def queue_source():
    server = dotenv_values(ROOT / ".env")
    source = os.environ.get("NAMCS_QUEUE_SOURCE", server.get("NAMCS_QUEUE_SOURCE") or "auto")
    if source not in {"auto", "live", "local", "supabase"}:
        raise ValueError("NAMCS_QUEUE_SOURCE must be auto, live, local, or supabase")
    if source == "auto":
        _, key = storage_settings()
        if key:
            return "supabase"
        return "local" if DATASET.is_file() else "live"
    return source


def download_archive():
    url, key = storage_settings()
    if not url or not key or not url.startswith("https://"):
        raise ValueError("Supabase queue requires an HTTPS project URL and server-side secret key")
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    request = Request(f"{url.rstrip('/')}/storage/v1/object/authenticated/{BUCKET}/{ARCHIVE}", headers=headers)
    with urlopen(request, timeout=30) as response:
        return gzip.decompress(response.read())


def load_encounters(dataset=DATASET):
    import pandas as pd

    rows = pd.read_stata(dataset, columns=["PUF_ID", "AGE", "SEX"], convert_categoricals=False)
    if rows.empty or rows["PUF_ID"].isna().any() or not rows["PUF_ID"].is_unique:
        raise ValueError("NAMCS dataset must contain unique, nonempty public-use visit IDs")
    return rows.sort_values("PUF_ID", ignore_index=True)


class NamcsReplay:
    def __init__(self, source):
        dataset = BytesIO(download_archive()) if source == "supabase" else DATASET
        self.rows = load_encounters(dataset)
        self.prefix = f"{DEMO_PREFIX}{uuid4().hex}-"
        self.source = source
        self.position = 0
        self.released = 0

    def advance(self):
        count = min(BATCH_SIZE, len(self.rows))
        positions = [(self.position + step) % len(self.rows) for step in range(count)]
        rows = self.rows.iloc[positions]
        encounters = []
        visits = []
        survey_ids = []
        for ordinal, (survey_id, age, sex) in enumerate(rows.itertuples(index=False, name=None), self.released + 1):
            survey_ids.append(int(survey_id))
            patient_id = f"{DEMO_PREFIX}{int(survey_id):06d}"
            visit_id = f"{self.prefix}{ordinal}"
            clean_age = int(age) if age == age and age >= 0 else None
            recorded_sex = {1: "Male", 2: "Female"}.get(sex)
            encounters.append((patient_id, "", f"NAMCS Visit {int(survey_id)}", clean_age, recorded_sex))
            visits.append((visit_id, patient_id, f"N{ordinal:03d}"))

        with get_db() as conn:
            conn.executemany(
                """INSERT INTO patients (patient_id, phone, name, age, gender)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(patient_id) DO UPDATE SET name=excluded.name, age=excluded.age, gender=excluded.gender""",
                encounters,
            )
            conn.executemany(
                "INSERT INTO visits (visit_id, patient_id, token_number) VALUES (?, ?, ?)",
                visits,
            )
        self.position = (self.position + len(visits)) % len(self.rows)
        self.released += len(visits)
        logger.info(
            "NAMCS replay %s released survey visits %s; next survey visit %s; total released %s",
            self.source, survey_ids, int(self.rows.at[self.position, "PUF_ID"]), self.released,
        )
