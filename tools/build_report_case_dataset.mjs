import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/Dell/Desktop/ELLL/Team_404-Vision";
const truthPath = `${root}/tmp/report_case_dataset_truth.json`;
const outputPath = `${root}/outputs/01a1827d-e830-7520-b21f-3ced29736d4a/report_case_training_dataset.xlsx`;
await fs.mkdir(outputPath.slice(0, outputPath.lastIndexOf("/")), { recursive: true });
const truth = JSON.parse(await fs.readFile(truthPath, "utf8"));
const reports = truth.reports;

const wb = Workbook.create();
const summary = wb.worksheets.add("SUMMARY");
const policy = wb.worksheets.add("LABEL_POLICY");
const reportIndex = wb.worksheets.add("PDF_REPORT_INDEX");
const resultTruth = wb.worksheets.add("PDF_RESULT_TRUTH");
const caseInputs = wb.worksheets.add("CASE_INPUTS");
const findings = wb.worksheets.add("EXPECTED_FINDINGS");
const briefs = wb.worksheets.add("EXPECTED_BRIEFS");
const splits = wb.worksheets.add("SPLITS");

const reportRows = reports.map(r => [r.report_id, r.file, r.patient, r.patient_id, r.age, r.sex, r.collected, r.reported, r.facility, r.panel, r.layout, r.source, r.review_status]);
const resultRows = reports.flatMap(r => r.results.map(x => [r.report_id, x.test_id, x.test, x.value, x.unit, x.range_low, x.range_high, x.reference_range, x.flag, r.file, "llm", "synthetic_extraction_truth"]));

const symptoms = ["tiredness for 2 weeks", "headache since yesterday", "increased thirst for 1 month", "dizziness on standing for 3 days", "ankle swelling for 5 days", "reduced appetite for 1 week", "muscle cramps at night", "feeling cold and sluggish", "breathlessness while climbing stairs", "no current symptoms reported"];
const denied = ["no vomiting", "no chest pain", "no fainting", "no fever", "no blood in urine", "no wheezing", "no black stools", "no rash", "no palpitations", "no denied symptom stated"];
const meds = [
  ["metformin 500 mg twice daily", "patient says stopped metformin last week"],
  ["amlodipine 5 mg once daily", "patient says taking amlodipine regularly"],
  ["levothyroxine 50 mcg every morning", "patient is unsure of current thyroid tablet dose"],
  ["atorvastatin 20 mg at night", "patient says ran out of atorvastatin 4 days ago"],
  ["ferrous ascorbate 100 mg once daily", "patient says taking iron on alternate days"],
  ["no active medicine listed", "patient cannot remember medicine names"],
];
const allergies = ["penicillin caused itchy rash", "no known medicine allergy reported", "ibuprofen caused facial swelling", "allergy status not provided"];

function numeric(v) { return Number(v); }
function trendLabel(previous, current) {
  const a = numeric(previous), b = numeric(current);
  const tolerance = Math.max(Math.abs(a) * 0.02, 0.01);
  if (Math.abs(b - a) <= tolerance) return "stable";
  return b > a ? "increased" : "decreased";
}
function evidence(reportId, testId) { return `${reportId}:${testId}`; }

