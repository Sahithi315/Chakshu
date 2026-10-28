# Product Requirements Document: Provenance-Linked Clinical Context Platform

**Working product name:** Clinical Context Platform (CCP)  
**Document version:** 1.0  
**Status:** Product definition / pre-pilot  
**Primary market:** Indian outpatient departments (OPDs), clinics, polyclinics and small-to-mid-sized hospitals  
**Initial clinical wedge:** Diabetes and general-medicine follow-up OPDs  
**Primary users:** Patients, caregivers, nurses, doctors and hospital administrators  
**Document owner:** Product team  
**Last updated:** 28 October 2026

---

## 1. Executive summary

Indian doctors often have only a few minutes with each outpatient. During that time, they must reconstruct the patient's current complaint, previous diagnoses, medication use, allergies, test results and changes since the previous visit. The information is frequently distributed across the patient's memory, paper prescriptions, WhatsApp PDFs, photographs, multiple laboratories and disconnected hospital systems.

The Clinical Context Platform turns the patient's waiting time into structured clinical preparation. After receiving a token, the patient or caregiver provides symptoms and uploads relevant records. A nurse records current vitals. The platform extracts facts from documents, reconciles medication evidence and organizes longitudinal changes. The doctor receives a concise, provenance-linked clinical brief before beginning the consultation.

The system is not intended to diagnose, prescribe, replace a doctor or independently determine treatment. It is a clinical-context and reconciliation system. Every clinically meaningful item must identify where it came from, when it was recorded, how confident the system is and whether a qualified person has verified it.

The product's central promise is:

> Give the doctor a trustworthy, source-linked view of what matters now, what changed and what still needs verification—without making the doctor search through multiple documents.

### 1.1 Novelty position

Electronic records, OPD token systems, nurse vitals entry and AI report explanations already exist in India. This product will therefore not claim novelty merely because it digitizes records or summarizes a PDF. Its differentiation will be the combination of five product pillars:

1. A provenance-linked clinical brief.
2. Medication reconciliation based on evidence rather than patient memory alone.
3. Longitudinal change detection across visits and documents.
5. A workflow designed for real Indian OPD constraints.
6. ABDM-compatible, consent-driven interoperability instead of another isolated record store.

The numbering above intentionally preserves the original product-idea numbering.

---

## 2. Problem statement

### 2.1 Core problem

Doctors frequently begin consultations without a dependable, current and reviewable picture of the patient. Patients may forget the names or doses of medicines, omit older conditions, confuse dates, or bring multiple unorganized documents. Nurses may record vitals on paper or in a system that does not present them effectively to the doctor. Existing software often stores records but does not reconcile contradictions, highlight meaningful changes or make every summary statement traceable to its source.

### 2.2 Consequences

- Consultation time is spent reconstructing history instead of discussing care.
- Current and discontinued medicines can be confused.
- Duplicate brands containing the same active ingredient may go unnoticed.
- Trends such as gradually increasing HbA1c or blood pressure may be hidden across reports.
- Previously requested investigations or follow-up actions may be missed.
- AI-generated summaries may look authoritative even when based on uncertain OCR or incomplete context.
- Patients repeat the same information at registration, nursing and consultation desks.
- Hospitals create additional data silos when new tools do not integrate with existing HMIS or ABDM infrastructure.

### 2.3 Opportunity

The waiting period before an OPD consultation can be converted into useful preparation time. A patient, caregiver and nurse can collectively create a structured encounter packet that the doctor reviews, corrects and approves. The product succeeds if it improves the doctor's situational awareness without increasing cognitive burden or creating false confidence.

---

## 3. Product vision and principles

### 3.1 Vision

To make every Indian outpatient consultation begin with a clear, current, source-verifiable understanding of the patient.

### 3.2 Product principles

1. **Evidence before inference:** Show extracted facts and their sources before offering an AI interpretation.
2. **Doctor remains responsible:** AI prepares and organizes; a registered medical practitioner decides.
3. **Uncertainty must be visible:** Illegible, conflicting or incomplete information must never be silently converted into certainty.
4. **No repeated questions without reason:** Previously captured information should be reused, while still allowing confirmation of changes.
5. **Fit the OPD:** Each role should complete its part quickly on inexpensive, familiar devices.
6. **Patient-controlled sharing:** Access must be purpose-specific, time-bound where appropriate and revocable.
7. **Interoperate rather than imprison:** Records should be exchangeable through ABDM-compatible mechanisms and hospital interfaces.
8. **Safety over impressiveness:** A short, traceable brief is preferable to a sophisticated but ungrounded narrative.

---

## 4. Goals, non-goals and success definition

### 4.1 Product goals

- Present the doctor with a reviewable clinical brief before the consultation begins.
- Trace every brief item to a patient statement, nurse measurement, uploaded document, imported record or explicit AI inference.
- Reconcile medication evidence across prescriptions, patient statements and current hospital records.
- Identify meaningful changes across time rather than explaining each document in isolation.
- Work in multilingual, caregiver-assisted and low-connectivity OPD environments.
- Support consent-based import and sharing of ABHA-linked health records through an approved ABDM integration path.
- Integrate into existing hospital workflows with minimal duplicate data entry.
- Produce measurable reductions in history-reconstruction time and medication discrepancies.

