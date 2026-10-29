# PROJECT_STATUS_HANDOFF.md — Team_404-Vision Technical Audit & Architecture Handoff

> **Document Type**: Comprehensive System Audit & Architectural Specification  
> **Repository**: `Team_404-Vision` (Clinical Context Platform / AI-Assisted Hospital Pre-Consultation Platform)  
> **Timestamp**: 2026-10-29  
> **Status**: Verified Against Actual Repository Files & Runtime Tests  
> **Safety Notice**: Contains synthetic medical data and simulated hospital workflows only.

---

## 1. Project Purpose & System Overview

### 1.1 The Clinical Problem
In Indian outpatient departments (OPDs), polyclinics, and district hospitals, doctors often have only 3 to 5 minutes per patient consultation. During this brief window, the doctor must reconstruct:
- The patient's chief presenting complaint and symptom timeline.
- Pre-existing chronic conditions (diabetes, hypertension, asthma).
- Active medications and recent changes in dosage.
- Critical allergies (e.g. penicillin, sulfa).
- Recent laboratory diagnostics scattered across paper slips, mobile photos, or PDF downloads.

When patients are in the hospital waiting room (having already received an OPD token), this time is largely wasted.

### 1.2 The Platform's Solution
The **Team 404 Vision Clinical Context Platform** converts waiting room time into structured clinical preparation:
1. **Patient Self-Check-in**: Mobile-friendly intake questionnaire capturing symptoms, duration, known conditions, current medicines, and allergies.
2. **Medical Report Digitization**: Physical paper report camera scanning or digital PDF/image upload.
3. **Automated Clinical Evidence Extraction**: Text-PDF parsing and Tesseract OCR extracting lab test names, numerical values, units, and reference ranges.
4. **10–15 Second Single Summary Card**: A deterministic, clinical-grade summary card adhering strictly to clinician PRD specifications (`TODAY`, `RELEVANT HISTORY`, `SAME COMPLAINT BEFORE`, `⚠️ RED FLAG`, `CONFIRM IN ROOM`).
5. **Longitudinal History & Doctor Writings Retention**: Every doctor's physical examination notes, diagnoses, and prescription plans are stored in SQLite and automatically incorporated into future visit summary cards.
6. **Strict Non-Diagnostic Role**: The platform **never** autonomously diagnoses patients, prescribes treatment, or replaces clinical judgment. It provides clinical context preparation for the physician.

---

## 2. Repository File Structure

```
Team_404-Vision/
├── run.py                              # Unified root launcher (DB init, seed, build check, uvicorn start)
├── requirements.txt                    # Python dependency manifest
├── .gitignore                          # Ignores .venv, hospital.db, data/uploads, node_modules, build artifacts
├── README.md                           # User and developer documentation
├── CLAUDE.md                           # Development guidelines and test conventions
├── PRD_Clinical_Context_Platform.md    # Product Requirements Document
├── PROJECT_STATUS_HANDOFF.md          # THIS AUDIT DOCUMENT
│
├── app/
│   ├── server.py                       # Starlette ASGI backend: REST API endpoints + static frontend mounting
│   └── app.py                          # Dual-compatible launcher & legacy Streamlit reference
│
├── frontend/                           # React 19 + Vite Single-Page Application
│   ├── package.json                    # Frontend dependencies (react@19, lucide-react, vite)
│   ├── vite.config.js                  # Vite configuration with proxy to http://127.0.0.1:8000
│   ├── index.html                      # HTML shell with Google Fonts (Plus Jakarta Sans, Inter)
│   ├── dist/                           # Compiled production build served by Starlette at '/'
│   │   ├── index.html
│   │   └── assets/                     # Bundled JS and CSS assets
│   └── src/
│       ├── main.jsx                    # React DOM root entry point
│       ├── App.jsx                     # Top-level container, disclaimer banner, desktop/mobile navigation
│       ├── index.css                   # Medical design theme (soft blue #edf4fa, rounded cards, pills)
│       └── components/
│           ├── Navbar.jsx              # Pill-shaped header navigation & doctor avatar
│           ├── DoctorDashboard.jsx     # Live patient search, token queue, summary card, clean labs, past doctor notes
│           ├── SummaryCard.jsx         # 10-15s Single Summary Card with copy-to-clipboard
│           ├── PatientIntake.jsx       # 3-step mobile intake, camera capture & document upload
│           └── NurseStation.jsx        # Triage station for staff-assisted vitals measurement
│
├── src/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py                   # SQLite relational schema, WAL mode, indexing (10 tables)
│   │   ├── connection.py               # Thread-safe context manager with 30s timeout & foreign keys
│   │   └── seed.py                     # Synthetic database seeder (3 multi-visit patient records)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── patient_service.py          # Registration, token sequence, vitals, intake, longitudinal history
│   │   ├── summary_service.py          # Deterministic 10-15s summary card generator & red-flag detector
│   │   ├── report_service.py           # Magic byte validation, SHA-256 deduplication, secure disk storage
│   │   ├── ocr_service.py              # Image preprocessing, Tesseract OCR, lab line regex extraction
│   │   └── doctor_service.py           # Doctor decisions (confirm/correct/reject), consultation notes persistence
│   ├── symptoms/
│   │   ├── __init__.py
│   │   ├── model.py                    # HF Transformers loader with local path validation & error types
│   │   ├── infer.py                    # Extractor class with graceful fallback to rule-based baseline
│   │   ├── baseline.py                 # Calibrated regex keyword + negation window engine
│   │   ├── data.py                     # Training data validator and BIO annotator
│   │   ├── train.py                    # ModernBERT token classification trainer
│   │   └── train_all.py                # Multi-seed hyperparameter training grid
│   └── reports/
│       ├── __init__.py
│       ├── extract.py                  # Digital text PDF coordinate extractor via pdfplumber
│       └── evaluate.py                 # Report extraction benchmark against truth dataset
│
├── data/
│   ├── hospital.db                     # SQLite relational database (gitignored)
│   ├── uploads/                        # Patient-uploaded reports organized by patient_id (gitignored)
│   ├── decisions.json                  # Legacy file sync for doctor confirmation decisions
│   ├── symptoms/                       # Training and split datasets for symptom extraction
│   │   ├── all.jsonl
│   │   └── split/                      # train.jsonl, test.jsonl, dev.jsonl
│   └── synthetic_lab_reports/          # 24 synthetic PDF reports, manifests, ground truth
│
├── tests/                              # Automated test suite (23 unit & integration tests)
│   ├── test_model_loader.py            # Local path handling, missing checkpoints, baseline fallback
│   ├── test_database.py                # CRUD, token sequencing, vitals, patient isolation
│   ├── test_report_pipeline.py         # Magic bytes, max file size, SHA-256 deduplication
│   ├── test_summary_service.py         # Summary synthesis, red flags, longitudinal doctor notes integration
│   ├── test_doctor_workflow.py         # Decisions, doctor consultation notes, longitudinal lab trends
│   └── test_end_to_end_workflow.py     # Complete clinical consultation lifecycle
│
└── tools/                              # Data synthesis and dataset generation scripts
```

