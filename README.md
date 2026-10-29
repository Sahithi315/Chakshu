# Team 404 Vision: AI-Assisted Hospital Pre-Consultation Platform

> **Clinical Disclaimer**: Prototype for documentation and preparation assistance only. Synthetic data used. **This platform must never independently diagnose patients, prescribe medication, or replace clinical judgment.**

---

## 1. Overview & Vision

In hospital outpatient departments (OPDs), doctors typically have only 3–5 minutes per patient. Much of that time is lost asking repetitive intake questions, deciphering crumpled paper lab reports, or searching through unorganized records.

The **Team 404 Vision Clinical Context Platform** converts the patient's waiting room time (after receiving an OPD token) into a high-yield, structured pre-consultation summary:
- **Mobile-First Patient Intake**: Patients enter their reason for visit, symptom timeline, chronic conditions, current medications, and known allergies.
- **Physical Report Scanning & Document Upload**: Upload lab reports (PDF, JPG, PNG) via file selection or direct mobile camera capture.
- **Automated Clinical Data Extraction & Optional OCR**: Extracts lab test names, observed values, units, reference ranges, and out-of-range parameters. Digital PDFs use `pdfplumber`; photos and scanned PDFs use Tesseract when it is installed.
- **10–15 Second Single Summary Card**: Deterministically synthesized clinical card adhering to the exact clinician-oriented layout (TODAY, RELEVANT HISTORY, SAME COMPLAINT BEFORE, RED FLAG, CONFIRM IN ROOM).
- **Doctor Dashboard with Live Patient Search**: Search any patient instantly by Name, Phone, MRN (Patient ID), or Token number.
- **Clean Laboratory Review**: Structured tabular view of patient lab results without distraction (no inspect report modal).
- **Doctor Consultation Notes & Plan**: Direct clinical observation entry and treatment plan recording saved permanently to the patient's record.
- **Nurse Station**: Triage station for staff-assisted check-in and vital signs recording (BP, Pulse, Temp, SpO2, Blood Sugar).

---

## AI and Intelligent Automation Used

Chakshu does **not** call an external generative-AI API at runtime, and it does not require OpenAI, Anthropic, Gemini, or similar API keys. Its intelligent features are local, reviewable, and deliberately non-autonomous:

| Capability | Implementation | Safety boundary |
| :--- | :--- | :--- |
| Symptom and negation extraction | ModernBERT-compatible token-classification interface with a local rule-based fallback; the current demo runs in `baseline` mode when no trained checkpoint is installed | Extracts keywords, duration, severity, and negation for clinician review; it does not diagnose |
| Temporal reasoning | Deterministic comparison of the current complaint, duration, vital signs, prior visits, and follow-up history | Surfaces chronology and change; it does not predict disease or outcome |
| Clinical brief synthesis | Evidence-linked, deterministic structured summary built from patient intake, nurse vitals, reports, and history | Not a generative-LLM diagnosis or treatment recommendation |
| Prescription safety assistant | Transparent local rules check incomplete directions, duplicate medicines, recorded allergy terms, and a small documented interaction ruleset | Warns the doctor but never adds, removes, or changes a medicine automatically |
| Report understanding and OCR | `pdfplumber` for text PDFs, optional Tesseract OCR plus image preprocessing for photos/scanned PDFs, followed by structured lab parsing | Missing OCR is reported explicitly; the system does not invent report values |
| Red-flag highlighting | Explicit, auditable combinations of symptoms and observations | Attention prompt only; final interpretation remains with clinical staff |

The active capabilities are exposed by the health endpoint:

```bash
curl http://127.0.0.1:8000/api/health
```

On the current development machine, the response reports `"model_mode":"baseline"` and `"tesseract_available":false`. Install the Tesseract executable to enable OCR for image-only reports; digitally generated PDFs continue to be parsed without it.

---

## 2. Architecture & Tech Stack