### 4.2 Non-goals for the initial product

- Autonomous diagnosis.
- Autonomous prescribing or dosage changes.
- Declaring that a medicine interaction is clinically safe or unsafe without doctor review.
- Replacing emergency triage, physical examination or clinical judgment.
- Interpreting raw radiology images, pathology slides, ECG waveforms or other diagnostic signals.
- Becoming a full hospital billing, pharmacy, bed-management or laboratory-information system.
- Replacing the hospital's existing HMIS where one is already operational.
- Allowing an AI-generated statement to enter the permanent clinical record without human confirmation.

### 4.3 Pilot success criteria

The first controlled pilot will be considered successful if, compared with the pre-pilot baseline:

- Median doctor time spent reconstructing history decreases by at least 30%.
- At least 90% of generated briefs are opened before or during the consultation.
- At least 80% of doctors rate the brief as useful or very useful.
- At least 95% of high-importance extracted items provide a working source link.
- At least 90% of structured medication fields accepted by a doctor are accurate.
- Fewer than 2% of reviewed briefs contain a clinically material unsupported statement.
- At least 70% of eligible patients complete intake without staff completing the entire form for them.
- Median nurse vitals-entry time remains below 90 seconds.
- No severe privacy or security incident occurs.

These are pilot targets, not claims of clinical benefit. Final thresholds must be reviewed by clinical and safety advisors before deployment.

---

## 5. Target users and jobs to be done

### 5.1 Patient

**Context:** Has received a token or appointment and is waiting for consultation. May have low health literacy, limited English proficiency, limited data connectivity or no installed app.

**Jobs to be done:**

- Describe the current problem in a familiar language.
- Confirm demographics, allergies, known conditions and current medicines.
- Upload or photograph relevant prescriptions and reports.
- Correct information extracted from a document.
- Authorize access to existing records for the current care purpose.
- Understand which information still needs discussion with the doctor.

### 5.2 Caregiver

**Context:** Assists a child, older adult, disabled person or patient who does not use a smartphone independently.

**Jobs to be done:**

- Complete intake on behalf of the patient with a clearly recorded relationship and authority.
- Manage multiple family members without mixing their records.
- State whether an answer is personally known, patient-reported or inferred from a document.
- Upload and organize records held by the family.

### 5.3 Nurse or clinical assistant

**Jobs to be done:**

- View the correct patient in the live queue.
- Record vitals rapidly with units, time and device/manual method.
- Repeat or correct implausible measurements.
- Record a short structured note or voice intake where required.
- Escalate visibly abnormal observations according to hospital protocol.
- Avoid making diagnostic conclusions outside the role's scope.

### 5.4 Doctor

**Jobs to be done:**

- Understand the chief complaint and important context within approximately 30 seconds.
- Distinguish new information from historical information.
- Verify any statement by opening its source.
- Review medication conflicts and patient-reported adherence.
- See longitudinal trends with dates, units and reference ranges.
- Accept, correct or reject extracted and AI-generated information.
- Transfer approved information into the encounter note or HMIS.

### 5.5 Hospital administrator

**Jobs to be done:**

- Configure departments, roles, devices, intake templates and integration settings.
- Ensure staff only access patients within their responsibilities.
- Review audit logs and operational metrics.
- Configure retention and consent policies.
- Monitor queue completion without viewing unnecessary clinical details.

### 5.6 Clinical safety or data-quality reviewer

**Jobs to be done:**

- Review extraction failures, unsupported statements and user corrections.
- Monitor model and rule performance across languages, document types and demographic groups.
- Approve versioned changes to clinical rules.
- Investigate safety incidents with a complete audit trail.

---

## 6. End-to-end user journey

### 6.1 Standard returning-patient journey

1. Reception creates or confirms the OPD encounter and assigns a token.
2. The patient receives a QR code, SMS or WhatsApp link. No app installation is required.
3. The patient sees a short consent and purpose notice in the selected language.
4. The patient confirms identity using the hospital-approved mechanism.
5. The platform offers to import permitted ABHA-linked or hospital records, if integration and consent are available.
6. The patient provides the current complaint through text, guided choices or voice.
7. The patient confirms current medicines, allergies, pregnancy status where relevant and important changes since the previous visit.
8. The patient or caregiver uploads new prescriptions, laboratory reports or discharge summaries.
9. The platform processes documents and requests confirmation only for uncertain or conflicting high-value information.
10. A nurse opens the patient from the live queue and records current vitals.
11. The system composes a draft clinical brief, clearly separating facts, unresolved discrepancies, rule-based alerts and AI-generated synthesis.
12. The doctor opens the brief, reviews changes and source evidence, and corrects or confirms relevant items.
13. Approved data is written to the encounter record or passed to the HMIS through the supported integration.
14. Any new prescription, investigation or follow-up instruction is linked to the encounter and made available to the patient according to the hospital workflow.