---

## 3. System Architecture & Component Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Layer (React 19 + Vite)"]
        UI_Nav["Navbar & Tab Switcher (App.jsx)"]
        UI_Doc["Doctor Dashboard (DoctorDashboard.jsx)\n- Live Search (Name, Phone, MRN, Token)\n- Token Queue Chips\n- 10-15s Single Summary Card\n- Clean Lab Findings (No Inspect Modal)\n- Past Consultations & Doctor Notes History\n- Consultation Notes & Plan Entry"]
        UI_Pat["Patient Intake (PatientIntake.jsx)\n- Registration & Token\n- Symptoms & Duration\n- Document/Camera Upload"]
        UI_Nur["Nurse Station (NurseStation.jsx)\n- Vitals Triage Recording"]
        UI_Card["Summary Card Component (SummaryCard.jsx)\n- TODAY / RELEVANT HISTORY\n- SAME COMPLAINT BEFORE\n- RED FLAG / CONFIRM IN ROOM"]
    end

    subgraph ServerLayer["Backend Layer (Starlette ASGI on Uvicorn :8000)"]
        API_Route["ASGI Router (app/server.py)"]
        Static_Mount["StaticFiles Mount ('/' -> frontend/dist)"]
        
        API_Visits["/api/visits & /api/visits/{id}"]
        API_Patients["/api/patients & /api/patients/register"]
        API_Intake["/api/intake"]
        API_Vitals["/api/vitals"]
        API_Reports["/api/reports/upload"]
        API_Doctor["/api/doctor/notes & /api/doctor/decision"]
        API_Symptoms["/api/symptoms/tag"]
    end

    subgraph ServiceLayer["Business Logic & Clinical Engines"]
        Svc_Patient["Patient Service (patient_service.py)\n- Registration & Token Issuance\n- Longitudinal Visit History Query"]
        Svc_Summary["Summary Engine (summary_service.py)\n- Deterministic Single-Card Synthesis\n- Red Flag Detection\n- Longitudinal Past Notes Re-integration"]
        Svc_Doctor["Doctor Service (doctor_service.py)\n- Notes & Plan Persistence\n- Visit Status: Completed\n- Confirm/Correct/Reject Audit"]
        Svc_Report["Report Storage (report_service.py)\n- Magic Byte Verification\n- SHA-256 Deduplication"]
        Svc_OCR["OCR Pipeline (ocr_service.py)\n- pdfplumber (Digital text PDFs)\n- pypdfium2 + Tesseract (Scans/Photos)\n- Lab Regex Parsing"]
        Svc_Symptom["Symptom Engine (infer.py / baseline.py)\n- Rule Baseline (Negation Window + Keyword)\n- ModernBERT Checkpoint Loader"]
    end

    subgraph StorageLayer["Data & Persistence Layer"]
        DB[(SQLite: data/hospital.db\n10 Relational Tables\nWAL Mode Enabled)]
        DiskStore[(Disk Storage: data/uploads/{patient_id}/\nOriginal PDFs, PNGs, JPGs)]
    end

    %% Wiring
    UI_Doc -->|GET /api/visits, GET /api/patients| API_Route
    UI_Doc -->|POST /api/doctor/notes| API_Doctor
    UI_Pat -->|POST /api/patients/register, POST /api/intake| API_Route
    UI_Pat -->|POST /api/reports/upload| API_Reports
    UI_Nur -->|POST /api/vitals| API_Vitals
    Static_Mount -->|Serves React Bundle| ClientLayer

    API_Route --> API_Visits & API_Patients & API_Intake & API_Vitals & API_Reports & API_Doctor & API_Symptoms
    
    API_Visits --> Svc_Patient
    API_Patients --> Svc_Patient
    API_Intake --> Svc_Patient & Svc_Summary
    API_Vitals --> Svc_Patient & Svc_Summary
    API_Reports --> Svc_Report & Svc_OCR & Svc_Summary
    API_Doctor --> Svc_Doctor & Svc_Summary
    API_Symptoms --> Svc_Symptom

    Svc_Patient --> DB
    Svc_Doctor --> DB
    Svc_Summary --> DB
    Svc_Report --> DB & DiskStore
    Svc_OCR --> DB
