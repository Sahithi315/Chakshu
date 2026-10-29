import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = "C:/Users/Dell/Desktop/ELLL/Team_404-Vision/outputs/01a1827d-e830-7520-b21f-3ced29736d4a/opd_intake_entity_train_2000.xlsx";
await fs.mkdir(outputPath.slice(0, outputPath.lastIndexOf("/")), { recursive: true });

const wb = Workbook.create();
const summary = wb.worksheets.add("SUMMARY");
const codebook = wb.worksheets.add("CODEBOOK");
const symptomSheet = wb.worksheets.add("TRAIN_SYMPTOMS");
const medicationSheet = wb.worksheets.add("TRAIN_MEDICATIONS");
const historySheet = wb.worksheets.add("TRAIN_HISTORY");
const labSheet = wb.worksheets.add("TRAIN_LABS");
const combinedSheet = wb.worksheets.add("TRAIN_COMBINED");

const headers = ["id", "author", "text_marked", "source"];
const allowedTags = new Set(["S", "N", "D", "V", "B", "F", "M", "Q", "U", "C", "A", "E", "P", "H", "T", "L"]);

const symptoms = ["fever", "cough", "headache", "dizziness", "nausea", "vomiting", "loose motions", "constipation", "breathlessness", "wheezing", "sore throat", "runny nose", "body ache", "weakness", "tiredness", "burning while passing urine", "frequent urination", "loss of appetite", "blurred vision", "palpitations", "swelling", "itching", "rash", "chills", "night sweats", "dry mouth", "fainting", "stomach cramps", "acidity", "joint stiffness"];
const typoSymptoms = ["hedache", "dizzines", "fevr", "vommiting", "brethlessness", "stomak cramps", "wekness", "runy nose"];
const deniedSymptoms = ["vomiting", "fainting", "chest pain", "breathlessness", "blood in stool", "blood in urine", "fever", "cough", "blurred vision", "seizures", "wheezing", "rash"];
const bodies = ["chest", "lower back", "upper abdomen", "lower abdomen", "right knee", "left shoulder", "neck", "right ear", "left ankle", "both legs", "right side of my head", "middle of my back"];
const durations = ["2 hours", "this morning", "3 days", "one week", "about 10 days", "two months", "last night", "half an hour", "4 weeks", "yesterday evening", "many months", "Monday"];
const severities = ["mild", "moderate", "severe", "very bad", "unbearable", "slight"];
const frequencies = ["on and off", "all the time", "mostly at night", "twice a day", "every morning", "once every few days"];
const medProfiles = [
  { name: "metformin", dose: "500 mg twice daily", condition: "type 2 diabetes" },
  { name: "amlodipine", dose: "5 mg once daily", condition: "high blood pressure" },
  { name: "telmisartan", dose: "40 mg once daily", condition: "high blood pressure" },
  { name: "atorvastatin", dose: "20 mg at night", condition: "high cholesterol" },
  { name: "levothyroxine", dose: "50 mcg every morning before food", condition: "hypothyroidism" },
  { name: "pantoprazole", dose: "40 mg before breakfast", condition: "acid reflux" },
  { name: "paracetamol", dose: "500 mg when needed", condition: "arthritis" },
  { name: "cetirizine", dose: "10 mg at night", condition: "seasonal allergies" },
  { name: "montelukast", dose: "10 mg at night", condition: "asthma" },
  { name: "glimepiride", dose: "1 mg before breakfast", condition: "type 2 diabetes" },
  { name: "insulin glargine", dose: "10 units at bedtime", condition: "type 2 diabetes" },
  { name: "aspirin", dose: "75 mg once daily", condition: "coronary artery disease" },
  { name: "clopidogrel", dose: "75 mg once daily", condition: "coronary artery disease" },
  { name: "losartan", dose: "50 mg once daily", condition: "high blood pressure" },
  { name: "bisoprolol", dose: "2.5 mg once daily", condition: "high blood pressure" },
  { name: "azithromycin", dose: "500 mg once daily for 3 days", condition: "bacterial infection" },
  { name: "amoxicillin", dose: "500 mg three times daily for 5 days", condition: "bacterial infection" },
  { name: "calcium carbonate", dose: "500 mg once daily", condition: "osteoporosis" },
  { name: "vitamin D3", dose: "60000 IU once weekly", condition: "vitamin D deficiency" },
  { name: "ferrous ascorbate", dose: "100 mg once daily", condition: "anaemia" },
  { name: "salbutamol inhaler", dose: "two puffs when needed", condition: "asthma" },
  { name: "budesonide inhaler", dose: "one puff twice daily", condition: "asthma" },
  { name: "gabapentin", dose: "300 mg at night", condition: "neuropathic pain" },
  { name: "pregabalin", dose: "75 mg at night", condition: "neuropathic pain" },
  { name: "furosemide", dose: "40 mg every morning", condition: "heart failure" },
  { name: "metoprolol", dose: "25 mg twice daily", condition: "high blood pressure" },
];
const useStates = ["taking regularly", "miss doses sometimes", "stopped last week", "started yesterday", "take only when needed", "not sure if I should continue", "ran out three days ago", "taking a different dose"];
const conditions = ["type 2 diabetes", "high blood pressure", "hypothyroidism", "asthma", "high cholesterol", "arthritis", "migraine", "fatty liver", "chronic kidney disease", "anaemia", "acid reflux", "polycystic ovary syndrome", "epilepsy", "coronary artery disease", "seasonal allergies"];
const allergens = ["penicillin", "sulfa medicines", "ibuprofen", "aspirin", "prawns", "peanuts", "latex", "iodine contrast", "dust", "eggs", "milk", "diclofenac"];
const reactions = ["itchy rash", "swelling of lips", "breathing difficulty", "hives", "stomach upset", "face swelling", "severe itching", "dizziness"];
const pregnancyStates = ["8 weeks pregnant", "16 weeks pregnant", "28 weeks pregnant", "not pregnant", "pregnancy status unknown", "trying to conceive", "breastfeeding a 4 month old baby"];
const historyEvents = ["appendix surgery in 2018", "hospital admission for pneumonia last year", "gallbladder removal in 2022", "caesarean delivery three years ago", "angioplasty in 2020", "admission for dengue two years ago", "knee replacement surgery", "kidney stone procedure last month", "blood transfusion in childhood", "fracture surgery in 2019", "hospital stay for asthma in June", "thyroid surgery five years ago"];
const tests = ["HbA1c", "fasting glucose", "haemoglobin", "TSH", "creatinine", "vitamin D", "LDL cholesterol", "platelet count", "serum potassium", "ALT", "total bilirubin", "urine protein", "eGFR", "ferritin", "CRP"];
const results = ["8.2%", "146 mg/dL", "10.4 g/dL", "7.6 uIU/mL", "1.8 mg/dL", "14 ng/mL", "162 mg/dL", "98000 per uL", "5.4 mmol/L", "72 U/L", "1.6 mg/dL", "2+", "42 mL/min/1.73m2", "18 ng/mL", "22 mg/L"];