### 6.2 New-patient journey

The workflow is similar, but the system must not imply that absence of imported history means absence of disease or medication. The brief must display: **“No prior records available in this system”** rather than **“No medical history.”**

### 6.3 Patient without a smartphone

- Reception prints or displays the token as usual.
- Intake is completed on a kiosk, shared tablet or staff device.
- The system records who entered the data and whether answers came directly from the patient or caregiver.
- Consent must not be bundled with unrelated hospital services.

### 6.4 Emergency or severely unwell patient

The digital intake must be bypassable immediately. The platform must never delay urgent clinical care. Staff can mark the encounter as emergency-bypass and complete documentation later.

---

## 7. Clinical brief information architecture

The doctor view must fit on one primary screen at common clinic-desktop resolutions. It may expand into detailed panels, but it must not require opening multiple pages to understand the encounter.

### 7.1 Recommended brief order

1. Patient identity and encounter context.
2. Immediate safety banner, only when a configured rule or staff escalation applies.
3. Chief complaint and duration.
4. What changed since the previous encounter.
5. Current nurse-measured vitals with time.
6. Current medicines and medication discrepancies.
7. Allergies and adverse reactions.
8. Relevant diagnoses and important history.
9. Significant laboratory trends.
10. Pending follow-ups or previously requested investigations.
11. Unresolved questions requiring confirmation.
12. Source and audit access.

### 7.2 Evidence classes

Every item must be assigned one evidence class:

- **Patient reported**
- **Caregiver reported**
- **Measured by nurse/staff**
- **Entered by doctor**
- **Extracted from uploaded document**
- **Imported from hospital system**
- **Imported through ABDM-authorized exchange**
- **Calculated from verified inputs**
- **Rule-generated alert**
- **AI inference—doctor confirmation required**

### 7.3 Verification states

- Unreviewed
- Patient confirmed
- Staff confirmed
- Doctor confirmed
- Corrected by doctor
- Rejected
- Superseded
- Source unavailable

The evidence class and verification state are separate. For example, a medicine can be “Extracted from prescription” and later “Doctor confirmed.”

---

## 8. Novelty pillar 1: Provenance-linked clinical brief

### 8.1 Objective

Make every important clinical statement auditable and easy to verify, reducing the risk that an incorrect extraction or AI inference is mistaken for a clinical fact.

### 8.2 Functional requirements

**PROV-001 — Source label**  
Every displayed clinical item must show a short source label, including actor/source type and timestamp or document date where available.

Examples:

- Patient reported today at 09:18
- Measured by nurse Anita at 10:42
- Extracted from Apollo laboratory report dated 12 August 2026
- Medication found in prescription dated 4 March 2025
- Imported through patient-authorized ABDM exchange
- AI inference—doctor confirmation required

**PROV-002 — One-action evidence access**  
The doctor must be able to open the original evidence in one click or tap from the brief item.

**PROV-003 — Precise document reference**  
For a document-derived item, the evidence view must show the relevant page and visually highlight the exact line, table row or region from which the value was extracted. If precise highlighting is not technically possible, the system must say so and open the relevant page.

**PROV-004 — Immutable source preservation**  
The original uploaded file must be preserved according to the applicable retention policy. Processing must use derived copies so that rotation, enhancement or OCR does not overwrite the original evidence.

**PROV-005 — Transformation history**  
The system must record transformations such as OCR, language translation, unit normalization, medicine-brand mapping and manual correction.

**PROV-006 — Confidence display**  
Confidence must be displayed for uncertain extraction in plain language: high confidence, review suggested or unable to read. A raw model probability must not be shown without explanation.

**PROV-007 — No-source behavior**  
If an item cannot be linked to evidence, it must be labeled “Source unavailable” and excluded from automatic promotion into the verified record.

**PROV-008 — Corrections**  
Authorized staff and doctors must be able to correct an item without erasing the original extraction. The audit trail must preserve original value, corrected value, actor, reason and timestamp.

**PROV-009 — Inference separation**  
AI inference must appear in a visually distinct section and must never be styled identically to measured or document-extracted facts.

**PROV-010 — Summary grounding**  
Every sentence in an AI-generated doctor summary must reference one or more structured facts or source records. Unsupported sentences must be blocked from display.

### 8.3 Acceptance criteria

- Selecting a laboratory value opens the source document at the correct page and highlighted row.
- A corrected extraction retains both the original and corrected value in audit history.
- Removing source access changes the item state to “Source unavailable”; it does not silently leave a verified-looking statement.
- An AI sentence without supporting source identifiers fails automated validation and is not shown to the doctor.
- Exported briefs retain human-readable source references, even if interactive links cannot be preserved.

---

## 9. Novelty pillar 2: Medication reconciliation

### 9.1 Objective

Create an evidence-based working medication list while exposing disagreements between prescriptions, patient statements and hospital records. The system assists reconciliation but does not decide treatment.

### 9.2 Medication data model

Each medication evidence record should support:

