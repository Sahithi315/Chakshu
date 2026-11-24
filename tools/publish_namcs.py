"""Publish the complete Stata dataset to private Supabase Storage."""

import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.namcs_queue import ARCHIVE, BUCKET, DATASET, load_encounters, storage_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Print the local queue without uploading")
    args = parser.parse_args()

    if args.preview:
        print(load_encounters().head(4).to_string(index=False))
        return

    url, key = storage_settings()
    if not url or not url.startswith("https://") or not key:
        parser.exit(1, "Configure SUPABASE_URL and SUPABASE_SECRET_KEY in the server environment or root .env.\n")

    from supabase import create_client
    storage = create_client(url, key).storage
    if not any(bucket.id == BUCKET for bucket in storage.list_buckets()):
        storage.create_bucket(BUCKET, options={"public": False})
    bucket = storage.get_bucket(BUCKET)
    if bucket.public:
        parser.exit(1, f"The {BUCKET} bucket must be private.\n")

    objects = storage.from_(BUCKET)
    with TemporaryDirectory() as directory:
        archive = Path(directory) / f"{DATASET.name}.gz"
        with DATASET.open("rb") as source, gzip.open(archive, "wb", compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        checksum = hashlib.sha256(archive.read_bytes()).digest()
        objects.upload(ARCHIVE, archive, {"content-type": "application/gzip", "upsert": "true"})
        if hashlib.sha256(objects.download(ARCHIVE)).digest() != checksum:
            raise RuntimeError("Supabase archive checksum did not match the uploaded file")
    print(f"Verified {BUCKET}/{ARCHIVE}")


if __name__ == "__main__":
    main()