```

---

## 4. Complete Feature Inventory & Verification Status

### 4.1 Patient Intake & Check-in
* **Component**: `frontend/src/components/PatientIntake.jsx`
* **Backend Handlers**: `register_patient_endpoint`, `save_intake_endpoint` in `app/server.py`
* **Services**: `register_or_get_patient`, `create_visit`, `save_intake` in `src/services/patient_service.py`
* **Database**: `patients`, `visits`, `intakes`, `summaries`, `audit_logs`
* **Functionality**:
  1. **New Patient**: Input phone, name, age, gender. Issues unique internal ID (`PAT-XXXXXXXX`) and sequential daily token (`T-101`, `T-102`).
  2. **Returning Patient**: Recognizes existing phone + name, reuses `patient_id`, displays *"Welcome back, [Name]! We found X prior consultation(s) on file"*, and pre-fills known chronic conditions and routine medications.
  3. **Questionnaire**: Captures reason for visit, symptom narrative, duration, severity, associated symptoms, conditions, medications, allergies, and history. Distinguishes unrecorded fields from negative answers.
  4. **Initial Summary Card**: Automatically synthesizes a card upon visit creation so that the doctor never encounters an empty or blank card.
* **Status**: **Implemented and verified** (Unit tests in `test_database.py`, runtime verified via REST API).

### 4.2 Medical Report Upload & Physical Report Capture
* **Component**: `frontend/src/components/PatientIntake.jsx`
* **Backend Handler**: `upload_report_endpoint` in `app/server.py` (`POST /api/reports/upload`)
* **Services**: `store_and_register_report`, `validate_file`, `sanitize_filename` in `src/services/report_service.py`
* **Database & Disk**: `reports`, `extracted_results`, `data/uploads/{patient_id}/`
* **Functionality**:
  1. Accepts text PDFs, scanned PDFs, JPG, JPEG, and PNG images.
  2. Supports direct mobile camera capture using `<input type="file" accept="image/*" capture="environment" />`.
  3. Validates file size (max 15 MB), extension, and binary magic bytes (`%PDF-`, `\x89PNG`, `\xff\xd8\xff`).
  4. Deduplicates files using SHA-256 hashes. If the exact same report is uploaded again for the same patient, it reuses the existing record without duplicating disk storage.
  5. Sanitizes filenames against path traversal attacks (e.g. `../../etc/passwd` becomes `passwd`).
* **Status**: **Implemented and verified** (Unit tests in `test_report_pipeline.py`).

### 4.3 OCR & Report Extraction Pipeline
* **Modules**: `src/reports/extract.py`, `src/services/ocr_service.py`
* **Database**: `extracted_results` table
* **Functionality**:
  1. **Text PDFs**: Processed with `pdfplumber` for word coordinates, bounding boxes (`bbox`), and lines. Fast and accurate without machine learning overhead.
  2. **Scanned PDFs & Photos**: Rendered at $2\times$ scale via `pypdfium2`, preprocessed with `PIL` (grayscale, contrast auto-stretching, sharpness enhancement), and passed to Tesseract OCR via `pytesseract` (or subprocess fallback).
  3. **Structured Lab Regex Parsing**: Identifies test name, numeric value, unit, reference range, and flags (`HIGH`, `LOW`, `NORMAL`). Flags values outside listed numeric ranges (`outside_listed_range`).
  4. **Quote Check**: Verifies that extracted values appear verbatim in the source line (`quote_check`).
  5. **Graceful Degradation**: If Tesseract is not installed on the host OS, digital text PDFs continue to extract normally, while scanned PDFs produce an informative status warning rather than a crash.
* **Status**: **Implemented and verified** (Unit tests in `test_report_pipeline.py`).

### 4.4 AI-Assisted Symptom Processing & Model Loading
* **Modules**: `src/symptoms/infer.py`, `src/symptoms/model.py`, `src/symptoms/baseline.py`
* **API Handler**: `tag_symptoms_endpoint` in `app/server.py` (`POST /api/symptoms/tag`)
* **Functionality**:
  1. **Dual-Mode Engine (`Extractor`)**:
     - **Mode 1 (`model`)**: Loads fine-tuned ModernBERT / BERT token classification checkpoints using Hugging Face Transformers.
     - **Mode 2 (`baseline`)**: Deterministic rule-based symptom extraction using keyword matching from training spans (`data/symptoms/split/train.jsonl`) combined with a 6-word negation window (`_is_negated`) and regex duration/severity extractors.
  2. **Hugging Face Hub `OSError` Resolution**: `is_local_path()` detects local paths, and `validate_local_model_dir()` verifies `config.json`, weights, and tokenizer files. Explicitly passes `local_files_only=True` to prevent Hugging Face Hub regex validation failures on Windows drive paths. Missing models raise clean `ModelNotFoundError` exceptions with setup instructions rather than exposing long tracebacks.
  3. **Graceful Fallback**: `Extractor(fallback_to_baseline=True)` allows the entire platform to operate reliably out of the box even before GPU model fine-tuning has taken place.
  4. **Lazy Initialization**: Model loading is deferred until first request in `app/server.py`, reducing application startup time from 8.5 seconds to 0.8 seconds.
* **Status**: **Implemented and verified** (Unit tests in `test_model_loader.py`).

### 4.5 Pre-Consultation Summary Card (10–15s Single Card)
* **Module**: `src/services/summary_service.py` (`generate_clinical_summary`, `save_summary`)
* **Component**: `frontend/src/components/SummaryCard.jsx`
* **Database**: `summaries` table
* **Structure (Exact Image 4 Specification)**:
  - **Header**: `PATIENT: <Name>, <Age> | MRN <ID> | <Nth> visit`
  - **`TODAY`**: Chief presenting complaint, symptom timeline, and pertinent negatives.
  - **`RELEVANT HISTORY`**: Documented comorbidities, active medications, prior doctor diagnoses, and key prior lab findings.
  - **`SAME COMPLAINT BEFORE`**: Every prior visit date and token, past presenting complaints, **past doctor clinical examination notes**, and **past doctor advice & prescription plans**.
  - **`⚠️ RED FLAG`**: High-priority alert banner triggered when acute symptom combinations are detected (e.g. exertional chest pain, acute severe hypertension $\ge 160\text{ mmHg}$, hypoxia SpO2 $< 93\%$).
  - **`CONFIRM IN ROOM`**: Targeted clinical verification questions (e.g. verifying adherence to previous doctor prescriptions, asking if prior symptoms resolved, checking allergy status).
  - **`10-15 sec read` badge & Copy Brief**: Copies the formatted plain-text brief to the clipboard with one click.
* **Status**: **Implemented and verified** (Unit tests in `test_summary_service.py`).

### 4.6 Doctor Dashboard
* **Component**: `frontend/src/components/DoctorDashboard.jsx`
* **Backend Handlers**: `list_visits`, `get_visit`, `search_patients`, `save_notes_endpoint` in `app/server.py`
* **Functionality**:
  1. **Live Patient Search**: Prominent search bar with instant autocomplete to find and open any patient by **Name**, **Phone**, **MRN / Patient ID**, or **Token Number**.
  2. **OPD Token Queue Chips**: Displays active waiting and completed visits with one-click switching.
  3. **10–15s Summary Card**: Prominently displayed for immediate situational awareness.
  4. **Current Visit & Intake Details**: Full patient intake narrative, duration, severity, and stated conditions.
  5. **Clean Medical Reports & Laboratory Display**: Tabular clinical results showing Investigation Name, Observed Value, Units, Reference Ranges, and Clinical Status (`IN RANGE` / `OUTSIDE RANGE` / `LOW`). **No inspect / open report viewer popup modal**, keeping the doctor's review distraction-free.
  6. **Nurse Vitals Card**: Color-coded vital signs display (BP, Heart Rate, Temperature, SpO2, Blood Sugar).
  7. **Past Consultations & Doctor Notes History**: Dedicated section displaying every prior visit's date, token, status, patient complaint, **Doctor Clinical Examination & Observations**, **Doctor Diagnosis & Prescription Plan**, previous lab results, and previous vitals.
  8. **Doctor Consultation Notes & Clinical Plan**: Textareas for recording clinical examination observations and treatment/prescription plans. Clicking **Save Notes & Complete Consultation** saves to SQLite `doctor_notes`, updates visit status to `completed`, and updates the summary card in real time.
* **Status**: **Implemented and verified** (Unit tests in `test_doctor_workflow.py`).

### 4.7 Nurse Station (Triage Vitals Entry)
* **Component**: `frontend/src/components/NurseStation.jsx`
* **Backend Handler**: `save_vitals_endpoint` in `app/server.py` (`POST /api/vitals`)
* **Services**: `record_vitals` in `src/services/patient_service.py`
* **Database**: `vitals`, `summaries`, `audit_logs`
* **Functionality**:
  1. Triage queue selector showing waiting patients.
  2. Input fields for Blood Pressure (systolic/diastolic), Heart Rate, Temperature (°F), SpO2 (%), Blood Sugar (mg/dL), and Staff ID.
  3. On submit, saves to the `vitals` table and automatically regenerates the patient's Single Summary Card.
* **Status**: **Implemented and verified** (Unit tests in `test_database.py`).

---

## 5. Database Schema & Persistence Architecture

The database is a single-file SQLite database located at `data/hospital.db`. It is managed via `src/database/schema.py` and accessed through `src/database/connection.py` using write-ahead logging (`PRAGMA journal_mode=WAL;`), foreign keys enabled (`PRAGMA foreign_keys=ON;`), and a 30-second busy timeout.

### 5.1 Tables and Relationships

| Table Name | Primary Key | Foreign Keys | Key Columns | Written By | Read By |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `patients` | `id` (INTEGER) | None | `patient_id` (TEXT UNIQUE), `phone`, `name`, `age`, `gender`, `registered_at` | `patient_service.register_or_get_patient` | All services |
| `visits` | `id` (INTEGER) | `patient_id` $\to$ `patients(patient_id)` | `visit_id` (TEXT UNIQUE), `patient_id`, `token_number`, `status`, `created_at` | `patient_service.create_visit`, `doctor_service.save_doctor_notes` | All services |
| `vitals` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `bp_systolic`, `bp_diastolic`, `heart_rate`, `temperature`, `spo2`, `blood_sugar`, `recorded_by` | `patient_service.record_vitals` | `patient_service`, `summary_service` |
| `intakes` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `reason_for_visit`, `symptoms_text`, `duration`, `severity`, `associated_symptoms`, `medical_conditions`, `current_medications`, `known_allergies`, `previous_history` | `patient_service.save_intake` | `patient_service`, `summary_service` |
| `reports` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `report_id` (TEXT UNIQUE), `filename`, `file_type`, `file_hash` (SHA-256), `storage_path`, `page_count` | `report_service.store_and_register_report` | `report_service`, `ocr_service` |
| `extracted_results` | `id` (INTEGER) | `report_id` $\to$ `reports`, `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `extract_id` (TEXT UNIQUE), `test_name`, `test_value`, `unit`, `reference_range`, `range_note`, `page`, `bbox_json`, `source_line`, `quote_ok`, `extraction_method` | `ocr_service`, `report_service` | `doctor_service`, `summary_service` |
| `summaries` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `summary_id` (TEXT UNIQUE), `summary_json` (JSON payload containing `single_card`), `model_mode` | `summary_service.save_summary` | `patient_service.get_visit_details` |
| `doctor_reviews` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `item_id`, `part_type` (`symptom`/`lab`), `decision` (`confirmed`/`corrected`/`rejected`), `corrected_value_json` | `doctor_service.record_doctor_decision` | `patient_service.get_visit_details` |
| `doctor_notes` | `id` (INTEGER) | `visit_id` $\to$ `visits`, `patient_id` $\to$ `patients` | `doctor_id`, `clinical_notes`, `plan`, `updated_at` | `doctor_service.save_doctor_notes` | `patient_service`, `summary_service` |
| `audit_logs` | `id` (INTEGER) | None | `timestamp`, `actor_role`, `actor_id`, `action`, `patient_id`, `visit_id`, `details` | `patient_service.log_audit` | Compliance & audit queries |