function mark(value, tag) { return `[${value}]{${tag}}`; }
function pick(arr, n, step = 1) { return arr[(n * step) % arr.length]; }
function stylePrefix(n) {
  const variants = ["", "hi, ", "pls help, ", "at kiosk: ", "doctor ji ", "since today ", "quick note - ", "I wanted to say "];
  return pick(variants, n, 5);
}
function neutralTail(n, templateCount) {
  const tails = [
    "", " please check this.", " this is what I remember.", " family helped me type this.",
    " I may have typed spelling wrong.", " sharing this for the doctor.", " these are my current details.",
    " adding this before consultation.", " this is the main issue.", " entered using the kiosk.",
    " I can explain more inside.", " please confirm with me."
  ];
  return tails[Math.floor(n / templateCount) % tails.length];
}
function uniqueGenerate(count, generator) {
  const rows = [];
  const seen = new Set();
  let attempt = 0;
  while (rows.length < count && attempt < count * 50) {
    const text = generator(attempt, rows.length);
    if (!seen.has(text)) { seen.add(text); rows.push(text); }
    attempt++;
  }
  if (rows.length !== count) throw new Error(`Could only create ${rows.length} unique rows out of ${count}`);
  return rows;
}

function symptomText(n) {
  const symptom = pick(n % 7 === 0 ? typoSymptoms : symptoms, n, 7);
  const symptom2 = pick(symptoms, n + 9, 11);
  const denied = pick(deniedSymptoms, n + 3, 5);
  const body = pick(bodies, n, 7);
  const duration = pick(durations, n, 5);
  const severity = pick(severities, n, 5);
  const frequency = pick(frequencies, n, 7);
  const negative = n % 2 === 0 ? `, but no ${mark(denied, "N")}` : "";
  const templates = [
    `${stylePrefix(n)}I have ${mark(severity, "V")} ${mark(symptom, "S")} for ${mark(duration, "D")}${negative}.`,
    `${mark(symptom, "S")} ${mark(frequency, "F")} from ${mark(duration, "D")}${negative}`,
    `feeling ${mark(symptom, "S")} and ${mark(symptom2, "S")} for ${mark(duration, "D")}, ${mark(severity, "V")}${negative}`,
    `${stylePrefix(n)}${mark("pain", "S")} in ${mark(body, "B")} is ${mark(severity, "V")}, going on ${mark(duration, "D")}${negative}`,
    `mujhe ${mark(symptom, "S")} ho raha hai ${mark(duration, "D")} se, ${mark(frequency, "F")}${negative}`,
    `since ${mark(duration, "D")} ${mark(symptom, "S")}. feels ${mark(severity, "V")}${negative}`,
    `${mark(body, "B")} me ${mark("pain", "S")} ${mark(frequency, "F")}, ${mark(duration, "D")} se${negative}`,
    `I get ${mark(symptom, "S")} ${mark(frequency, "F")}; started ${mark(duration, "D")}${negative}`,
  ];
  return templates[n % templates.length] + neutralTail(n, templates.length);
}