- Brand name as written.
- Normalized brand name.
- Active ingredient or salt, when confidently mapped.
- Strength and unit.
- Dosage form.
- Dose per administration.
- Frequency.
- Route.
- Duration or start/end date.
- Indication, if explicitly stated.
- Prescriber and facility, if available.
- Source document and precise location.
- Extraction confidence.
- Patient-reported use status.
- Clinician verification state.
- Last confirmed date.

### 9.3 Medication status vocabulary

- Prescribed—current status unknown
- Patient reports currently taking
- Patient reports taking differently
- Patient reports stopped
- Course apparently completed
- Doctor confirmed active
- Doctor discontinued
- Unable to identify

The system must avoid treating a historical prescription as proof that a medicine is still being taken.

### 9.4 Functional requirements

**MED-001 — Multi-source extraction**  
Extract medication information from supported printed prescriptions, discharge summaries, patient-entered lists and HMIS/ABDM records.

**MED-002 — Indian brand normalization**  
Map Indian brand names to active ingredients using a maintained, versioned medication terminology source. Mapping confidence and database version must be retained.

**MED-003 — Duplicate evidence flag**  
Flag probable duplicate active ingredients or same-brand entries. Phrase the output as a review prompt, not a clinical conclusion.

Example: “Two entries may contain metformin. Confirm whether both are currently used.”

**MED-004 — Conflicting dose flag**  
When sources show different strengths, frequencies or instructions for a possibly identical medicine, display both versions, dates and sources side by side.

**MED-005 — Expired or completed course flag**  
Identify that a stated duration appears to have ended, while clearly saying that actual current use is unconfirmed.

**MED-006 — Stopped-medicine capture**  
Allow the patient to mark a medicine as stopped and optionally give a reason. This must not overwrite the prescription evidence.

**MED-007 — Allergy comparison**  
If a medication ingredient appears to match a recorded allergy, present an urgent review prompt with both sources. Do not claim a confirmed allergy interaction when mapping is uncertain.

**MED-008 — Illegible handwriting handling**  
If confidence is below the approved threshold, show the cropped source region and ask for human confirmation. The system must not guess a medicine name merely to complete the field.

**MED-009 — Doctor action**  
The doctor can confirm, correct, discontinue or leave unresolved each medication. Bulk confirmation must be disabled for unresolved conflicts.

**MED-010 — No autonomous interaction advice**  
Medication interaction information, if introduced in a later regulated release, must provide evidence and require clinician review. The MVP will not recommend starting, stopping or changing a medicine.

### 9.5 Acceptance criteria

- Two prescriptions containing different brands of the same confidently mapped salt generate a probable-duplicate review item.
- A patient marking a medicine “stopped” does not delete the historical prescription.
- A low-confidence handwritten medicine is displayed as unresolved with its source crop; it is not added to the active list automatically.
- Conflicting doses show date, source and verification status for both values.
- The final active-medication list cannot be labelled “doctor confirmed” until a doctor explicitly confirms it.

---

## 10. Novelty pillar 3: Longitudinal patient context

### 10.1 Objective

Help the doctor understand change across time instead of reading isolated reports.

### 10.2 Functional requirements

**LONG-001 — Normalized timeline**  
Create a chronological timeline of encounters, documents, measurements, prescriptions, laboratory results and follow-up instructions.

**LONG-002 — Laboratory normalization**  
Normalize test names and compatible units while retaining the exact original value, unit, reference range and laboratory source.

**LONG-003 — Reference-range awareness**  
Do not compare flags solely by color or “H/L” markers. Preserve laboratory-specific reference ranges and acknowledge that ranges can differ by laboratory, method, age, sex or pregnancy status.

**LONG-004 — Trend presentation**  
Display numerical trends with dates and sources, for example: HbA1c 7.1% → 7.8% → 8.4%. Charts must permit opening every point's evidence.

**LONG-005 — Vital trends**  
Display BP, pulse, temperature, SpO2, weight and other configured measurements over time, clearly distinguishing clinic measurements from patient-entered home readings.

**LONG-006 — Change since last visit**  
Generate a concise comparison covering new symptoms, resolved symptoms, medication changes, relevant laboratory changes and new clinical events.

**LONG-007 — Pending follow-up register**  
Capture doctor-confirmed instructions such as “repeat HbA1c in three months” or “bring thyroid report.” Show unresolved items when the expected date has passed or a result is absent.

**LONG-008 — Missing-investigation language**  
Use cautious wording: “No matching result was found in available records,” never “The patient did not complete the test,” unless explicitly confirmed.

**LONG-009 — Contradictory history**  
If sources disagree—for example, different diabetes-onset years—show the discrepancy rather than selecting one answer invisibly.

**LONG-010 — Relevance control**  
Allow the doctor to filter the timeline by specialty, condition, document type, test or date range. The default brief should show only encounter-relevant history.

### 10.3 Acceptance criteria

- Trend values with compatible units appear in one series; incompatible or unknown units remain separate.
- Every chart point opens its source evidence.
- Home BP readings and nurse-measured clinic readings are visually distinguishable.
- A missing expected result is worded as absent from available records, not as patient noncompliance.
- A corrected historical value updates the trend while preserving audit history.

