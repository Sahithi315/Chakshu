import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = "C:/Users/Dell/Desktop/ELLL/Team_404-Vision/outputs/01a1827d-e830-7520-b21f-3ced29736d4a/symptom_dataset_calibration.xlsx";
await fs.mkdir(outputPath.slice(0, outputPath.lastIndexOf("/")), { recursive: true });

const wb = Workbook.create();
const guide = wb.worksheets.add("GUIDE");
const llm = wb.worksheets.add("TRAIN_LLM_01");
const template = wb.worksheets.add("TRAIN_TEMPLATE");
const truth = wb.worksheets.add("LAB_GROUND_TRUTH");

for (const sheet of [guide, llm, template, truth]) {
  sheet.showGridLines = false;
}

guide.getRange("A1:B1").values = [["Symptom dataset calibration", ""]];
guide.getRange("A3:B11").values = [
  ["Tag", "Rule"],
  ["{S}", "Affirmed symptom phrase. Include words needed to express the symptom, but not unrelated context."],
  ["{N}", "Denied symptom phrase only. Do not include no, not, denies, without, or similar negation words."],
  ["{D}", "Duration or onset-time value only. Do not include linking words such as since, for, or from. Examples: [3 days]{D}, since [yesterday]{D}, [this morning]{D}."],
  ["{V}", "Explicit severity phrase only. Examples: mild, severe, very bad, a lot."],
  ["Disease", "Do not tag diagnoses or diseases, such as diabetes, asthma, dengue, or migraine."],
  ["Medicine", "Do not tag medicine names or treatment names."],
  ["Body part", "Do not tag a body part alone. Tag the whole symptom expression when needed, such as chest hurts."],
  ["Source", "Use human for human-written TRAIN rows and llm for model-generated TRAIN rows. Never label LLM text as human."],
];
guide.getRange("A13:B20").values = [
  ["Workflow", "Required action"],
  ["1", "Each TRAIN writer creates exactly 5 calibration messages in a personal tab."],
  ["2", "Compare span boundaries, negation scope, duration, and severity tagging before expanding the dataset."],
  ["3", "Resolve disagreements and update this guide with the agreed rule."],
  ["4", "Only then expand each TRAIN tab to about 100 messages, including at least 35 messages with a {N} tag."],
  ["5", "Keep the 120-message human-only TEST set in a separate access-restricted sheet, not a tab in the shared TRAIN workbook."],
  ["6", "Freeze the model, tokenizer, normalization, and tag parser before the TEST owner releases evaluation data."],
  ["7", "Validate markup automatically before training: allowed tags, balanced brackets, unique IDs, and required source values."],
];
guide.getRange("A22:B25").values = [
  ["Important", "Reason"],
  ["No real patient text", "All messages and lab reports must be synthetic."],
  ["No TEST content in AI", "The held-out TEST set must remain human-written and unseen by any model or assistant."],
  ["No shared TEST tab", "Hidden tabs are not a security boundary for spreadsheet editors."],
];

const headers = [["id", "author", "text_marked", "source"]];
llm.getRange("A1:D1").values = headers;
llm.getRange("A2:D6").values = [
  ["train_llm_01_001", "LLM_01", "I've had [high]{V} [fever]{S} for [2 days]{D}, with [body ache]{S}, no [cough]{N}.", "llm"],
  ["train_llm_01_002", "LLM_01", "Since [last night]{D} my [chest pain]{S} is [mild]{V}, not having [breathlessness]{N}.", "llm"],
  ["train_llm_01_003", "LLM_01", "[stomch is hurting]{S} [a lot]{V} from [3 hrs]{D}, also [loose motions]{S} but no [blood in stool]{N}", "llm"],
  ["train_llm_01_004", "LLM_01", "I feel [dizzy]{S} whenever I stand, going on for [one week]{D}. No [fainting]{N} or [blurred vision]{N}.", "llm"],
  ["train_llm_01_005", "LLM_01", "My [sore throat]{S} started [4 days ago]{D}; it is [moderate]{V} and I have [difficulty swallowing]{S}, but no [runny nose]{N}.", "llm"],
];