function medicationText(n) {
  const profile = pick(medProfiles, n, 7);
  const profile2 = pick(medProfiles, n + 5, 11);
  const med = profile.name;
  const med2 = profile2.name;
  const dose = profile.dose;
  const dose2 = profile2.dose;
  const state = pick(useStates, n, 5);
  const condition = profile.condition;
  const duration = pick(durations, n, 11);
  const templates = [
    `I take ${mark(med, "M")} ${mark(dose, "Q")} and I am ${mark(state, "U")}.`,
    `${mark(med, "M")} - ${mark(dose, "Q")}, ${mark(state, "U")}`,
    `for ${mark(condition, "C")} I use ${mark(med, "M")} ${mark(dose, "Q")}.`,
    `${mark(med, "M")}: ${mark(state, "U")}.`,
    `my medicines are ${mark(med, "M")} ${mark(dose, "Q")} and ${mark(med2, "M")} ${mark(dose2, "Q")}`,
    `tablet name maybe ${mark(med, "M")}, dose is ${mark(dose, "Q")}; ${mark(state, "U")}`,
    `doctor gave ${mark(med, "M")} for ${mark(condition, "C")}, I am ${mark(state, "U")}`,
  ];
  return templates[n % templates.length] + neutralTail(n, templates.length);
}

