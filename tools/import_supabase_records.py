"""Import the enriched NAMCS archive and optionally migrate local hospital records."""

import argparse
import csv
import gzip
import json
from itertools import islice
from pathlib import Path
import sqlite3
import sys
import zlib
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database.postgres import Database, connect, database_url
from src.database.schema import init_postgres

ARCHIVE = ROOT / "output" / "namcshc2024_with_diagnosis_explanations.csv.gz"
LOCAL_DB = ROOT / "data" / "hospital.db"
CLINICAL_TABLES = (
    "patients", "visits", "intakes", "vitals", "reports", "extracted_results",
    "extracted_medications", "document_findings", "summaries", "doctor_reviews",
    "doctor_notes", "nurse_queue_completions", "audit_logs",
)


def migrate_local(source):
    from psycopg import sql

    with closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as local, connect() as remote:
        local.row_factory = sqlite3.Row
        local.execute("BEGIN")
        db = Database(remote)
        db.lock(408011)
        db.execute("LOCK TABLE patients IN SHARE ROW EXCLUSIVE MODE")
        if db.execute("SELECT EXISTS (SELECT 1 FROM patients) AS occupied").fetchone()["occupied"]:
            raise RuntimeError("Migrate local records before writing clinical records to the Supabase database.")
        existing = {row[0] for row in local.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in CLINICAL_TABLES:
            if table not in existing:
                continue
            rows = local.execute(f"SELECT * FROM {table} ORDER BY id")
            columns = [field[0] for field in rows.description if field[0] != "id"]
            legacy_medications = table == "extracted_medications" and "med_id" not in columns
            if legacy_medications:
                columns.append("med_id")
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
            with remote.cursor() as cursor:
                for row in rows:
                    values = [row[column] for column in (columns[:-1] if legacy_medications else columns)]
                    if legacy_medications:
                        old_id = row["medication_id"] if "medication_id" in row.keys() else None
                        values.append(old_id or f"LEGACY-MED-{row['id']}")
                    if table == "reports":
                        path = Path(row["storage_path"])
                        if not path.is_file():
                            raise RuntimeError(f"Local attachment {row['report_id']} is missing; no records were copied.")
                        values[columns.index("storage_path")] = ""
                    cursor.execute(query, values)
                    if table == "reports":
                        db.execute("INSERT INTO report_files (report_id, content) VALUES (?, ?)",
                                   (row["report_id"], path.read_bytes()))


def import_archive(source):
    with gzip.open(source, "rt", encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        required = {"PUF_ID", "AGE", "SEX", "MONTH", "YEAR"}
        required.update(f"DX{i}{suffix}" for i in range(1, 31) for suffix in ("", "_LABEL", "_EXPLANATION"))
        required.update(f"DX_TYPE{i}" for i in range(1, 31))
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("Archive is missing diagnosis codes, labels, types, or explanations.")
        count = last_id = 0
        while batch := list(islice(rows, 20_000)):
            with connect() as remote:
                db = Database(remote)
                db.lock(408014)
                db.execute("CREATE TEMP TABLE namcs_import (LIKE namcs_archive) ON COMMIT DROP")
                with remote.cursor().copy("COPY namcs_import FROM STDIN WITH (FORMAT BINARY)") as writer:
                    writer.set_types(["int4", "bytea"])
                    for row in batch:
                        record = {key: value for key, value in row.items() if value != ""}
                        survey_id = int(record["PUF_ID"])
                        if survey_id <= last_id:
                            raise ValueError("Archive visit IDs must be unique and in ascending order.")
                        last_id = survey_id
                        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                        writer.write_row((survey_id, zlib.compress(payload, level=3)))
                db.execute("""
                    INSERT INTO namcs_archive (survey_id, record)
                    SELECT survey_id, record FROM namcs_import
                    ON CONFLICT (survey_id) DO UPDATE SET record = excluded.record
                    WHERE namcs_archive.record IS DISTINCT FROM excluded.record
                """)
            count += len(batch)
            print(f"Committed {count:,} NAMCS encounters.", flush=True)
        if not count:
            raise ValueError("Archive contains no encounters")
    print(f"Imported {count:,} NAMCS encounters into Supabase PostgreSQL.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--migrate-local", type=Path, nargs="?", const=LOCAL_DB)
    args = parser.parse_args()
    if not database_url():
        parser.exit(1, "Set the server-side SUPABASE_DB_URL before importing records.\n")
    if not args.archive.is_file():
        parser.exit(1, "The enriched NAMCS dataset is missing. Run tools/enrich_namcs_diagnoses.py first.\n")
    init_postgres()
    import_archive(args.archive)
    if args.migrate_local:
        migrate_local(args.migrate_local)
        print("Migrated saved local patient records and attachments.")


if __name__ == "__main__":
    main()