```
Team_404-Vision/
├── frontend/                      # Modern Vite + React 19 Frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx         # Role-aware card navigation and session actions
│   │   │   ├── DoctorDashboard.jsx# Live patient search, tokens, summary card, clean labs, doctor notes
│   │   │   ├── PatientRecords.jsx # Complete longitudinal visit history, labs & report archive
│   │   │   ├── SummaryCard.jsx    # Single summary card (10-15s read) with copy button
│   │   │   ├── PatientIntake.jsx  # 2-option intake (New MRN vs Returning Check-in) & camera upload
│   │   │   └── NurseStation.jsx   # OPD triage queue & vitals measurement recording
│   │   ├── App.jsx                # URL routes, role boundary, and protected pages
│   │   ├── main.jsx               # React entry point
│   │   └── index.css              # Image 5 theme: soft blue #edf4fa, rounded cards, pills
│   ├── dist/                      # Compiled production static bundle
│   ├── package.json               # React 19, Lucide icons, Vite
│   └── vite.config.js             # Vite configuration with proxy to port 8000
├── app/
│   ├── server.py                  # High-performance Starlette ASGI backend & REST API
│   └── app.py                     # Launcher / Streamlit dual-compatibility
├── src/
│   ├── database/
│   │   ├── schema.py              # SQLite relational schema, indexing, WAL mode
│   │   ├── connection.py          # Database connection manager with transaction safety
│   │   └── seed.py                # Synthetic patient database seeder
│   ├── services/
│   │   ├── auth_service.py        # Staff sessions, password verification, and role checks
│   │   ├── summary_service.py     # Deterministic brief and temporal context generator
│   │   ├── patient_service.py     # Patient registration, OPD visits, token issue, vitals, intake
│   │   ├── report_service.py      # Secure file storage, magic byte validation, SHA-256 deduplication
│   │   ├── ocr_service.py         # PDF text extraction and optional Tesseract OCR
│   │   ├── prescription_safety_service.py # Review-only medication safety checks
│   │   └── doctor_service.py      # Consultation notes persistence, doctor review decisions
│   ├── symptoms/
│   │   ├── infer.py               # Symptom extractor with local path handling & rule fallback
│   │   ├── model.py               # Token classification loader with validation
│   │   └── baseline.py            # Rule-based negation & symptom extraction engine
│   └── reports/
│       └── extract.py             # pdfplumber coordinate & bounding-box extractor
├── data/
│   ├── hospital.db                # Persistent SQLite database (3 pre-seeded synthetic patients)
│   ├── uploads/                   # Secure patient uploaded report store
│   └── synthetic_lab_reports/     # Synthetic PDF reports and manifest
├── tests/                         # 22 automated unit & integration tests
├── run.py                         # Single-command launcher for backend + React frontend
├── requirements.txt               # Python dependencies
└── README.md
```

---

## 3. UI Theme & Design System

The frontend has been built to match the provided clinical design specifications:
- **Design Inspiration (Image 5)**:
  - Background: Soft, calming clinical light blue (`#edf4fa`).
  - Cards: High-elevation rounded white containers (`border-radius: 20px`, soft box-shadow).
  - Navigation & Chips: Pill-shaped status badges, active queue chips, and tab buttons (`border-radius: 9999px`).
  - Search Bar: Prominent floating search bar with instant autocomplete to find patients by Name, Phone, MRN, or Token.
  - Fully responsive: Optimized for mobile phones (during patient check-in) and laptops/desktops (for doctor OPD consultation).
- **Single Summary Card (Image 4)**:
  - `PATIENT: <Name>, <Age> | MRN <ID> | <Nth> visit`
  - `TODAY`: Presenting complaint, timeline, pertinent negatives.
  - `RELEVANT HISTORY`: Comorbidities, active medications, key past diagnostics.
  - `SAME COMPLAINT BEFORE`: Past visits, past advice, adherence/follow-up status.
  - `⚠️ RED FLAG`: Priority warning banner if acute red flag combinations are detected (e.g. chest pain with exertion, acute severe hypertension, hypoxia).
  - `CONFIRM IN ROOM`: Targeted clinical verification checklist for the doctor.
  - `10-15 sec read` pill badge and one-click copy brief to clipboard.
- **Dedicated Patient Records Tab**:
  - Full longitudinal patient timeline displaying every past visit in chronological order (newest first).
  - Demographics banner with copyable short MRN (`P10482`), baseline conditions, allergies, and current medications.
  - Expandable visit cards detailing vitals, uploaded lab reports with direct file download links, extracted test findings, doctor examination notes, and treatment plans.
  - Aggregated patient report archive across all historical visits.

---

## 4. Quick Start & Running the Platform

### A. One-Command Production Launch (Recommended)

From the project root:

```bash
python run.py
```

This single command:
1. Initializes and seeds the SQLite database (`data/hospital.db`).
2. Checks the compiled Vite + React application in `frontend/dist`.
3. Starts the unified ASGI server on `http://127.0.0.1:8000`.

Open your browser at **`http://localhost:8000`** (or `http://127.0.0.1:8000`).

### Role-based routes and demo sign-in