function historyText(n) {
  const condition = pick(conditions, n, 7);
  const condition2 = pick(conditions, n + 4, 11);
  const allergen = pick(allergens, n, 5);
  const reaction = pick(reactions, n, 7);
  const pregnancy = pick(pregnancyStates, n, 5);
  const history = pick(historyEvents, n, 7);
  const templates = [
    `I have ${mark(condition, "C")} and ${mark(condition2, "C")}.`,
    `allergic to ${mark(allergen, "A")}; it caused ${mark(reaction, "E")}.`,
    `past history: ${mark(history, "H")}.`,
    `I am ${mark(pregnancy, "P")}.`,
    `${mark(condition, "C")} since years, also had ${mark(history, "H")}`,
    `please note ${mark(allergen, "A")} allergy - ${mark(reaction, "E")}`,
    `currently ${mark(pregnancy, "P")} and known ${mark(condition, "C")}`,
    `old operation was ${mark(history, "H")}; I also have ${mark(condition, "C")}`,
  ];
  return templates[n % templates.length] + neutralTail(n, templates.length);
}

function labText(n) {
  const idx = (n * 7) % tests.length;
  const idx2 = (n * 11 + 3) % tests.length;
  const test = tests[idx];
  const result = results[idx];
  const test2 = tests[idx2];
  const result2 = results[idx2];
  const duration = pick(["today", "yesterday", "last week", "two months ago", "in my latest report", "this morning", "on Monday"], n, 5);
  const templates = [
    `my ${mark(test, "T")} is ${mark(result, "L")} from ${mark(duration, "D")}`,
    `report says ${mark(test, "T")}: ${mark(result, "L")}`,
    `${mark(duration, "D")} ${mark(test, "T")} came ${mark(result, "L")}`,
    `lab values ${mark(test, "T")} ${mark(result, "L")}, ${mark(test2, "T")} ${mark(result2, "L")}`,
    `I checked ${mark(test, "T")} and result was ${mark(result, "L")} ${mark(duration, "D")}`,
    `latest blood report - ${mark(test, "T")} = ${mark(result, "L")}`,
  ];
  return templates[n % templates.length] + neutralTail(n, templates.length);
}

function combinedText(n) {
  const symptom = pick(symptoms, n, 7);
  const symptom2 = pick(symptoms, n + 8, 11);
  const denied = pick(deniedSymptoms, n + 4, 5);
  const duration = pick(durations, n, 5);
  const severity = pick(severities, n, 5);
  const body = pick(bodies, n, 7);
  const frequency = pick(frequencies, n, 7);
  const profile = pick(medProfiles, n, 11);
  const med = profile.name;
  const dose = profile.dose;
  const state = pick(useStates, n, 7);
  const condition = profile.condition;
  const allergen = pick(allergens, n, 5);
  const reaction = pick(reactions, n, 7);
  const history = pick(historyEvents, n, 11);
  const pregnancy = pick(pregnancyStates, n, 5);
  const tIdx = (n * 7) % tests.length;
  const negative = n % 2 === 0 ? ` No ${mark(denied, "N")}.` : "";
  const templates = [
    `I have ${mark(severity, "V")} ${mark(symptom, "S")} for ${mark(duration, "D")}.${negative} I take ${mark(med, "M")} ${mark(dose, "Q")} and have ${mark(condition, "C")}.`,
    `${mark("pain", "S")} in ${mark(body, "B")} ${mark(frequency, "F")} since ${mark(duration, "D")}.${negative} ${mark(med, "M")} - ${mark(state, "U")}.`,
    `known ${mark(condition, "C")}, on ${mark(med, "M")} ${mark(dose, "Q")}. now ${mark(symptom, "S")} and ${mark(symptom2, "S")} for ${mark(duration, "D")}.${negative}`,
    `allergic to ${mark(allergen, "A")} - got ${mark(reaction, "E")}. Today ${mark(symptom, "S")} is ${mark(severity, "V")}.${negative}`,
    `history of ${mark(history, "H")}. ${mark(symptom, "S")} ${mark(frequency, "F")} for ${mark(duration, "D")}.${negative}`,
    `my ${mark(tests[tIdx], "T")} was ${mark(results[tIdx], "L")} ${mark("last week", "D")}. I have ${mark(condition, "C")} and take ${mark(med, "M")}.`,
    `I am ${mark(pregnancy, "P")}; having ${mark(symptom, "S")} for ${mark(duration, "D")}, ${mark(severity, "V")}.${negative}`,
    `pls note ${mark(condition, "C")}, ${mark(allergen, "A")} allergy causing ${mark(reaction, "E")}; ${mark(symptom, "S")} from ${mark(duration, "D")}.${negative}`,
    `medicine ${mark(med, "M")} ${mark(dose, "Q")}, ${mark(state, "U")}. complaint is ${mark(symptom, "S")} ${mark(frequency, "F")}.${negative}`,
    `I had ${mark(history, "H")}. Now ${mark("pain", "S")} at ${mark(body, "B")} for ${mark(duration, "D")}, ${mark(severity, "V")}.${negative}`,
  ];
  return templates[n % templates.length] + neutralTail(n, templates.length);
}

