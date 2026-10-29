"""Small server-side authentication service for the synthetic-data prototype."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from src.database.connection import get_db


PBKDF2_ITERATIONS = 210_000
STAFF_SESSION_HOURS = 8
PATIENT_SESSION_HOURS = 4


def _utc_now():
    return datetime.now(timezone.utc)


def _timestamp(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password, salt=None):
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (TypeError, ValueError):
        return False


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def seed_demo_staff(conn):
    """Create deterministic demo identities without replacing changed passwords."""
    accounts = (
        (
            "DR-SHARMA",
            "doctor.demo",
            "Dr. Sharma",
            "doctor",
            os.environ.get("CHAKSHU_DOCTOR_PASSWORD", "Doctor123!"),
        ),
        (
            "NURSE-ANITA",
            "nurse.demo",
            "Nurse Anita",
            "nurse",
            os.environ.get("CHAKSHU_NURSE_PASSWORD", "Nurse123!"),
        ),
    )
    for staff_id, username, display_name, role, password in accounts:
        conn.execute(
            """
            INSERT OR IGNORE INTO staff_users
                (staff_id, username, display_name, role, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (staff_id, username, display_name, role, hash_password(password)),
        )


def authenticate_staff(username, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM staff_users WHERE LOWER(username) = LOWER(?) AND active = 1",
            (username.strip(),),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return {
        "staff_id": row["staff_id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


def create_staff_session(staff_id):
    token = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(hours=STAFF_SESSION_HOURS)
    with get_db() as conn:
        conn.execute("DELETE FROM staff_sessions WHERE expires_at <= ?", (_timestamp(_utc_now()),))
        conn.execute(
            "INSERT INTO staff_sessions (token_hash, staff_id, expires_at) VALUES (?, ?, ?)",
            (_token_hash(token), staff_id, _timestamp(expires_at)),
        )
    return token, expires_at.isoformat()


def get_staff_session(token):
    if not token:
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.staff_id, u.username, u.display_name, u.role, s.expires_at
            FROM staff_sessions s
            JOIN staff_users u ON u.staff_id = s.staff_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1
            """,
            (_token_hash(token), _timestamp(_utc_now())),
        ).fetchone()
    return dict(row) if row else None


def revoke_staff_session(token):
    if token:
        with get_db() as conn:
            conn.execute("DELETE FROM staff_sessions WHERE token_hash = ?", (_token_hash(token),))


def create_patient_session(patient_id, visit_id):
    token = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(hours=PATIENT_SESSION_HOURS)
    with get_db() as conn:
        conn.execute("DELETE FROM patient_sessions WHERE expires_at <= ?", (_timestamp(_utc_now()),))
        conn.execute(
            """
            INSERT INTO patient_sessions (token_hash, patient_id, visit_id, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (_token_hash(token), patient_id, visit_id, _timestamp(expires_at)),
        )
    return token, expires_at.isoformat()


def get_patient_session(token):
    if not token:
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT patient_id, visit_id, expires_at
            FROM patient_sessions
            WHERE token_hash = ? AND expires_at > ?
            """,
            (_token_hash(token), _timestamp(_utc_now())),
        ).fetchone()
    return dict(row) if row else None