---

## 11. Novelty pillar 5: Designed for Indian OPD reality

### 11.1 Multilingual and voice intake

**IND-001** — Support English, Hindi and Hinglish in the first pilot. Add regional languages only after language-specific clinical validation.  
**IND-002** — Patients may answer using speech, text or guided selections.  
**IND-003** — Preserve the original audio only with explicit consent and a defined retention period. Otherwise retain the transcript and delete the audio after successful processing.  
**IND-004** — Store original-language text alongside translation. Clinical users must be able to view both.  
**IND-005** — For high-risk questions, confirm the interpreted meaning back to the patient in the selected language.

### 11.2 Caregiver mode

**IND-006** — Capture caregiver name, relationship, contact information where required and basis of authority.  
**IND-007** — Clearly label every caregiver-provided answer.  
**IND-008** — Prevent accidental switching between family-member records by displaying patient name, age and photograph or another hospital-approved identifier throughout intake.  
**IND-009** — Support guardian workflows for minors and decision-support workflows for adults without independent digital access, subject to legal review.

### 11.3 No-install access

**IND-010** — Provide secure web intake through SMS/WhatsApp link or QR scan without requiring an app.  
**IND-011** — Links must be short-lived, scoped to the intended encounter and protected against access through forwarded messages.  
**IND-012** — Kiosk mode must clear session data automatically and prevent the next patient from seeing previous information.

### 11.4 Low-connectivity and low-cost devices

**IND-013** — The nurse workflow must be usable on a low-cost Android device with a small screen.  
**IND-014** — Draft structured intake and vitals locally during a network interruption and synchronize when connectivity returns.  
**IND-015** — Clearly show unsynced status. Safety-relevant information must not appear available to the doctor until synchronization succeeds, unless both users are operating through an approved local-network mode.  
**IND-016** — Resolve conflicting offline edits without silently overwriting either version.  
**IND-017** — Optimize the intake bundle and avoid downloading historical documents unless opened.

### 11.5 Document realities

**IND-018** — Accept PDF, JPEG, PNG and camera capture in the MVP.  
**IND-019** — Detect rotation, blur, glare, cropped content and low resolution before accepting a photograph.  
**IND-020** — Guide the patient to retake poor images.  
**IND-021** — Support multi-page documents and preserve page order.  
**IND-022** — Printed reports are supported in the MVP; handwritten prescription extraction remains assisted and must default to human verification.  
**IND-023** — Detect probable duplicates using document fingerprints while preserving separately uploaded originals when legally required.

### 11.6 Specialty templates

The pilot will include:

- General medicine acute complaint intake.
- Diabetes follow-up intake.

Later candidates include antenatal care, cardiology and geriatrics. Templates must be versioned, clinically reviewed and configurable without changing source code. A template must identify why each question is needed and what role can view the response.

### 11.7 HMIS integration

**IND-024** — Support standalone pilot mode and a documented API integration mode.  
**IND-025** — Reuse the hospital's patient and encounter identifiers.  
**IND-026** — Avoid forcing doctors to maintain two independent encounter notes.  
**IND-027** — Provide standards-based structured export where the target system supports it, with PDF fallback only when structured exchange is unavailable.  
**IND-028** — Integration failure must be visible and retryable; it must not falsely show that a record was saved to the HMIS.

---

## 12. Novelty pillar 6: ABDM-compatible interoperability

### 12.1 Objective

Enable consent-based access to existing health information and sharing of newly created records without making the product an isolated patient-record silo.

### 12.2 Product position in the ABDM ecosystem

The final architecture and organizational roles must be validated with an ABDM integration specialist. Depending on deployment, the platform may integrate through an established ABDM-enabled hospital/HMIS partner or pursue the applicable roles and certifications itself.

The product must not claim ABDM certification, compliance milestones or production connectivity until formally validated and approved.

### 12.3 Functional requirements

**ABDM-001 — ABHA capture**  
Support optional ABHA number/address capture and approved identity flows. A patient must not be denied essential care merely for not having or not sharing an ABHA identifier.

**ABDM-002 — Purpose-specific consent**  
Before requesting records, explain what data is requested, why, who will access it and for how long.

**ABDM-003 — Time-bound access**  
Where supported, patients can grant access limited to the current encounter or a defined follow-up period.

**ABDM-004 — Revocation**  
Patients can revoke future access through the relevant consent mechanism. Revocation effects and legally retained encounter records must be explained accurately.

**ABDM-005 — Import provenance**  
Imported data must retain originating facility, record type, creation date, import date and consent reference.

**ABDM-006 — Deduplication**  
If a patient uploads a file that also arrives through an authorized record exchange, the system should identify probable duplication without discarding either source silently.

**ABDM-007 — Structured record support**  
Use current ABDM-supported standards and profiles appropriate to the record type. Version compatibility must be tested and documented.

**ABDM-008 — Consent receipt**  
Provide a human-readable consent receipt or history accessible to the patient.

**ABDM-009 — Failure fallback**  
If ABDM services are unavailable, continue the permitted local OPD workflow and clearly state that external records could not be fetched. Do not treat this as evidence that no external record exists.