const datasets = [
  { sheet: symptomSheet, key: "sym", author: "LLM_SYMPTOM_01", count: 500, rows: uniqueGenerate(500, symptomText) },
  { sheet: medicationSheet, key: "med", author: "LLM_MEDICATION_01", count: 300, rows: uniqueGenerate(300, medicationText) },
  { sheet: historySheet, key: "hist", author: "LLM_HISTORY_01", count: 300, rows: uniqueGenerate(300, historyText) },
  { sheet: labSheet, key: "lab", author: "LLM_LAB_01", count: 300, rows: uniqueGenerate(300, labText) },
  { sheet: combinedSheet, key: "mix", author: "LLM_COMBINED_01", count: 600, rows: uniqueGenerate(600, combinedText) },
];

const tagDefinitions = [
  ["{S}", "Affirmed current symptom", "[headache]{S}"],
  ["{N}", "Denied symptom only; keep no/not/denies outside", "no [vomiting]{N}"],
  ["{D}", "Duration or onset-time value; keep since/for/from outside", "for [3 days]{D}"],
  ["{V}", "Explicit severity", "[severe]{V}"],
  ["{B}", "Body location when expressed separately", "[chest]{B} [pain]{S}"],
  ["{F}", "Frequency or temporal pattern", "[on and off]{F}"],
  ["{M}", "Medicine name", "[metformin]{M}"],
  ["{Q}", "Dose, route, frequency, or medicine instruction", "[500 mg twice daily]{Q}"],
  ["{U}", "Medication-use status", "[stopped last week]{U}"],
  ["{C}", "Known condition or prior diagnosis", "[type 2 diabetes]{C}"],
  ["{A}", "Allergen or substance linked to an allergy", "[penicillin]{A}"],
  ["{E}", "Allergic or adverse reaction", "[itchy rash]{E}"],
  ["{P}", "Pregnancy or breastfeeding status phrase", "[16 weeks pregnant]{P}"],
  ["{H}", "Prior procedure or hospitalization event", "[appendix surgery in 2018]{H}"],
  ["{T}", "Test or measurement name", "[HbA1c]{T}"],
  ["{L}", "Reported test value including unit when present", "[8.2%]{L}"],
];

function countTags(rows) {
  const counts = Object.fromEntries([...allowedTags].map(t => [t, 0]));
  for (const text of rows) for (const match of text.matchAll(/\]\{([A-Z])\}/g)) counts[match[1]]++;
  return counts;
}

