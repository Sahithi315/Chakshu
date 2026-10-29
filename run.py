
"""Root launcher for Team 404 Vision: AI-Assisted Hospital Pre-Consultation Platform.

Starts the Starlette ASGI backend and serves the compiled React + Vite frontend.

Usage:
    python run.py

On your laptop:
    http://127.0.0.1:8000

For another device on the same reachable network:
    http://<YOUR_LAPTOP_IP>:8000
"""

from pathlib import Path
import subprocess
import sys
import uvicorn

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.schema import init_db
from src.database.seed import seed_database


def main():
    print("=" * 70)
    print("  TEAM 404 VISION: AI-ASSISTED HOSPITAL PRE-CONSULTATION PLATFORM")
    print("=" * 70)

    # 1. Initialize SQLite database
    print("[1/3] Initializing persistent hospital database...")
    init_db()
    seed_database()
    db_file = ROOT / "data" / "hospital.db"
    print(f"      Database ready at: {db_file.resolve()}")

    # 2. Check the compiled React frontend
    dist_dir = ROOT / "frontend" / "dist"
    src_dir = ROOT / "frontend" / "src"

    needs_build = not dist_dir.exists() or not (dist_dir / "index.html").exists()
    if not needs_build and src_dir.exists():
        dist_mtime = (dist_dir / "index.html").stat().st_mtime
        for src_file in src_dir.rglob("*"):
            if src_file.is_file() and src_file.stat().st_mtime > dist_mtime:
                needs_build = True
                break

    if needs_build:
        print("[2/3] Building updated Vite + React frontend bundle...")
        frontend_dir = ROOT / "frontend"

        try:
            subprocess.run(
                ["npm.cmd", "run", "build"],
                cwd=str(frontend_dir),
                check=True,
            )
            print("      Frontend build completed successfully.")
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            print(f"      WARNING: Could not build the frontend: {error}")
            print("      Run 'cd frontend && npm.cmd run build' manually.")
            return
    else:
        print("[2/3] Found up-to-date compiled frontend at frontend/dist.")

    # 3. Launch the server on all network interfaces
    print("[3/3] Starting server on http://0.0.0.0:8000")
    print()
    print("  On this laptop: http://localhost:8000")
    print("  On your phone:  http://<YOUR_LAPTOP_IP>:8000")
    print()
    print("  Features:")
    print("    - Short Permanent Patient ID (MRN, e.g. P10482) & check-in")
    print("    - Returning patient verified check-in & past records prefill")
    print("    - Dedicated Patient Records & Medical History Archive")
    print("    - Physical report camera scan & multi-page document upload")
    print("    - 10-15s Single clinical summary card (Image 4 design)")
    print("    - Doctor dashboard with live search & consultation notes")
    print("    - Nurse triage station for vitals measurement")
    print()
    print("  Press CTRL+C to stop the server.")
    print()

    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