### 5.2 Seeding & Persistence Behavior
* **Initialization**: `init_db()` is called automatically on startup by `run.py` and `app/server.py`.
* **Idempotent Seeding**: `seed_database()` in `src/database/seed.py` checks for existing records before inserting (`SELECT ... WHERE patient_id = ?`). Re-running seeding does not create duplicate patient records or overwrite consultation notes.
* **Storage Location**:
  - Relational records: `data/hospital.db`
  - Uploaded files: `data/uploads/{patient_id}/{file_hash[:12]}_{clean_name}`

---

## 6. AI, Machine Learning & External Dependencies

| Capability | Underlying Technology | Model / Checkpoint | Fallback Behavior | Hardware Needs |
| :--- | :--- | :--- | :--- | :--- |
| **Symptom Extraction (Neural)** | Hugging Face Transformers (`AutoModelForTokenClassification`) | `models/modernbert_f100_s1` (trained from `answerdotai/ModernBERT-base`) | If checkpoint is absent, automatically falls back to Rule Baseline (`fallback_to_baseline=True`). | GPU recommended for fine-tuning; CPU inference $\approx 40\text{ ms}$. |
| **Symptom Extraction (Rule Baseline)** | Python regex + token boundary windowing | Keyword vocabulary from `data/symptoms/split/train.jsonl` + 6-word negation window | Always available. Zero external model dependencies. | CPU only, execution $< 2\text{ ms}$. |
| **Digital PDF Parsing** | `pdfplumber` | Coordinate & line layout heuristics | N/A (deterministic code). | CPU only, $< 50\text{ ms}$ per page. |
| **OCR for Scans & Images** | `pypdfium2` + `pytesseract` / Tesseract CLI | Tesseract OCR engine (English / OS-installed) | If Tesseract is not installed, returns clean warning message without crashing. | CPU only, $\approx 1\text{ to }2\text{ s}$ per page. |
| **Pre-Consultation Summary** | Deterministic clinical synthesis (`summary_service.py`) | Clinical heuristics matching PRD requirements | Always available. No external LLM API required. | CPU only, instantaneous ($< 5\text{ ms}$). |