function validateAll() {
  const ids = new Set();
  let total = 0;
  for (const ds of datasets) {
    const texts = new Set();
    for (let i = 0; i < ds.rows.length; i++) {
      const id = `train_${ds.key}_${String(i + 1).padStart(4, "0")}`;
      if (ids.has(id)) throw new Error(`Duplicate ID ${id}`);
      ids.add(id);
      const text = ds.rows[i];
      if (texts.has(text)) throw new Error(`Duplicate text in ${ds.sheet.name}`);
      texts.add(text);
      const stripped = text.replace(/\[[^\[\]{}]+\]\{[A-Z]\}/g, "");
      if (/[\[\]{}]/.test(stripped)) throw new Error(`Malformed markup: ${text}`);
      for (const m of text.matchAll(/\]\{([A-Z])\}/g)) if (!allowedTags.has(m[1])) throw new Error(`Unknown tag ${m[1]}`);
      for (const m of text.matchAll(/\[([^\]]+)\]\{N\}/g)) if (/^(no|not|denies|without)\b/i.test(m[1].trim())) throw new Error(`Negation included in N span: ${text}`);
      total++;
    }
    if ((ds.key === "sym" || ds.key === "mix") && ds.rows.filter(x => x.includes("{N}")).length / ds.rows.length < 0.35) throw new Error(`${ds.key} denied-symptom coverage below 35%`);
  }
  if (total !== 2000) throw new Error(`Expected 2000 rows, found ${total}`);
  return total;
}
const total = validateAll();

summary.getRange("A1:D1").values = [["OPD intake entity dataset", "", "", ""]];
summary.getRange("A3:D9").values = [
  ["Dataset tab", "Rows", "Rows with {N}", "Purpose"],
  ...datasets.map(ds => [ds.sheet.name, ds.count, ds.rows.filter(x => x.includes("{N}")).length, ds.key === "sym" ? "Symptoms, denial, duration, severity, body location, pattern" : ds.key === "med" ? "Medicines, instructions, usage, conditions" : ds.key === "hist" ? "Conditions, allergy, pregnancy, procedures and admissions" : ds.key === "lab" ? "Test names and reported values" : "Multi-entity patient-style messages"]),
  ["TOTAL", total, datasets.reduce((a, ds) => a + ds.rows.filter(x => x.includes("{N}")).length, 0), "TRAIN-only synthetic messages"],
];
summary.getRange("A11:D16").values = [
  ["Rule", "", "", "Requirement"],
  ["Patient experience", "", "", "Patients type or speak normal sentences. Inline tags are training annotations and never appear in the patient interface."],
  ["Source", "", "", "Every generated row is labelled llm. Do not relabel these rows as human."],
  ["TEST isolation", "", "", "No TEST messages are included. Keep the human-only TEST set in a separate restricted file."],
  ["Human review", "", "", "Review span boundaries and medical wording before model training. Generated quantity does not replace annotation quality."],
  ["Schema separation", "", "", "Do not mix this expanded body-location schema with the earlier symptom-only workbook without reannotation."],
];

codebook.getRange("A1:C1").values = [["Tag", "Meaning", "Example"]];
codebook.getRange(`A2:C${tagDefinitions.length + 1}`).values = tagDefinitions;
codebook.getRange("E1:F9").values = [
  ["Boundary rule", "Application"],
  ["Body location", "When location is separate, tag it as B and tag only the symptom as S: [chest]{B} [pain]{S}."],
  ["Lexical symptoms", "Do not split a symptom that normally stands alone, such as headache or breathlessness."],
  ["Negation", "N contains only the denied symptom. Never include no, not, denies, or without."],
  ["Diseases", "Use C for known conditions, not for a suspected diagnosis inferred from symptoms."],
  ["Medication", "M is the medicine name. Q is dosage/instruction. U is whether the patient takes, stopped, missed, or changed it."],
  ["Allergy", "A is the substance. E is the reaction. Do not mark a historical allergy reaction as a current S symptom."],
  ["Laboratory", "T is the test name. L is the reported value and unit. Do not interpret whether it is high or low."],
  ["No nesting", "Spans must not overlap or nest. Every character belongs to at most one labelled span."],
];

for (const ds of datasets) {
  const sheet = ds.sheet;
  sheet.getRange("A1:D1").values = [headers];
  const matrix = ds.rows.map((text, i) => [`train_${ds.key}_${String(i + 1).padStart(4, "0")}`, ds.author, text, "llm"]);
  sheet.getRangeByIndexes(1, 0, matrix.length, 4).values = matrix;
}