**ABDM-010 — Minimal disclosure**  
Request and disclose only the categories and time period necessary for the stated care purpose.

### 12.4 Authoritative references

- ABDM Health Data Management Policy: <https://abdm.gov.in/publications/policies_regulations/health_data_management_policy>
- ABDM official site: <https://abdm.gov.in/>

Implementation teams must consult the current ABDM technical documentation and sandbox requirements because APIs and certification processes can change.

---

## 13. AI and document-processing requirements

### 13.1 Processing pipeline

1. Malware and file validation.
2. Image-quality assessment.
3. Document classification.
4. OCR and layout reconstruction.
5. Language detection.
6. Entity and table extraction.
7. Terminology and unit normalization.
8. Source-region linking.
9. Confidence scoring.
10. Conflict and duplicate detection.
11. Human confirmation where required.
12. Brief generation from approved structured facts.

### 13.2 AI output classes

- **Extraction:** What is visibly written or measured.
- **Normalization:** Mapping equivalent names or units.
- **Calculation:** Deterministic result from verified values, such as BMI.
- **Rule alert:** Output of a versioned, clinician-approved rule.
- **Inference:** AI-generated interpretation requiring confirmation.

These classes must not be merged in the user interface.

### 13.3 Safety controls

- Retrieval or generation must be limited to the current patient's authorized records.
- The system must not fill missing clinical facts from general medical knowledge.
- Summaries must be generated from structured, source-linked inputs.
- Prompt and model versions must be logged for reproducibility where legally and technically appropriate.
- Model changes require offline evaluation and controlled rollout.
- High-risk rules must be deterministic, versioned and clinician approved rather than relying only on generative AI.
- Users must be able to report an unsafe or incorrect output from the evidence view.
- AI output must never suppress the original record.

### 13.4 Model-quality evaluation

Evaluation datasets should represent:

- Multiple Indian laboratories and prescription formats.
- English, Hindi, Hinglish and later supported regional languages.
- Clear and poor-quality phone photographs.
- Printed and handwritten documents.
- Common Indian medicine brands.
- Different age groups and sexes.
- Normal, abnormal and internally contradictory reports.

Metrics must be reported by document type and language, not only as a single overall accuracy number.

---

## 14. Safety, privacy and regulatory requirements

### 14.1 Clinical safety

- The product must display that it supports, but does not replace, professional judgment.
- The clinical governance team must approve all red-flag rules and specialty templates.
- Every safety-relevant alert must show its triggering value, source, threshold/rule version and time.
- Staff must be trained that absence of an alert does not establish absence of risk.
- Emergency bypass must always be available.
- A safety-incident process must support containment, patient-impact assessment, root-cause analysis and corrective action.

### 14.2 Privacy

- Provide clear notice in the patient's selected language.
- Capture valid consent where consent is the applicable basis.
- Limit collection to necessary information.
- Support correction and applicable rights workflows.
- Define retention separately for original documents, derived data, audio, audit logs and inactive accounts.
- Do not use patient records to train general-purpose models without a separate lawful basis, explicit governance and appropriate consent where required.
- Do not sell or use clinical data for advertising.
- Perform a privacy-impact assessment before pilot deployment.

### 14.3 Security

- Encryption in transit and at rest.
- Role-based and facility-scoped access control.
- Multi-factor authentication for privileged roles.
- Short session timeouts on shared devices.
- Immutable audit logs for clinical record access and modification.
- Secure secret and key management.
- Malware scanning for uploads.
- Rate limits and abuse controls.
- Tested backup and recovery.
- Incident detection and response plan.
- Vendor and subprocessors register.
- Regular vulnerability assessment and penetration testing.

### 14.4 Regulatory review

Before production use, qualified counsel and regulatory specialists must assess:

- Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025, including phased commencement.
- ABDM Health Data Management Policy and current sandbox/production requirements.
- Applicable medical-record and professional-conduct requirements.
- Telemedicine rules if the product enables remote consultation.
- Whether any intended AI or decision-support function constitutes medical-device software under the Medical Device Rules and current CDSCO guidance.

The regulatory classification depends on intended use and claims, not merely on calling the feature “educational” or “assistive.”

---

## 15. Permissions matrix

| Capability | Patient/caregiver | Nurse | Doctor | Administrator | Safety reviewer |
|---|---:|---:|---:|---:|---:|
| Enter patient-reported information | Yes | Assisted | Yes | No | No |
| Upload records | Yes | Yes | Yes | No | Restricted |
| Record clinical vitals | No self-clinic measurement | Yes | Yes | No | No |
| View current encounter brief | Own record | Assigned patients | Assigned/authorized patients | Operational metadata only | De-identified or authorized case review |
| Confirm medication clinically | No | No | Yes | No | No |
| Correct extraction | Confirm own statement | Yes, with audit | Yes, with audit | No | Review only |
| Configure clinical rules | No | No | Clinical approver only | Operational enablement | Yes, governed workflow |
| View audit logs | Own consent/access history | Limited | Limited | Yes, facility scope | Yes, approved scope |