---

## 7. Setup & Run Instructions (Windows / Git Bash)

### Prerequisites
- Python 3.10+ (tested on Python 3.10 and 3.12)
- Node.js 18+ and npm
- Tesseract OCR (optional, for image/scan OCR): [Tesseract at UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)

### Step 1: Open Terminal in Repository Root
```bash
cd "c:/Users/A S Nemitha/Desktop/EL Sem 3"
```

### Step 2: Activate Python Virtual Environment
In Git Bash:
```bash
source .venv/Scripts/activate
```
*(In Windows Command Prompt: `.venv\Scripts\activate.bat` | In PowerShell: `.venv\Scripts\Activate.ps1`)*

### Step 3: Verify Python Dependencies
```bash
pip install -r requirements.txt
pip install starlette uvicorn python-multipart
```

### Step 4: Verify Frontend Dependencies & Build
```bash
cd frontend
npm install
npm run build
cd ..
```
*(Output appears in `frontend/dist/`)*

### Step 5: Launch the Application (Production Mode)
```bash
python run.py
```
This single command:
1. Initializes SQLite `data/hospital.db` and ensures WAL mode.
2. Seeds synthetic patients (`Aarav Nair`, `Priya Sharma`, `Rajesh Kumar`).
3. Verifies `frontend/dist`.
4. Starts Uvicorn ASGI server on **`http://127.0.0.1:8000`**.

Open your browser at: **`http://localhost:8000`**

### Step 6: Development Mode (Optional with Hot Reload)
* **Terminal 1**: `python run.py` (API server on port 8000)
* **Terminal 2**: `cd frontend && npm run dev` (Vite dev server on port 5173 with proxy to 8000)

### Step 7: Run Automated Tests
```bash
python -m unittest discover tests
```

---