const caseRows = [];
const findingRows = [];
const briefRows = [];
const splitRows = [];
for (let i = 0; i < 500; i++) {
  const currentIndex = 8 + (i % 16);
  const current = reports[currentIndex];
  const prior = reports[currentIndex - 8];
  const currentResult = current.results[i % current.results.length];
  const priorMatch = prior.results.find(x => x.test === currentResult.test);
  const comparable = priorMatch || prior.results[(i + 2) % prior.results.length];
  const hasTrueTrend = Boolean(priorMatch) && current.patient_id === prior.patient_id;
  const med = meds[i % meds.length];
  const allergy = allergies[i % allergies.length];
  const patientText = `Main concern: ${symptoms[i % symptoms.length]}; ${denied[i % denied.length]}. Current medicine list says ${med[0]}; ${med[1]}. Allergy: ${allergy}.`;
  const caseId = `CASE-${String(i + 1).padStart(4, "0")}`;
  const split = i < 400 ? "TRAIN" : "DEV";
  const review = "clinician_review_required";
  const abnormal = currentResult.flag !== "IN_RANGE";
  const medConflict = /stopped|ran out|unsure|cannot remember|alternate days/.test(med[1]);
  const missing = /not provided|cannot remember|unsure/.test(`${allergy} ${med[1]}`);
  caseRows.push([caseId, split, current.report_id, hasTrueTrend ? prior.report_id : "", patientText, med[0], med[1], allergy, "Create an evidence-linked clinical brief; do not diagnose or recommend treatment.", "llm", review]);
  let seq = 1;
  findingRows.push([caseId, seq++, "reported_symptom", symptoms[i % symptoms.length], "patient_text", "Patient reported", "", "Do not infer a diagnosis", "llm", review]);
  findingRows.push([caseId, seq++, "denied_symptom", denied[i % denied.length], "patient_text", "Patient reported", "", "Negation must be preserved", "llm", review]);
  findingRows.push([caseId, seq++, "laboratory_result", `${currentResult.test}: ${currentResult.value} ${currentResult.unit} (${currentResult.flag}; supplied range ${currentResult.reference_range})`, evidence(current.report_id, currentResult.test_id), `Extracted from ${current.file}`, currentResult.flag, "Compare only with the range printed in the synthetic report", "llm", review]);
  if (hasTrueTrend) {
    findingRows.push([caseId, seq++, "trend", `${currentResult.test} ${trendLabel(comparable.value, currentResult.value)} from ${comparable.value} to ${currentResult.value} ${currentResult.unit}`, `${evidence(prior.report_id, comparable.test_id)} + ${evidence(current.report_id, currentResult.test_id)}`, "Calculated from two synthetic reports", trendLabel(comparable.value, currentResult.value), "No clinical cause inferred", "llm", review]);
  } else {
    findingRows.push([caseId, seq++, "trend_unavailable", `No prior ${currentResult.test} value is available for comparison`, current.report_id, "Dataset comparison rule", "not_comparable", "Do not compare different tests", "llm", review]);
  }
  if (medConflict) findingRows.push([caseId, seq++, "medication_reconciliation", `Medication list and patient statement need reconciliation: ${med[0]}; ${med[1]}`, "patient_text", "Patient reported and active-list comparison", "possible_conflict", "Evidence only; do not change treatment", "llm", review]);
  if (missing) findingRows.push([caseId, seq++, "missing_information", "Medication or allergy information is incomplete and should be confirmed", "patient_text", "Patient reported", "missing", "Ask/confirm; do not fill from inference", "llm", review]);
  const pieces = [
    `Patient reports ${symptoms[i % symptoms.length]} and ${denied[i % denied.length]}.`,
    `${currentResult.test} is ${currentResult.value} ${currentResult.unit}, marked ${currentResult.flag} against the report's supplied range ${currentResult.reference_range} [${evidence(current.report_id, currentResult.test_id)}].`,
    hasTrueTrend ? `Compared with ${comparable.value} ${comparable.unit}, this value ${trendLabel(comparable.value, currentResult.value)} [${evidence(prior.report_id, comparable.test_id)}].` : `A same-test prior value is unavailable, so no trend is stated.`,
    medConflict ? `Medication reconciliation is required because ${med[1]}.` : `No medication-list contradiction is present in the supplied text.`,
    missing ? `Incomplete medication/allergy information should be confirmed.` : "",
    "This is an evidence-linked draft, not a diagnosis or treatment recommendation; clinician confirmation is required."
  ].filter(Boolean);
  briefRows.push([caseId, pieces.join(" "), abnormal ? "contains_report_flag" : "no_report_flag", medConflict ? "yes" : "no", missing ? "yes" : "no", "No diagnosis generated", "No treatment generated", "llm", review]);
  splitRows.push([caseId, split, current.report_id, hasTrueTrend ? prior.report_id : "", i < 400 ? "Model development" : "Development validation only; not final held-out TEST", "llm"]);
}