Exact permissions must be configurable by facility without allowing administrators to bypass clinical confidentiality unnecessarily.

---

## 16. Data model overview

Core entities:

- Patient
- Caregiver relationship
- Facility
- Practitioner/staff identity
- Encounter/token
- Consent artifact
- Source document
- Document page/source region
- Patient statement
- Observation/vital
- Laboratory result
- Medication evidence
- Reconciled medication item
- Allergy/adverse reaction
- Diagnosis/problem evidence
- Follow-up instruction
- Clinical brief and version
- Alert and rule version
- Verification action
- Audit event
- External identifier and import/export event

Every derived entity must contain references to its source entities. Deleting or restricting a source must trigger a defined review of dependent derived items.

---

## 17. Non-functional requirements

### 17.1 Performance

- Nurse vitals screen interactive within 2 seconds under pilot network conditions.
- Doctor brief opens within 3 seconds when structured data is already processed.
- A typical clear, five-page printed report should produce a draft extraction within 60 seconds under normal service conditions.
- Upload processing must be asynchronous; users may continue intake while processing occurs.

### 17.2 Availability and resilience

- Pilot target: 99.5% monthly service availability excluding scheduled maintenance.
- Graceful degradation when AI, messaging, ABDM or HMIS integrations are unavailable.
- No integration outage should block emergency or ordinary clinical care.
- Recovery objectives must be defined before live patient use.

### 17.3 Accessibility and usability

- Large touch targets and readable text for kiosk/shared-phone use.
- Screen-reader compatible patient flow where feasible.
- Do not rely on color alone for abnormal values or statuses.
- Plain-language patient prompts.
- Maximum essential patient intake target: five minutes for a returning patient, excluding document upload time.

### 17.4 Observability

- Monitor upload failures, OCR failures, synchronization conflicts, source-link failures and HMIS/ABDM integration failures.
- Clinical safety metrics must not expose patient-identifiable data in general analytics dashboards.
- Trace identifiers should allow support teams to investigate a failed workflow without broad access to clinical content.

---

## 18. Analytics and success metrics

### 18.1 North-star metric

**Percentage of eligible OPD consultations in which the doctor reviews a source-linked brief containing confirmed current vitals and at least one clinically relevant historical item.**

### 18.2 Workflow metrics

- Intake start and completion rate.
- Median patient intake time.
- Median nurse entry time.
- Percentage of briefs ready before token call.
- Brief open rate.
- Doctor review and confirmation time.
- HMIS synchronization success rate.
- ABDM record-fetch success rate where enabled.

### 18.3 Quality metrics

- Field-level extraction precision and recall.
- Medication-name, salt, strength and frequency accuracy.
- Source-link correctness.
- Unsupported-summary statement rate.
- Correction rate by field and source type.
- Low-confidence escalation rate.
- Duplicate-document detection accuracy.
- Language-specific transcription and translation accuracy.

### 18.4 Safety metrics

- Material misinformation rate.
- Missed and false safety-rule alerts.
- Incorrect patient/record association incidents.
- Unauthorized access attempts and confirmed access incidents.
- Time to identify and resolve a reported unsafe output.

### 18.5 Outcome-study metrics

- Time spent reconstructing history.
- Medication discrepancies identified and resolved.
- Previously requested investigations surfaced.
- Doctor-reported cognitive burden.
- Patient-reported repetition and clarity.

Metrics must not be interpreted as improved clinical outcomes without an appropriately designed study.

---

## 19. MVP scope and release plan

### Phase 0 — Discovery and safety definition

- Observe at least three different OPD settings.
- Interview doctors, nurses, receptionists, patients and caregivers.
- Map existing HMIS and paper workflows.
- Choose one pilot specialty and one facility.
- Establish clinical governance and incident processes.
- Define baseline metrics.
- Complete initial privacy and regulatory assessment.

### Phase 1 — Controlled standalone MVP

Included:

- Token-linked patient intake through web link or QR.
- English, Hindi and Hinglish text intake.
- Caregiver mode.
- Nurse entry for BP, pulse, temperature, SpO2, weight and glucose.
- Upload of PDFs and phone photographs.
- Extraction from selected printed laboratory reports and printed prescriptions.
- Source-linked evidence view.
- Basic medication reconciliation and unresolved-conflict view.
- HbA1c, glucose, BP and weight trends.
- Doctor confirmation and correction.
- PDF/structured encounter export.
- Consent, role controls and audit logs.

Excluded:

- Autonomous clinical recommendations.
- Raw diagnostic-image interpretation.
- Fully automated handwritten-prescription acceptance.
- Broad multi-specialty templates.
- Production ABDM exchange until sandbox and compliance work is completed.

### Phase 2 — Hospital integration and workflow hardening

- HMIS patient, encounter and note integration.
- Offline nurse workflow.
- WhatsApp delivery where contractually and legally appropriate.
- Additional laboratory formats.
- Voice intake after language validation.
- Follow-up instruction tracking.
- Expanded medication terminology and brand mapping.

### Phase 3 — ABDM integration