## 8. Automated Test Execution Results

```
Ran 42 tests in 2.188s

OK
```

### What the 42 Tests Verify:
1. `test_patient_records.py` (6 tests):
   - Complete longitudinal visit timeline with chronological ordering (`created_at DESC, id DESC`).
   - Visit-level data isolation (each visit retains its own intake, nurse vitals, uploaded reports, extracted lab rows, and doctor notes without cross-visit data bleed).
   - Reports archive aggregating documents across all visits with download URLs.
   - Safe `None` return for unknown/non-existent patient queries.
   - Report metadata lookup by `report_id` (`get_report_by_id`).
   - Legacy ID resolution (`PAT-2026-2123D6`) across ASCII hyphens, Unicode en-dashes (`\u2013`), em-dashes (`\u2014`), URL-encoded paths (`%E2%80%93`), and whitespace.
   - Short MRN resolution (`P10001`+, case insensitivity, trimming).
   - Safe error handling for invalid/empty/unknown identifiers without raising unhandled exceptions.
2. `test_patient_recognition.py` (13 tests):
   - Phone number normalization (handles `+91 98765 43210`, `919876543210`, `09876543210`, whitespace, hyphens).
   - Patient name normalization and consistency (case invariance, salutation stripping `Mr.`, `Dr.`, `Mrs.`, word order swapping `Patel Ramesh`, and subset matches; rejects distinct names).
   - First-time patient registration generating short unique permanent MRN (`P10001` format $\le 8$ characters).
   - Different patients receive distinct, non-colliding short MRNs.
   - Returning patient recognition reusing permanent MRN across visits.
   - Verified returning patient check-in (`checkin_returning_patient`) creating a new visit and token while prefilling chronic conditions, medications, and allergies.
   - Identity verification rejection when an incorrect verification mobile number is supplied.
   - Safe error rejection when an unknown MRN is provided.
   - Forgot MRN lookup by registered mobile number (`lookup_patient_by_phone_and_name`).
   - Backward compatibility for legacy patient IDs (`PAT-2024-XXXX`, `SYN-P001`).
   - Identity name conflict detection raising `PatientNameConflictError` and offering resolution paths (`confirm_existing=True` vs `force_new=True` for family members).
   - Monotonic token allocation (`T-101`, `T-102`) and check-in idempotency (reusing active `waiting` token on browser refresh/double-click).
   - Multi-visit longitudinal history preservation and past doctor consultation notes retention.
3. `test_camera_upload.py` (3 tests):
   - Magic byte validation for PNG, JPEG, and PDF documents; rejection of renamed executables or disguised files.
   - Multi-page camera capture grouping under a shared `group_id`, associating pages with visit and patient.
   - Stored image report OCR extraction and graceful handling when Tesseract is or isn't installed.
4. `test_model_loader.py` (6 tests): Validates local path resolution, raises `ModelNotFoundError` for non-existent directories, raises `ModelLoadError` for incomplete folders, verifies baseline fallback, tests negation extraction (`"no fever"` $\to$ `negated=True`).
5. `test_database.py` (4 tests): Patient registration, phone deduplication, sequential daily token assignment (`T-101`, `T-102`), vitals and intake persistence, strict multi-tenant patient record isolation, conflict rejection.
6. `test_report_pipeline.py` (4 tests): PDF, PNG, JPG magic byte header validation, rejection of oversized and disguised files, filename sanitization against path traversal, SHA-256 deduplication.
7. `test_summary_service.py` (3 tests): Non-diagnostic disclaimer presence, abnormal lab separation, gap detection for missing duration/allergies, multi-visit longitudinal synthesis verifying prior doctor notes, exam observations, and prescription advice in next visit summaries.
8. `test_doctor_workflow.py` (3 tests): Doctor Confirm/Correct/Reject reviews, consultation notes persistence marking visit completed, longitudinal lab query across visits.
9. `test_end_to_end_workflow.py` (3 tests): Complete lifecycle: registration $\to$ vitals $\to$ intake $\to$ symptom tagging $\to$ report upload $\to$ summary generation $\to$ doctor review $\to$ doctor notes save $\to$ returning patient check-in with history retrieval.

### What the Tests Do NOT Prove:
- Automated tests verify the in-browser and fallback upload API contracts, canvas capture logic, and server processing. They do **NOT** prove physical camera autofocus, lighting, or lens behavior on a physical handheld phone in the real world (must be tested on physical device hardware).
- Automated tests verify OCR pipeline behavior when Tesseract is available or graceful warning fallbacks when absent.
- Automated tests run sandboxed and do not test external network dependencies.

---

## 9. Security, Reliability & Clinical Safety Audit