- Role selection: `http://localhost:8000/`
- Patient check-in: `http://localhost:8000/patient/check-in`
- Staff sign-in: `http://localhost:8000/staff/login`
- Doctor queue: `http://localhost:8000/doctor/queue`
- Nurse queue: `http://localhost:8000/nurse/queue`

Synthetic demo staff accounts:

| Role | Username | Password |
| :--- | :--- | :--- |
| Doctor | `doctor.demo` | `Doctor123!` |
| Nurse | `nurse.demo` | `Nurse123!` |

For non-demo environments, set `CHAKSHU_DOCTOR_PASSWORD` and
`CHAKSHU_NURSE_PASSWORD` before initializing a fresh database. Staff sessions
are server-side and role-scoped; patient intake and report uploads use a
short-lived token tied to the current patient and visit.

---

### B. Development Mode (Hot Reload)

If you wish to edit frontend React components with instant hot module reloading:

**Terminal 1 (Backend API):**
```bash
python run.py
```

**Terminal 2 (Vite Frontend):**
```bash
cd frontend
npm.cmd run dev
```
Open **`http://localhost:5173`** (Vite automatically proxies `/api` calls to port 8000).

---

## 5. Synthetic Demonstration Patients

The fresh database seed contains coherent fictional records for immediate workflow testing:

| Patient | Age / Gender | Presenting concern | Meaningful context |
| :--- | :--- | :--- | :--- |
| Aarav Nair | 52 / Male | Diabetes follow-up with bilateral foot tingling | Current and prior vitals, diabetes history, medication history, a prior completed consultation, and a synthetic laboratory report |
| Meera Kulkarni | 46 / Female | Hypertension review with episodic headache | Elevated blood pressure, recent missed doses, penicillin rash history, a prior consultation, and a synthetic report |
| Imran Shaikh | 61 / Male | Dyslipidemia follow-up with fatigue | Current vitals, medication status requiring confirmation, and a synthetic lipid report |

The repository also includes `snehu_illustrative_iron_deficiency_sample.pdf` and `tools/reconcile_demo_data.py`. The reconciliation utility creates a coherent fictional Snehu demonstration record from that teaching report (including haemoglobin 9.8 g/dL, ferritin 8 ng/mL, and TIBC 460 µg/dL) while removing obsolete duplicate demo findings. All names, reports, and clinical details are synthetic.

Use the nurse or doctor search field to find a patient by name, MRN, phone number, or current token.

---

## 6. Physical Report Camera Scan & Medical Reports Display

### Physical-Report Camera Workflow
- **Take Photo of Report**:
  - **In-Browser Viewfinder**: Uses WebRTC `navigator.mediaDevices.getUserMedia` preferring the rear/environment camera (`facingMode: { ideal: "environment" }`) with a document framing guide and canvas snapshot capture.
  - **Device Camera Fallback**: Provides a native mobile camera capture button (`<input type="file" accept="image/*" capture="environment">`) for devices where in-browser media streams are restricted, denied, or non-HTTPS.
  - **Photo Preview Before Upload**: Patients inspect the captured document snapshot with one-click **Retake Photo** or **Upload Page**.
  - **Multi-Page Scanning**: Assigns a shared `group_id` for multi-page prescriptions and multi-page lab slips. Shows an attached page gallery and "+ Photograph Page X" button to scan subsequent pages without losing earlier pages.
  - **Track Cleanup**: Automatically stops all camera media tracks when closing the camera, switching tabs, or unmounting the component.
- **Upload Existing File**: Direct file selector supporting PDF, JPG, JPEG, and PNG files up to 15MB.
- **Laboratory Display (No Inspect Modal)**:
  - Extracted lab findings are cleanly formatted in an OPD tabular view (Investigation Name, Observed Result, Reference Range, Clinical Status).
  - The doctor sees the extracted clinical values directly without disruptive popups or PDF viewer overlays.
  - Original files are validated (magic bytes, MIME type) and deduplicated via SHA-256 in `data/uploads/`.

### Is OCR present?

Yes. OCR is implemented in `src/services/ocr_service.py`, with two report paths:

- Text-based PDFs are extracted locally with `pdfplumber` and do not need Tesseract.
- JPG, PNG, and image-only/scanned PDF pages use image preprocessing and Tesseract OCR.
- If Tesseract is unavailable, the API records a clear warning and returns no fabricated extraction. The original report remains available for review.

Check the local OCR capability directly:

```bash
python -c "from src.services.ocr_service import is_tesseract_available; print(is_tesseract_available())"
```

The current development machine returns `False`, so Tesseract must be installed and available on `PATH` before image OCR can run.