summary.getRange("A1:E1").values = [["Synthetic report extraction and grounded case-synthesis dataset", "", "", "", ""]];
summary.mergeCells("A1:E1");
summary.getRange("A3:E11").values = [
  ["Component", "Rows/files", "What it tests", "Ground truth status", "Important limit"],
  ["Synthetic PDF reports", reports.length, "Reading digitally generated lab reports in four layouts", "Exact generator truth", "Does not test handwriting or camera images"],
  ["PDF result truth", resultRows.length, "Test, value, unit, supplied range and printed flag", "Exact generator truth", "Range is report-specific; no disease inference"],
  ["Case inputs", caseRows.length, "Patient text + current/prior reports + medication/allergy context", "Synthetic", "Not real patient data"],
  ["Expected findings", findingRows.length, "Evidence-linked facts, trends, conflicts and missing information", "LLM-generated; clinician review required", "Not diagnostic ground truth"],
  ["Expected briefs", briefRows.length, "Concise draft for a doctor with evidence IDs", "LLM-generated; clinician review required", "No autonomous diagnosis or treatment"],
  ["TRAIN", 400, "Model development", "Synthetic", "Patient/report groups may repeat within TRAIN"],
  ["DEV", 100, "Development validation", "Synthetic", "Not the human-only held-out TEST set"],
  ["Deployment rule", "—", "Every interpretation remains reviewable and source-linked", "Mandatory", "Qualified clinicians must validate before clinical use"],
];

policy.getRange("A1:D1").values = [["Rule", "Allowed output", "Forbidden output", "Review requirement"]];
policy.getRange("A2:D11").values = [
  ["Report extraction", "Copy test name, value, unit, supplied range, date and source", "Inventing missing values", "Verify against original line/image"],
  ["Abnormality", "State HIGH/LOW/IN_RANGE only from the supplied report range", "Calling a disease from one value", "Clinician confirmation"],
  ["Trend", "Compare the same test and compatible units across dates", "Comparing different tests or silently converting uncertain units", "Clinician confirmation"],
  ["Medication reconciliation", "Show conflicting list/patient statements and provenance", "Stopping, starting or changing treatment", "Doctor decision required"],
  ["Symptoms", "Preserve patient wording and explicit denials", "Turning symptoms into a diagnosis", "Clinician confirmation"],
  ["Missing data", "State what is missing or uncertain", "Guessing from context", "Ask patient/review document"],
  ["Doctor brief", "Evidence-linked draft using supplied facts", "Unsupported clinical conclusion", "Must be editable and confirmed"],
  ["Urgency", "Only surface an institution-approved deterministic rule if separately supplied", "LLM-only emergency classification", "Clinical governance required"],
  ["Dataset use", "Bootstrap OCR/extraction and grounded summarisation", "Claiming clinical safety from synthetic data", "Prospective clinician-led evaluation"],
  ["TEST set", "Keep clinician-authored held-out cases separate", "Training on the final TEST set", "Access-restricted adjudication"],
];

function write(sheet, headers, rows) {
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  sheet.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;
}
write(reportIndex, ["report_id", "pdf_file", "synthetic_patient", "patient_id", "age", "sex", "collected_at", "reported_at", "facility", "panel", "layout", "source", "review_status"], reportRows);
write(resultTruth, ["report_id", "test_id", "test", "value", "unit", "range_low", "range_high", "reference_range", "expected_flag", "pdf_file", "source", "review_status"], resultRows);
write(caseInputs, ["case_id", "split", "current_report_id", "prior_report_id", "patient_text", "active_medication_list", "patient_medication_statement", "allergy_statement", "task", "source", "review_status"], caseRows);
write(findings, ["case_id", "finding_order", "finding_type", "expected_finding", "evidence_id", "provenance_label", "expected_status", "safety_note", "source", "review_status"], findingRows);
write(briefs, ["case_id", "expected_doctor_brief", "report_flag_present", "medication_conflict", "missing_information", "diagnosis_output", "treatment_output", "source", "review_status"], briefRows);
write(splits, ["case_id", "split", "current_report_id", "prior_report_id", "purpose", "source"], splitRows);