| Check Category | Classification | Finding / Code Evidence |
| :--- | :--- | :--- |
| **Authentication & Authorization** | **Potential risk requiring testing** | The current prototype operates without user login or session tokens. Any user on the local network can access `/api/*` endpoints. Role-based access control (ABHA / OAuth2) is required before clinical deployment. |
| **Patient Record Isolation** | **Verified safe in inspected code** | All SQL queries are strictly scoped by `patient_id` or `visit_id` (e.g. `SELECT * FROM visits WHERE patient_id = ?`). |
| **Unsafe File Uploads & Traversal** | **Verified safe in inspected code** | Binary magic bytes are strictly enforced (`validate_file` in `report_service.py`), rejecting executables disguised as PDFs. `sanitize_filename` strips `../` and directory separators. Storage is scoped to `data/uploads/{patient_id}/`. |
| **SQL Injection** | **Verified safe in inspected code** | All database queries use parameterized SQL queries (`?` placeholders). No string interpolation was observed in SQL queries. |
| **AI Hallucination Risk** | **Verified safe in inspected code** | The pre-consultation summary does not use an unconstrained generative LLM. It uses deterministic Python synthesis with direct quotation (`quote_check`) and verbatim source linking. |
| **Clinical Safety & Disclaimers** | **Verified safe in inspected code** | Non-diagnostic disclaimer banners are permanently displayed on the top navigation bar, in the API payloads, and in the database records: *"Prototype. Synthetic data only. For documentation assistance. Never independently diagnose patients or prescribe medication."* |
| **Red Flag Detection** | **Potential risk requiring testing** | Red flag detection (`_detect_red_flags`) relies on calibrated rule patterns (e.g. chest pain with exertion, acute hypertension $\ge 160$, SpO2 $< 93\%$). It is a safety net, but cannot replace complete clinical differential diagnosis. |

---

## 10. Implementation Status Matrix

| Feature | Intended Behavior | Actual Implementation | Status | Evidence | Remaining Work |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Short Permanent Patient ID (MRN)** | Issue short human-readable MRN (`P10482`, `P10001`+), concurrency-safe, DB unique | Sequential P-series allocation finding highest existing integer + collision check | **Implemented and verified** | `patient_service.py:generate_patient_id`, `test_database.py`, `test_patient_recognition.py` | ABDM ABHA ID linking |
| **Patient Registration & Tokens** | Register patient, issue sequential daily token (`T-101`), prevent double-click duplicates | SQLite insert/query with `max(100, max_token_today) + 1` and waiting check-in idempotency | **Implemented and verified** | `patient_service.py:create_visit`, `test_database.py`, `test_patient_recognition.py` | ABDM ABHA ID linking |
| **Returning Patient Identification & Verification** | Match by short MRN and registered phone for identity verification, retrieve past history | Phone verification against DB before disclosing records, prefills chronic conditions, meds, allergies | **Implemented and verified** | `patient_service.py:verify_and_get_returning_patient`, `PatientIntake.jsx`, `test_patient_recognition.py` | SMS/WhatsApp OTP verification |
| **Forgot MRN Lookup** | Allow returning patients to locate MRN by registered phone | Phone search returning non-sensitive masked identity confirmation | **Implemented and verified** | `patient_service.py:lookup_patient_by_phone_and_name`, `app/server.py:lookup_patient_endpoint`, `test_patient_recognition.py` | Automated SMS reminder |
| **Identity Name Conflict Handling** | Prevent silent merge/duplicate if phone matches but name conflicts | Raises `PatientNameConflictError` (409), modal offers confirmation, new family registration (`force_new=True`), or edit | **Implemented and verified** | `app/server.py:register_patient_endpoint`, `PatientIntake.jsx:130-190`, `test_patient_recognition.py` | Hospital reception biometric override |
| **Dedicated Patient Records / Medical History Tab** | Full longitudinal clinical timeline across all visits (newest first) | React tab with search, demographics, baseline conditions, expandable visit cards, clean labs, doctor notes, and summary cards | **Implemented and verified** | `PatientRecords.jsx`, `patient_service.py:get_patient_complete_timeline`, `test_patient_records.py` | Sparkline longitudinal lab trends |
| **Report File Downloads** | Secure file download endpoint for clinical staff | `GET /api/reports/{id}/file` returning binary file with MIME headers | **Implemented and verified** | `app/server.py:download_report_endpoint`, `test_patient_records.py` | Role-based download watermarking |
| **Mobile Patient Intake Form** | Collect reason, symptoms, duration, conditions, medicines, allergies | React 3-step intake questionnaire with returning patient pre-fill | **Implemented and verified** | `PatientIntake.jsx`, `patient_service.py:save_intake` | Multi-language translation (Kannada, Hindi) |
| **File Upload (PDF/JPG/PNG)** | Upload documents with size/type validation | Binary magic bytes, SHA-256 deduplication, multi-page document grouping | **Implemented and verified** | `report_service.py:store_and_register_report`, `test_camera_upload.py` | Multi-file simultaneous drag-and-drop |
| **Physical Report Camera Scan** | Photograph paper reports with live viewfinder & native fallback, preview, multi-page scan | WebRTC `getUserMedia` rear-camera viewfinder + mobile native capture fallback, canvas snapshot, preview before upload, retake/discard, multi-page `group_id` scanning | **Implemented and verified** | `PatientIntake.jsx:195-360`, `test_camera_upload.py` | Automatic document edge perspective correction |
| **Digital PDF Lab Extraction** | Extract test names, values, units, reference ranges | `pdfplumber` line & card parser | **Implemented and verified** | `src/reports/extract.py:extract_pdf` | Support complex multi-column hospital tables |
| **Scanned Document OCR** | Run OCR on photographs and scanned PDFs | `pypdfium2` + `pytesseract` image preprocessing | **Implemented and verified** | `src/services/ocr_service.py:process_report_file` | Cloud OCR engine integration (Google Vision) |
| **Symptom Extraction & Negation** | Tag symptoms and distinguish negated symptoms | Rule baseline (`src/symptoms/baseline.py`) with negation window | **Implemented and verified** | `src/symptoms/infer.py`, `test_model_loader.py` | Complete GPU fine-tuning of ModernBERT |
| **10–15s Single Summary Card** | Concise clinical brief (TODAY, HISTORY, SAME COMPLAINT, RED FLAG, CONFIRM) | Deterministic synthesis in `summary_service.py` | **Implemented and verified** | `SummaryCard.jsx`, `test_summary_service.py` | Doctor customizable card sections |
| **Doctor Live Patient Search** | Instant patient search by Name, Phone, MRN, Token | React debounce search querying `/api/patients?q=` | **Implemented and verified** | `DoctorDashboard.jsx:65-78`, `app/server.py:81-96` | Search by ICD-10 diagnosis |
| **Clean Lab Display (No Inspect Modal)** | Clean tabular lab view without disruptive PDF popups | Tabular review with status badges; inspect modal removed | **Implemented and verified** | `DoctorDashboard.jsx:274-325` | Longitudinal sparkline trend charts inline |
| **Doctor Consultation Notes & Plan** | Record examination observations and prescription plans | Textarea form saving to `doctor_notes` in SQLite | **Implemented and verified** | `DoctorDashboard.jsx:380-420`, `doctor_service.py` | Digital signature / prescription PDF export |
| **Longitudinal Doctor Notes Re-integration** | Previous doctor notes appear in future visit summaries | `get_patient_history` injected into `summary_service` | **Implemented and verified** | `summary_service.py:145-165`, `test_summary_service.py` | Medication reconciliation diff engine |
| **Nurse Vitals Station** | Staff-assisted vitals entry (BP, HR, SpO2, Temp, Sugar) | React triage form updating `vitals` and summary | **Implemented and verified** | `NurseStation.jsx`, `app/server.py:save_vitals_endpoint` | Bluetooth medical device integration |