---

## 7. Returning Patient Recognition & Identity Verification

### Core Identifier Separation
- **Permanent Patient ID (MRN)**: Short, human-readable format (`P10482`, `P10001`+). Never changes across visits. Concurrency-safe sequential allocation with DB unique constraint. Backward-compatible with legacy `PAT-` IDs.
- **Visit ID**: Generated per encounter (`VIS-...`).
- **OPD Token**: Generated for today's queue (`T-101`, `T-102`). Never used as a patient identifier.

### Two-Option Check-in Workflow
1. **A. New Patient Registration**:
   - Patient provides Name, Phone, Age, Gender.
   - Automatic phone deduplication and name conflict checks.
   - Generates short permanent MRN (`P10001`+).
   - Shows prominent Permanent Patient ID Card with one-click **Copy Patient ID** action and explanation to save for future visits.
2. **B. Returning Patient Check-in**:
   - Patient enters their Short MRN (e.g. `P10482`).
   - Patient enters their registered mobile number for identity verification.
   - The system verifies phone matches the database record before exposing any personal or medical history.
   - Prefills known chronic conditions, current medications, and allergies.
   - Mints a new Visit ID and fresh OPD token without overwriting past visit records.
   - Includes **"Forgot your Patient ID?"** helper allowing search by registered phone number and name.

### Identity Matching & Conflict Handling
1. **Phone Normalization (`normalize_phone`)**: Automatically strips spaces, hyphens, country codes (`+91`, `91`), and leading `0` down to 10 standard digits.
2. **Name Consistency (`normalize_name`, `names_are_consistent`)**: Trims whitespace, strips salutations (`Mr.`, `Dr.`, `Mrs.`), and compares case-insensitively with support for word-order swapping (`Patel Ramesh` vs `Ramesh Patel`) and subset matches.
3. **Name Conflict Protection**:
   - If a mobile number is already registered to a different person, the system prevents silent merging or duplicate creation by raising `PatientNameConflictError` (HTTP 409 `status: "name_conflict"`).
   - The user/staff is presented with 3 clear options:
     - **"Yes, I am [Existing Name]"** (`confirm_existing=True`): Links to existing MRN.
     - **"Register as new patient / family member"** (`force_new=True`): Issues a new distinct MRN sharing the phone.
     - **"Edit details"**: Corrects phone or name typos.
4. **Double-Click & Refresh Idempotency**:
   - If a patient refreshes the page or double-clicks check-in while in `waiting` status today, the system safely returns their active visit and token without minting redundant tokens. Once the doctor saves consultation notes and marks the visit completed, a subsequent check-in correctly creates a new visit.

---

## 8. Dedicated Patient Records / Medical History Tab

- **Top Navigation & Direct Access**:
  - Available as the second tab (`Patient Records`) in the top navigation bar.
  - Linked directly from the Doctor Brief via **"View Full History in Patient Records"** button in the Past Consultations section.
  - Mobile bottom navigation includes direct shortcut.
- **Search & Patient Identification**:
  - Search by Short MRN (`P10482`), legacy ID (`PAT-...`), patient name, or registered phone number.
- **Comprehensive Clinical Profile**:
  - Demographics card with prominent MRN badge and one-click copy button.
  - Baseline clinical summary displaying recorded allergies, chronic conditions, active medications, and total visit count.
- **Chronological Visit Timeline (Newest First)**:
  - Each visit is rendered as an expandable card containing:
    - Visit metadata: Visit ID, date, time, and status.
    - Chief complaint and symptom duration.
    - Recorded vital signs (BP, Pulse, Temperature, SpO2, Blood Sugar) with abnormal flagging.
    - Uploaded medical reports with direct file download links (`/api/reports/{id}/file`).
    - Extracted laboratory findings in clean tabular format.
    - Doctor consultation notes, physical examination observations, and prescription advice.
    - Complete 10-15s Single Summary Card snapshot for that encounter.
- **Consolidated Reports Archive**:
  - Displays all laboratory tests, imaging, and prescriptions across all visits in a single table with download links, file sizes, and visit provenance.

---

## 9. Model Path Resolution & Symptom Extractor