template.getRange("A1:D1").values = headers;
template.getRange("A2:D6").values = [
  ["", "", "", ""], ["", "", "", ""], ["", "", "", ""], ["", "", "", ""], ["", "", "", ""],
];
template.getRange("F1:G5").values = [
  ["Use", "Duplicate this tab once per TRAIN writer and rename it with the writer ID."],
  ["Calibration", "Write only 5 rows before the team comparison."],
  ["TRAIN target", "About 100 messages per writer after calibration."],
  ["Denied target", "At least 35 rows per completed TRAIN tab must contain a {N} tag."],
  ["TEST", "Do not place held-out TEST messages in this workbook."],
];
template.getRange("D2:D105").dataValidation = { rule: { type: "list", values: ["human", "llm"] } };

truth.getRange("A1:H1").values = [["report_file", "report_id", "synthetic_patient", "test", "value", "unit", "reference_range", "layout"]];
truth.getRange("A2:H37").values = [
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "Haemoglobin", 10.8, "g/dL", "12.0-15.0", "Classic table"],
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "WBC count", 13200, "/uL", "4000-11000", "Classic table"],
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "Platelet count", 245000, "/uL", "150000-450000", "Classic table"],
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "RBC count", 3.9, "million/uL", "4.2-5.4", "Classic table"],
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "MCV", 78, "fL", "80-100", "Classic table"],
  ["synthetic_cbc_report.pdf", "SYN-CBC-001", "Kiran Vale", "Neutrophils", 78, "%", "40-75", "Classic table"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Fasting glucose", 146, "mg/dL", "70-99", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Creatinine", 1.3, "mg/dL", "0.6-1.2", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Urea", 42, "mg/dL", "15-40", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Sodium", 133, "mmol/L", "135-145", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Potassium", 4.7, "mmol/L", "3.5-5.1", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Calcium", 8.7, "mg/dL", "8.5-10.5", "Compact grid"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "HbA1c", 8.4, "%", "4.0-5.6", "Modern cards"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "Estimated average glucose", 194, "mg/dL", "68-114", "Modern cards"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "Total cholesterol", 228, "mg/dL", "<200", "Modern cards"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "LDL cholesterol", 146, "mg/dL", "<100", "Modern cards"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "HDL cholesterol", 38, "mg/dL", ">=40", "Modern cards"],
  ["synthetic_diabetes_lipid_report.pdf", "SYN-DIA-003", "Dev Arin", "Triglycerides", 220, "mg/dL", "<150", "Modern cards"],
  ["synthetic_thyroid_report.pdf", "SYN-THY-004", "Tara Nivan", "TSH", 7.8, "uIU/mL", "0.4-4.5", "Classic table"],
  ["synthetic_thyroid_report.pdf", "SYN-THY-004", "Tara Nivan", "Free T4", 0.7, "ng/dL", "0.8-1.8", "Classic table"],
  ["synthetic_thyroid_report.pdf", "SYN-THY-004", "Tara Nivan", "Free T3", 2.4, "pg/mL", "2.3-4.2", "Classic table"],
  ["synthetic_thyroid_report.pdf", "SYN-THY-004", "Tara Nivan", "Anti-TPO", 85, "IU/mL", "<35", "Classic table"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "Total bilirubin", 1.6, "mg/dL", "0.3-1.2", "Two-column"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "Direct bilirubin", 0.5, "mg/dL", "<0.3", "Two-column"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "AST", 58, "U/L", "10-40", "Two-column"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "ALT", 72, "U/L", "7-56", "Two-column"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "Alkaline phosphatase", 138, "U/L", "44-147", "Two-column"],
  ["synthetic_liver_report.pdf", "SYN-LFT-005", "Rhea Kaal", "Albumin", 3.4, "g/dL", "3.5-5.0", "Two-column"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Creatinine", 2.1, "mg/dL", "0.6-1.2", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "eGFR", 38, "mL/min/1.73m2", ">=60", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Urea", 64, "mg/dL", "15-40", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Sodium", 139, "mmol/L", "135-145", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Potassium", 5.4, "mmol/L", "3.5-5.1", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Urine albumin-creatinine ratio", 110, "mg/g", "<30", "Compact grid"],
  ["synthetic_renal_report.pdf", "SYN-REN-006", "Aman Vero", "Bicarbonate", 21, "mmol/L", "22-29", "Compact grid"],
  ["synthetic_metabolic_report.pdf", "SYN-MET-002", "Mira Solan", "Chloride", 101, "mmol/L", "98-107", "Compact grid"],
];