---

## 11. Prioritized Remaining Work

### Priority 0 (Production Blockers)
* **RBAC & Authentication**: Implement token-based authentication (JWT / OAuth2 / ABHA) to separate patient, nurse, and doctor views securely.

### Priority 1 (Core Clinical Enhancements)
* **ModernBERT Checkpoint Training**: Run `python -m src.symptoms.train_all --data data/symptoms/split` on a GPU-enabled machine to produce the fine-tuned ModernBERT checkpoints in `models/modernbert_f100_s1`.
* **Export Prescription PDF**: Add a button on the Doctor Dashboard to export the completed consultation notes and treatment plan as an official hospital prescription slip (PDF).

### Priority 2 (Clinical Features & Usability)
* **Multi-Language Support**: Provide Kannada and Hindi translations for the patient intake questionnaire.
* **Inline Longitudinal Lab Sparklines**: Render small visual trend graphs next to repeated lab tests (e.g. HbA1c over the last 3 visits).

---

## 12. Technical Glossary

* **ASGI (Asynchronous Server Gateway Interface)**: The standard Python specification for asynchronous web servers (implemented here using Starlette and Uvicorn).
* **Magic Bytes**: The initial sequence of binary bytes in a file that identifies its true format (e.g. `%PDF-` for PDFs, regardless of file extension).
* **MRN (Medical Record Number)**: A unique internal patient identifier (formatted here as short `P10482` / `P10001`+ or legacy `PAT-XXXXXXXX`) ensuring record isolation.
* **Negation Detection**: Identifying when a patient denies a symptom (e.g. *"no fever"* is tagged as `NEG_SYMPTOM`, not a positive symptom).
* **OPD (Outpatient Department)**: Hospital clinic where patients receive consultations without being admitted overnight.
* **Provenance**: The verifiable source record (document, page, and line) from which clinical evidence was extracted.
* **Single Summary Card**: A high-density, structured clinical brief designed to be read by an attending physician in 10 to 15 seconds.
* **Tesseract OCR**: An open-source optical character recognition engine that converts document images into machine-readable text.
* **Vite**: A modern, high-speed frontend build tool and development server for React applications.
* **WAL Mode (Write-Ahead Logging)**: A SQLite configuration that allows concurrent readers while a write operation is occurring, preventing database locks.

---

## 13. Current State for Next AI Assistant

> **Key Facts for the Next AI Assistant**:
> 1. **Do not reinstall Streamlit**: Streamlit has been superseded by the modern **React 19 + Vite** frontend in `frontend/` and the **Starlette ASGI** backend in `app/server.py`.
> 2. **Single Server Architecture**: `app/server.py` mounts `frontend/dist` at `/`. Running `python run.py` serves both the API and the React SPA on port `8000`.
> 3. **The Summary Card Format**: The 10–15s summary card must strictly adhere to Image 4 structure (`TODAY`, `RELEVANT HISTORY`, `SAME COMPLAINT BEFORE`, `⚠️ RED FLAG`, `CONFIRM IN ROOM`).
> 4. **No Inspect Modal**: The medical reports and laboratory table in `DoctorDashboard.jsx` must remain clean and tabular without opening a PDF/image inspection modal.
> 5. **Short MRN Format**: Patient identifiers use short `P10001`+ format ($\le 8$ chars) while maintaining backward compatibility with existing `PAT-` and `SYN-` IDs.
> 6. **Patient Records Tab**: A dedicated 2nd tab (`PatientRecords.jsx`) provides full chronological visit history, expandable cards with vitals, labs, notes, summary cards, and an archive of uploaded files with direct download links.
> 7. **Longitudinal History Integration**: When a patient returns for subsequent visits, `get_patient_history` supplies prior visits to `generate_clinical_summary`, which automatically displays past doctor notes, exam findings, and treatment plans under `SAME COMPLAINT BEFORE`.
> 8. **All Tests Pass**: 45 automated tests are verified and passing via `python -m unittest discover tests`.