### Root Cause of the Transformers `OSError: Repo id must be in the form...`
When the application previously called `Extractor(MODEL_DIR)` with an uncreated local directory:
1. Hugging Face Transformers assumed any non-existent local directory string was a model repository on Hugging Face Hub.
2. On Windows, local file paths containing drive letters (`C:`) and backslashes (`\`) fail Hugging Face Hub's regex pattern.
3. This triggered `OSError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'`.

### Fix Implemented
- `src/symptoms/model.py`: Added `is_local_path()` and `validate_local_model_dir()`. Passes `local_files_only=True` to prevent remote HF Hub lookups.
- Missing checkpoints raise a clean `ModelNotFoundError` with training instructions instead of exposing a raw traceback.
- `src/symptoms/infer.py`: Implements `fallback_to_baseline=True` using the calibrated rule-based keyword and negation extractor (`src/symptoms/baseline.py`).
- The extractor is initialized once and cached by the server. Without a validated local checkpoint, the health endpoint reports `model_mode: "baseline"` and the application uses the deterministic fallback rather than attempting a network download.

To fine-tune the planned ModernBERT token classification model:
```bash
python -m src.symptoms.train_all --data data/symptoms/split
```

---

## 10. Automated Test Suite

Run all automated unit and integration tests:

```bash
python -m pytest -q
```

Tests cover:
- `test_patient_recognition.py` (13 tests):
  - Phone normalization: handles `+91 98765 43210`, `919876543210`, `09876543210`, spaces, hyphens.
  - Name consistency: handles case, salutations (`Mr.`, `Dr.`, `Mrs.`), name inversion (`Patel Ramesh` vs `Ramesh Patel`), and subset matches.
  - First-time patient registration with unique short MRN (`P10001`+).
  - Uniqueness and collision avoidance across multiple patient registrations.
  - Verified returning patient check-in flow with registered phone verification.
  - Rejection of returning patient check-in with mismatched phone number.
  - Rejection of unknown MRNs.
  - "Forgot MRN" lookup by registered mobile number and name.
  - Backward compatibility with legacy long IDs (`PAT-2026-XXXX`).
  - Identity name conflict detection raising `PatientNameConflictError` with `confirm_existing` and `force_new` resolution paths.
  - Token idempotency (reusing waiting token on double-click/refresh) and monotonic sequential allocation (`T-101`, `T-102`).
  - Multi-visit history preservation and doctor consultation notes retention.
- `test_patient_records.py` (6 tests):
  - Complete chronological visit timeline (newest first) with visit isolation, vitals, clean labs, and doctor notes.
  - Report lookup by report ID with secure file access.
  - Graceful handling of non-existent patient records.
  - Legacy ID resolution (`PAT-2026-2123D6`) across ASCII hyphens, Unicode en-dashes (`\u2013`), em-dashes (`\u2014`), URL-encoded paths (`%E2%80%93`), and whitespace.
  - Short MRN resolution (`P10001`+, case insensitivity, trimming).
  - Safe error handling for invalid/empty/unknown identifiers without raising unhandled exceptions.
- `test_camera_upload.py` (3 tests):
  - Magic byte validation for PNG, JPEG, and PDF documents; rejection of renamed executables or spoofed files.
  - Multi-page camera capture grouping under a shared `group_id`, associating pages with visit and patient.
  - Stored image report OCR extraction and graceful handling when Tesseract is or isn't installed.
- `test_model_loader.py` (6 tests): Transformers local path validation, missing checkpoints, negation extraction, and baseline fallback.
- `test_database.py` (4 tests): Patient registration, token sequence, vitals, intakes, and audit trails.
- `test_report_pipeline.py` (4 tests): Magic byte validation, file size limits, SHA-256 deduplication, and OCR extraction.
- `test_summary_service.py` (3 tests): Image 4 single summary card synthesis, red flag triggers, and gap detection.
- `test_doctor_workflow.py` (3 tests): Review decisions, doctor consultation notes persistence, and longitudinal lab trends.
- `test_end_to_end_workflow.py` (3 tests): Complete patient registration -> vitals -> intake -> report upload -> summary -> doctor notes lifecycle.
- `test_authenticated_lifecycle.py`: Role authentication and the complete patient -> nurse -> doctor -> records lifecycle, including queue removal after completion.
- `test_prescription_safety.py`: Incomplete directions, duplicate medicines, allergy terms, and documented interaction warnings without autonomous prescribing.

---

## 11. Security, Privacy & Compliance

- **Multi-tenant Isolation**: All database queries are explicitly scoped to patient and visit identifiers.
- **Audit Logging**: All view actions, vitals entries, notes saves, and report uploads are logged in `audit_logs`.
- **Deduplication**: SHA-256 hashing prevents storage of duplicate documents.
- **Clinical Safety Boundary**: The summary, temporal reasoning, and prescription checks are review aids. They cannot independently diagnose, prescribe, or change medication.