const navy = "#284B45", green = "#557C73", cream = "#F7F1E6", white = "#FFFFFF", font = "Arial";
for (const sheet of [summary, policy, reportIndex, resultTruth, caseInputs, findings, briefs, splits]) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getUsedRange();
  used.format = { font: { name: font, size: 9 }, verticalAlignment: "top" };
  sheet.getRangeByIndexes(0, 0, 1, used.columnCount).format = { fill: green, font: { name: font, size: 9, bold: true, color: white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, rowHeight: 28 };
}
summary.getRange("A1:E1").format = { fill: navy, font: { name: font, size: 15, bold: true, color: white }, rowHeight: 30 };
summary.getRange("A3:E3").format = { fill: green, font: { name: font, size: 9, bold: true, color: white }, wrapText: true };
summary.getRange("A4:E11").format.wrapText = true;
summary.getRange("A:A").format.columnWidth = 28; summary.getRange("B:B").format.columnWidth = 14; summary.getRange("C:E").format.columnWidth = 42;
policy.getRange("A:A").format.columnWidth = 24; policy.getRange("B:D").format.columnWidth = 50; policy.getRange("A2:D11").format.wrapText = true;
reportIndex.getRange("A:M").format.columnWidth = 18; reportIndex.getRange("C:C").format.columnWidth = 24; reportIndex.getRange("G:J").format.columnWidth = 27;
resultTruth.getRange("A:L").format.columnWidth = 17; resultTruth.getRange("C:C").format.columnWidth = 27;
caseInputs.getRange("A:K").format.columnWidth = 18; caseInputs.getRange("E:E").format.columnWidth = 75; caseInputs.getRange("F:I").format.columnWidth = 36; caseInputs.getRange("E:K").format.wrapText = true;
findings.getRange("A:J").format.columnWidth = 18; findings.getRange("D:D").format.columnWidth = 70; findings.getRange("E:F").format.columnWidth = 35; findings.getRange("H:H").format.columnWidth = 45; findings.getRange("D:J").format.wrapText = true;
briefs.getRange("A:I").format.columnWidth = 20; briefs.getRange("B:B").format.columnWidth = 110; briefs.getRange("B:I").format.wrapText = true;
splits.getRange("A:F").format.columnWidth = 24; splits.getRange("E:E").format.columnWidth = 55;

for (const sheet of [reportIndex, resultTruth, caseInputs, findings, briefs, splits]) {
  const used = sheet.getUsedRange();
  used.format.autofitRows();
}
wb.recalculate();
for (const [sheet, range] of [[summary,"A1:E11"],[policy,"A1:D11"],[reportIndex,"A1:M10"],[resultTruth,"A1:L12"],[caseInputs,"A1:K8"],[findings,"A1:J12"],[briefs,"A1:I7"],[splits,"A1:F10"]]) {
  const png = await wb.render({ sheetName: sheet.name, range, scale: 1, format: "png" });
  await fs.writeFile(outputPath.replace(".xlsx", `_${sheet.name.toLowerCase()}_preview.png`), new Uint8Array(await png.arrayBuffer()));
}
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
console.log(errors.ndjson);
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(outputPath);
console.log(JSON.stringify({ outputPath, reports: reports.length, resultRows: resultRows.length, cases: caseRows.length, findings: findingRows.length, briefs: briefRows.length, train: 400, dev: 100 }, null, 2));