const navy = "#284B45";
const green = "#557C73";
const cream = "#F7F1E6";
const light = "#FFFDF8";
const font = "Arial";
for (const sheet of [summary, codebook, ...datasets.map(x => x.sheet)]) sheet.showGridLines = false;

summary.getRange("A1:D1").format = { fill: navy, font: { name: font, size: 15, bold: true, color: "#FFFFFF" }, rowHeight: 28 };
for (const r of [summary.getRange("A3:D3"), summary.getRange("A11:A11"), summary.getRange("D11:D11"), codebook.getRange("A1:C1"), codebook.getRange("E1:F1")]) r.format = { fill: green, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
summary.getRange("A4:D9").format = { font: { name: font, size: 10 }, verticalAlignment: "top", wrapText: true };
summary.getRange("A9:D9").format = { fill: cream, font: { name: font, size: 10, bold: true } };
summary.getRange("A12:A16").format = { fill: light, font: { name: font, size: 10 }, verticalAlignment: "top", wrapText: true };
summary.getRange("D12:D16").format = { fill: light, font: { name: font, size: 10 }, verticalAlignment: "top", wrapText: true };
summary.getRange("A:A").format.columnWidth = 26;
summary.getRange("B:C").format.columnWidth = 16;
summary.getRange("D:D").format.columnWidth = 70;

codebook.getRange(`A2:C${tagDefinitions.length + 1}`).format = { font: { name: font, size: 10 }, verticalAlignment: "top", wrapText: true };
codebook.getRange("E2:F9").format = { fill: cream, font: { name: font, size: 10 }, verticalAlignment: "top", wrapText: true };
codebook.getRange("A:A").format.columnWidth = 12;
codebook.getRange("B:B").format.columnWidth = 52;
codebook.getRange("C:C").format.columnWidth = 42;
codebook.getRange("E:E").format.columnWidth = 22;
codebook.getRange("F:F").format.columnWidth = 72;
codebook.freezePanes.freezeRows(1);

for (const ds of datasets) {
  const sheet = ds.sheet;
  sheet.getRange("A1:D1").format = { fill: green, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRangeByIndexes(1, 0, ds.count, 4).format = { font: { name: font, size: 10 }, verticalAlignment: "top" };
  sheet.getRangeByIndexes(1, 2, ds.count, 1).format.wrapText = true;
  sheet.getRange("A:A").format.columnWidth = 22;
  sheet.getRange("B:B").format.columnWidth = 24;
  sheet.getRange("C:C").format.columnWidth = 105;
  sheet.getRange("D:D").format.columnWidth = 12;
  sheet.freezePanes.freezeRows(1);
}

wb.recalculate();
const previewSheets = [summary, codebook, ...datasets.map(x => x.sheet)];
for (const sheet of previewSheets) {
  const range = sheet === summary ? "A1:D16" : sheet === codebook ? "A1:F17" : "A1:D12";
  const preview = await wb.render({ sheetName: sheet.name, range, scale: 1.1, format: "png" });
  await fs.writeFile(outputPath.replace(".xlsx", `_${sheet.name.toLowerCase()}_preview.png`), new Uint8Array(await preview.arrayBuffer()));
}

const inspectSummary = await wb.inspect({ kind: "table", range: "SUMMARY!A1:D16", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 8 });
console.log(inspectSummary.ndjson);
for (const ds of datasets) {
  const inspect = await wb.inspect({ kind: "table", range: `${ds.sheet.name}!A1:D4`, include: "values,formulas", tableMaxRows: 6, tableMaxCols: 5 });
  console.log(inspect.ndjson);
}
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
console.log(errors.ndjson);

const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(outputPath);
console.log(JSON.stringify({ outputPath, totalRows: total, counts: datasets.map(ds => ({ sheet: ds.sheet.name, rows: ds.count, deniedRows: ds.rows.filter(x => x.includes("{N}")).length, tags: countTags(ds.rows) })) }, null, 2));