const titleFill = "#284B45";
const headerFill = "#557C73";
const lightFill = "#F7F1E6";
const warningFill = "#FFF2CC";
const font = "Arial";

guide.getRange("A1:B1").format = { fill: titleFill, font: { name: font, size: 15, bold: true, color: "#FFFFFF" }, rowHeight: 28 };
for (const range of [guide.getRange("A3:B3"), guide.getRange("A13:B13"), guide.getRange("A22:B22"), llm.getRange("A1:D1"), template.getRange("A1:D1"), truth.getRange("A1:H1")]) {
  range.format = { fill: headerFill, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
}
guide.getRange("A4:B11").format.fill = lightFill;
guide.getRange("A23:B25").format.fill = warningFill;
guide.getRange("A1:D25").format.font.name = font;
guide.getRange("A1:D25").format.font.size = 10;
guide.getRange("A3:B25").format.verticalAlignment = "top";
guide.getRange("A3:B25").format.wrapText = true;
guide.getRange("A:A").format.columnWidth = 18;
guide.getRange("B:B").format.columnWidth = 92;
guide.freezePanes.freezeRows(1);

for (const sheet of [llm, template]) {
  sheet.getRange("A1:D110").format.font = { name: font, size: 10 };
  sheet.getRange("A1:D110").format.verticalAlignment = "top";
  sheet.getRange("C2:C110").format.wrapText = true;
  sheet.getRange("A:A").format.columnWidth = 22;
  sheet.getRange("B:B").format.columnWidth = 18;
  sheet.getRange("C:C").format.columnWidth = 90;
  sheet.getRange("D:D").format.columnWidth = 14;
  sheet.freezePanes.freezeRows(1);
}
template.getRange("F1:G5").format = { fill: lightFill, font: { name: font, size: 10 }, wrapText: true, verticalAlignment: "top" };
template.getRange("F:F").format.columnWidth = 20;
template.getRange("G:G").format.columnWidth = 62;

truth.getRange("A1:H40").format.font = { name: font, size: 10 };
truth.getRange("A1:H40").format.verticalAlignment = "center";
truth.getRange("A1:H40").format.wrapText = true;
truth.getRange("A:A").format.columnWidth = 33;
truth.getRange("B:B").format.columnWidth = 16;
truth.getRange("C:C").format.columnWidth = 18;
truth.getRange("D:D").format.columnWidth = 30;
truth.getRange("E:E").format.columnWidth = 12;
truth.getRange("F:F").format.columnWidth = 18;
truth.getRange("G:G").format.columnWidth = 18;
truth.getRange("H:H").format.columnWidth = 16;
truth.freezePanes.freezeRows(1);

wb.recalculate();
const preview1 = await wb.render({ sheetName: "GUIDE", range: "A1:B25", scale: 1.2, format: "png" });
await fs.writeFile(outputPath.replace(".xlsx", "_guide_preview.png"), new Uint8Array(await preview1.arrayBuffer()));
const preview2 = await wb.render({ sheetName: "TRAIN_LLM_01", range: "A1:D6", scale: 1.2, format: "png" });
await fs.writeFile(outputPath.replace(".xlsx", "_train_preview.png"), new Uint8Array(await preview2.arrayBuffer()));

const inspect = await wb.inspect({ kind: "table", range: "TRAIN_LLM_01!A1:D6", include: "values,formulas", tableMaxRows: 10, tableMaxCols: 6 });
console.log(inspect.ndjson);
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);

const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(outputPath);
console.log(outputPath);