- Complete applicable sandbox milestones and security requirements.
- Patient-authorized record fetch.
- Import provenance and consent history.
- Structured export/linking of generated records where authorized.
- Production rollout only after formal approval.

### Phase 4 — Clinically validated expansion

- Additional specialties.
- Additional languages.
- More advanced reconciliation and clinical-decision-support functions only after regulatory classification, validation and governance approval.

---

## 20. Key edge cases

- Two patients share the same mobile number.
- A caregiver manages several family members.
- Patient name differs across ABHA, hospital record and report.
- A report belongs to another family member.
- The uploaded PDF is password protected.
- Pages are missing, duplicated or out of order.
- A lab uses a different unit or reference range.
- A patient denies taking a medicine shown in a recent prescription.
- A brand contains multiple active ingredients.
- Handwriting cannot be interpreted safely.
- The patient changes an answer after the doctor has opened the brief.
- Nurse records an implausible vital because of device or entry error.
- Connectivity fails after vitals entry but before synchronization.
- Consent is revoked during an active episode of care.
- ABDM or HMIS import returns duplicated or conflicting data.
- A document date is absent or detected incorrectly.
- A minor arrives without the expected guardian.
- The patient needs urgent treatment before intake is complete.

Each edge case must have an explicit product behavior, audit behavior and patient-safety response before production launch.

---

## 21. Risks and mitigations

| Risk | Consequence | Primary mitigation |
|---|---|---|
| Incorrect OCR or AI extraction | Wrong information appears in brief | Source highlighting, confidence thresholds and human confirmation |
| Automation bias | Doctor trusts a polished but incorrect summary | Separate fact/inference styling, source-first design and training |
| Duplicate patient identity | Records attached to wrong patient | Multi-factor identity matching and mismatch warnings |
| Staff workload increases | Low adoption | Measure task time, remove duplicate entry and integrate with HMIS |
| Patient cannot use digital intake | Exclusion or delay | Caregiver, kiosk and assisted flows; emergency bypass |
| Medication brand mapping error | False duplicate or allergy prompt | Versioned terminology, confidence threshold and evidence display |
| Data breach | Patient harm and legal exposure | Data minimization, encryption, role controls, audits and incident response |
| Product becomes another silo | Fragmented records | ABDM/HMIS integration and structured export strategy |
| Regulatory scope expands unexpectedly | Launch delay or non-compliance | Intended-use control and early specialist classification review |
| Alert fatigue | Important alert ignored | High-specificity governed rules and measured alert burden |

---

## 22. Pilot research plan

Before building the complete product, conduct field research with approximately:

- 8–12 doctors across general medicine and diabetes care.
- 8–12 nurses or clinical assistants.
- 4–6 reception/administrative staff.
- 25–40 patients, including older adults and people with low digital literacy.
- 8–12 caregivers.
- 2–3 HMIS/IT administrators.

Observe at least 50 real OPD journeys with appropriate permissions. Measure waiting time, consultation duration, repeated questions, document types, device/network conditions and where information is lost. Do not rely only on interview opinions; compare stated workflows with observed workflows.

Prototype testing should answer:

- Can a doctor understand the brief in 30 seconds?
- Does the source interaction increase trust or create extra work?
- Which medication discrepancies are genuinely useful?
- Can nurses enter vitals in under 90 seconds?
- Can patients complete intake without extensive staff help?
- Which questions are too sensitive, confusing or unnecessary?
- Which existing HMIS screen must the product complement or replace?

---

## 23. Launch gates

The product must not enter a live clinical pilot until all required gate owners approve:

1. Clinical workflow and escalation rules.
2. Privacy notice, consent and retention policy.
3. Role and access-control testing.
4. Patient identity and record-association safeguards.
5. Security assessment and incident-response readiness.
6. Extraction-quality evaluation on representative documents.
7. Doctor-facing unsupported-statement tests.
8. Backup, recovery and integration-failure behavior.
9. Staff training and emergency-bypass procedure.
10. Regulatory review of intended use and product claims.

---

## 24. Open product decisions

- Which facility and specialty will host the first pilot?
- Will the first version integrate with an existing token system or issue its own encounter token?
- Which HMIS must be supported first?
- Which medication terminology source can be licensed and maintained?
- Which laboratory formats cover the majority of pilot documents?
- Will voice recordings be deleted immediately after transcription or retained briefly for quality review with consent?
- What information must remain available after consent revocation for medical-record and legal obligations?
- Which organization will act in each applicable ABDM and data-protection role?
- Which features, if any, cross into regulated medical-device software based on their final intended use?
- What clinical team will own template and rule changes after launch?

---

## 25. Final product statement

This product should not be marketed as an AI doctor or as a generic medical-record locker. Its value is narrower and more defensible:

> A consent-driven clinical-context layer for Indian OPDs that combines patient intake, nurse measurements and historical records into a longitudinal, medication-reconciled and source-verifiable brief for doctor review.

The product earns trust not by producing the longest summary, but by making it effortless to distinguish what is known, what changed, where each claim came from and what still requires a clinician's judgment.

