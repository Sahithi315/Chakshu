"""OCR and medical report processing pipeline supporting text-based PDFs, scanned PDFs, and images.
Extracts structured laboratory results, prescription medications, document types, and clinical findings.
"""
from pathlib import Path
import io
import re
import shutil
import subprocess
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2

from src.reports.extract import extract_pdf, outside_listed_range, quote_check

# Known lab test names for robust identification
COMMON_TEST_NAMES = [
    "Hemoglobin", "Haemoglobin", "Hb", "HbA1c", "Fasting Blood Sugar", "Post Prandial Blood Sugar",
    "Random Blood Sugar", "Creatinine", "Blood Urea", "Uric Acid", "Total Cholesterol", "HDL Cholesterol",
    "LDL Cholesterol", "Triglycerides", "Total Bilirubin", "Direct Bilirubin", "SGOT", "AST", "SGPT", "ALT",
    "Alkaline Phosphatase", "ALP", "Total Protein", "Albumin", "Globulin", "WBC Count", "Total Leukocyte Count",
    "TLC", "RBC Count", "Platelet Count", "Platelets", "ESR", "Erythrocyte Sedimentation Rate",
    "CRP", "C-Reactive Protein", "hs-CRP", "TSH", "Free T3", "Free T4", "Sodium", "Potassium", "Chloride",
    "Calcium", "MCV", "MCH", "MCHC", "PCV", "Hematocrit", "Neutrophils", "Lymphocytes", "Eosinophils",
    "Monocytes", "Basophils", "Ferritin", "Serum Iron", "TIBC", "Vitamin B12", "Vitamin D", "Widal Test"
]

COMMON_MEDICINE_PREFIXES = (
    r"(?:tab(?:let)?\.?|cap(?:sule)?\.?|syp(?:rup)?\.?|inj(?:ection)?\.?|oint(?:ment)?\.?|"
    r"cream|gel|lotion|shampoo|drops?|susp(?:ension)?\.?|spray|inhaler|sachet)"
)

COMMON_MEDICINE_NAMES = [
    "Paracetamol", "Pantoprazole", "Omeprazole", "Rabeprazole", "Esomeprazole", "Ranitidine", "Famotidine",
    "Amoxicillin", "Azithromycin", "Cefixime", "Ciprofloxacin", "Levofloxacin", "Ceftriaxone", "Doxycycline",
    "Metronidazole", "Augmentin", "Clavulanic", "Cefuroxime", "Metformin", "Glimepiride", "Teneligliptin",
    "Dapagliflozin", "Vildagliptin", "Insulin", "Telmisartan", "Amlodipine", "Losartan", "Atenolol",
    "Metoprolol", "Enalapril", "Ramipril", "Hydrochlorothiazide", "Atorvastatin", "Rosuvastatin",
    "Cetirizine", "Levocetirizine", "Montelukast", "Fexofenadine", "Ibuprofen", "Diclofenac",
    "Aceclofenac", "Tramadol", "Ketoconazole", "Fluconazole", "Itraconazole", "Clotrimazole",
    "Vitamin B12", "Vitamin D3", "Vitamin D", "Vitamin C", "Calcium", "Iron", "Folic Acid",
    "Multivitamin", "B-Complex", "Zinc", "Ondansetron", "Domperidone", "Salbutamol", "Budesonide",
    "Ketoconazole Shampoo", "Ketoconazole Cream", "Mupirocin", "Betamethasone", "Cefpodoxime",
    "Ofloxacin", "Combiflam", "Pan 40", "Dolo 650", "Calpol", "ORS", "ORS Sachet", "Oral Rehydration Salts"
]

TIMING_PATTERNS = [
    (r"\b(?:before\s+food|before\s+meals?|empty\s+stomach|a\.?c\.?)\b", "Before food"),
    (r"\b(?:after\s+food|after\s+meals?|with\s+food|with\s+meals?|p\.?c\.?)\b", "After food"),
    (r"\b(?:at\s+bedtime|bedtime|night\s+only|h\.?s\.?|q\.?h\.?s\.?)\b", "At bedtime"),
    (r"\b(?:in\s+the\s+morning|morning\s+only)\b", "Morning"),
]

FREQUENCY_PATTERNS = [
    (r"\b(?:once\s+daily|once\s+a\s+day|1\s+time\s+daily|q\.?d\.?|o\.?d\.?)\b", "Once daily"),
    (r"\b(?:twice\s+daily|two\s+times\s+daily|2\s+times\s+daily|b\.?i\.?d\.?|b\.?d\.?)\b", "Twice daily"),
    (r"\b(?:thrice\s+daily|three\s+times\s+a\s+day|3\s+times\s+daily|t\.?i\.?d\.?|t\.?d\.?s\.?)\b", "Thrice daily"),
    (r"\b(?:four\s+times\s+daily|q\.?i\.?d\.?|q\.?d\.?s\.?)\b", "Four times daily"),
    (r"\b(?:every\s+\d+\s+hours?)\b", None),
    (r"\b(?:twice\s+weekly|2\s+times\s+a\s+week)\b", "Twice weekly"),
    (r"\b(?:once\s+weekly|1\s+time\s+a\s+week|weekly|w/\s*1)\b", "Once weekly"),
    (r"\b1-0-1\b", "Twice daily (1-0-1)"),
    (r"\b1-0-0\b", "Once daily morning (1-0-0)"),
    (r"\b0-0-1\b", "Once daily night (0-0-1)"),
    (r"\b1-1-1\b", "Thrice daily (1-1-1)"),
    (r"\b0-1-0\b", "Once daily afternoon (0-1-0)"),
    (r"\b(?:s\.?o\.?s\.?|as\s+needed|prn)\b", "As needed (SOS)"),
]

ROUTE_PATTERNS = [
    (r"\b(?:oral|by\s+mouth|p\.?o\.?)\b", "Oral"),
    (r"\b(?:topical|local\s+application|external\s+use)\b", "Topical"),
    (r"\b(?:shampoo)\b", "Topical / Shampoo"),
    (r"\b(?:i\.?v\.?|intravenous)\b", "Intravenous (IV)"),
    (r"\b(?:i\.?m\.?|intramuscular)\b", "Intramuscular (IM)"),
    (r"\b(?:eye\s+drops?|ophthalmic)\b", "Ophthalmic"),
    (r"\b(?:ear\s+drops?|otic)\b", "Otic"),
    (r"\b(?:inhalation|inhaler)\b", "Inhalation"),
]

DURATION_PATTERN = re.compile(
    r"\b(?:for\s+|x\s*)?(\d+)\s*(days?|weeks?|months?|d|wks?|mths?)\b|\b(?:sos|continue)\b",
    re.IGNORECASE
)

DOSAGE_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|gm|ml|%|iu|units)(?:/\d+(?:\.\d+)?\s*(?:ml|mg))?)(?!\w)",
    re.IGNORECASE
)

WIDAL_PATTERN = re.compile(
    r"(?P<test>(?:widal\s*(?:test)?\s*[-–:]?\s*)?S(?:almonella|\.)?\s*(?:typhi|paratyphi)\s*[O|H|AH|BH|A|B](?:'?[OHABH]+'?)?)\s*"
    r"[:\-–]?\s*"
    r"(?P<value>[1lI|4\d]\s*[:/]\s*\d+)\s*"
    r"(?:(?P<unit>titer|dilution)\s*)?"
    r"(?:\(?(?P<range>(?:<|<=|>|>=)?\s*[1lI|4\d]\s*[:/]\s*\d+|negative|normal|nil|up\s+to\s+1\s*[:/]\s*\d+)\)?)?"
    r"(?:\s+(?P<flag>HIGH|LOW|NORMAL|POSITIVE|REACTIVE|NEGATIVE|SIGNIFICANT))?",
    re.IGNORECASE
)

FLEX_LAB_PATTERN = re.compile(
    r"^(?P<test>[A-Za-z0-9\s\(\)/_\-\.,\+]+?)\s*[:\-–]?\s+"
    r"(?P<value>-?\d+(?:,\d+)*(?:\.\d+)?|1:\d+|Positive|Negative|Reactive|Non-Reactive)\s*"
    r"(?P<unit>%|[a-zA-Z/%µ\^]+(?:/[a-zA-Z0-9\^µ\.\-]+)?|million/[a-zA-Zµ]+|lakhs?/[a-zA-Z]+|mm/(?:hr|1st\s*hr)|cells?/[a-zA-Z]+)?\s*"
    r"(?:\(?(?P<flag_mid>Low|High|Normal|Critical|Abnormal|In_Range|\*)\)?\s*)?"
    r"(?P<range>(?:\d+(?:,\d+)*(?:\.\d+)?\s*[-–—to~]+\s*\d+(?:,\d+)*(?:\.\d+)?|[<>]=?\s*\d+(?:,\d+)*(?:\.\d+)?|1:\d+|<1:\d+))\s*"
    r"(?:[a-zA-Z/%µ\^]+(?:/[a-zA-Z0-9\^µ\.\-]+)?\s*)?"
    r"(?:\(?(?P<flag_end>Low|High|Normal|Critical|Abnormal|In_Range|\*)\)?)?$",
    re.IGNORECASE
)


def is_tesseract_available():
    """Check if tesseract binary is accessible and configure default paths."""
    if shutil.which("tesseract"):
        return True
    try:
        import pytesseract
        default_win_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if default_win_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(default_win_path)
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def preprocess_image(image, attempt=1):
    """
    Enhance document image contrast, sharpness, orientation and resolution.
    Supports multi-pass attempts (attempt 1: contrast/sharpness, attempt 2: binarization).
    """
    # 1. Orientation from EXIF if present
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    # 2. Upscale small images for OCR clarity
    w, h = image.size
    if w < 1200 or h < 1200:
        scale = max(1.5, 1400 / max(w, h))
        new_size = (int(w * scale), int(h * scale))
        image = image.resize(new_size, Image.Resampling.BICUBIC)

    # 3. Grayscale conversion
    if image.mode != "L":
        gray = image.convert("L")
    else:
        gray = image

    # 4. Attempt-specific processing
    if attempt == 1:
        stretched = ImageOps.autocontrast(gray, cutoff=2)
        sharp = ImageEnhance.Sharpness(stretched).enhance(2.0)
        contrast = ImageEnhance.Contrast(sharp).enhance(1.4)
        return contrast
    else:
        # High contrast binarization / thresholding fallback
        stretched = ImageOps.autocontrast(gray, cutoff=3)
        fn = lambda x: 255 if x > 140 else 0
        binarized = stretched.point(fn, mode="1")
        return binarized.convert("L")


def ocr_image(image):
    """Run Tesseract OCR on a PIL Image object with multi-PSM and multi-pass fallback."""
    is_avail = is_tesseract_available()
    if not is_avail:
        return ""

    import pytesseract
    preprocessed = preprocess_image(image, attempt=1)

    best_text = ""
    # Try PSM 6 first, fallback to PSM 3 (automatic page segmentation) or PSM 4
    for psm in [6, 3, 4]:
        try:
            text = pytesseract.image_to_string(preprocessed, config=f"--psm {psm}")
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
            if len(text.strip().splitlines()) >= 4:
                break
        except Exception:
            continue

    # If first attempt produced very little text, try attempt 2 (binarized)
    if len(best_text.strip()) < 50:
        try:
            prep2 = preprocess_image(image, attempt=2)
            text2 = pytesseract.image_to_string(prep2, config="--psm 3")
            if len(text2.strip()) > len(best_text.strip()):
                best_text = text2
        except Exception:
            pass

    return best_text


def identify_document_type(text, filename=""):
    """
    Automatically identify document type:
    'Prescription', 'Blood / Laboratory Report', 'Widal / Serology Report',
    'Discharge Summary', 'Diagnostic Examination Report', or 'General Medical Document'.
    """
    combined = f"{filename} {text}".lower()

    if any(k in combined for k in ["widal", "typhi", "paratyphi", "enteric fever"]):
        return "Widal / Serology Report"
    if any(k in combined for k in ["prescription", "rx", "dr.", "opd prescription", "cghs", "dosage", "frequency", "days"]):
        return "Prescription"
    if any(k in combined for k in ["haematology", "complete blood count", "cbc", "biochemistry", "pathology", "reference range", "observed value", "lft", "kft", "lipid profile"]):
        return "Blood / Laboratory Report"
    if any(k in combined for k in ["discharge summary", "date of admission", "date of discharge", "discharge diagnosis"]):
        return "Discharge Summary"
    if any(k in combined for k in ["radiology", "ultrasound", "x-ray", "ecg", "echo", "ct scan", "mri"]):
        return "Diagnostic Examination Report"
    return "Laboratory Investigation Report" if "test" in combined or "result" in combined else "General Medical Document"


def determine_lab_status(test, val_str, range_str, flag_str=""):
    """
    Determine abnormality status (High, Low, Normal) and human-readable range note.
    Evaluates explicit flags first, then handles Widal titers and numeric ranges.
    """
    flag_upper = (flag_str or "").upper().strip("()")
    if any(h in flag_upper for h in ["HIGH", "ABNORMAL", "CRITICAL", "*", "POSITIVE", "REACTIVE", "SIGNIFICANT"]):
        return "High", "outside listed range"
    if any(l in flag_upper for l in ["LOW"]):
        return "Low", "outside listed range"
    if "NORMAL" in flag_upper or "IN_RANGE" in flag_upper or "NEGATIVE" in flag_upper:
        return "Normal", ""

    # Check for Widal titer format (e.g. 1:320, 1:160, 1:80)
    titer_m = re.match(r"^1\s*[:/]\s*(\d+)$", str(val_str).strip())
    if titer_m:
        denom = int(titer_m.group(1))
        # In endemic areas, S. typhi O/H >= 1:160 is clinically significant/high
        if denom >= 160:
            return "High", "outside listed range"
        else:
            return "Normal", ""

    # Check qualitative text results
    v_clean = str(val_str).strip().lower()
    if v_clean in ["positive", "reactive", "detected"]:
        return "High", "outside listed range"
    if v_clean in ["negative", "non-reactive", "not detected"]:
        return "Normal", ""

    # Numeric comparison
    try:
        num_val = float(str(val_str).replace(",", "").strip())
        rng_clean = str(range_str).replace(",", "").strip()

        # Format: low - high
        m_rng = re.match(r"^(\d+(?:\.\d+)?)\s*[-–—to~]+\s*(\d+(?:\.\d+)?)$", rng_clean)
        if m_rng:
            low = float(m_rng.group(1))
            high = float(m_rng.group(2))
            if num_val < low:
                return "Low", "outside listed range"
            elif num_val > high:
                return "High", "outside listed range"
            else:
                return "Normal", ""

        # Format: < high or <= high
        m_less = re.match(r"^<=\s*(\d+(?:\.\d+)?)$|^<\s*(\d+(?:\.\d+)?)$", rng_clean)
        if m_less:
            high = float(m_less.group(1) or m_less.group(2))
            if num_val > high:
                return "High", "outside listed range"
            else:
                return "Normal", ""

        # Format: > low or >= low
        m_great = re.match(r"^>=\s*(\d+(?:\.\d+)?)$|^>\s*(\d+(?:\.\d+)?)$", rng_clean)
        if m_great:
            low = float(m_great.group(1) or m_great.group(2))
            if num_val < low:
                return "Low", "outside listed range"
            else:
                return "Normal", ""
    except Exception:
        pass

    return "Normal", ""


def parse_lab_lines(raw_text, page_no=1, source_mode="ocr"):
    """
    Parse raw OCR or PDF text into structured lab records.
    Returns list of dicts with:
    test, value, unit, reference_range, range_note, status, page, bbox, source_line, quote_ok, extraction_method
    """
    rows = []
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    boilerplate = [
        "patient", "doctor", "signature", "hospital", "date", "age", "gender", "token",
        "referred", "report date", "collection date", "investigation report", "page",
        "specimen", "educational sample", "fictional results"
    ]

    for line in lines:
        lower = line.lower()
        if any(b == lower or lower.startswith(b + ":") for b in boilerplate):
            continue
        if "test antigen" in lower or "investigation observed" in lower or "test fictional result" in lower:
            continue

        # 1. Check for Widal test serology lines
        wm = WIDAL_PATTERN.search(line)
        if wm:
            test = wm.group("test").strip()
            test = re.sub(r"\s+", " ", test)
            val = wm.group("value").replace(" ", "")
            val = re.sub(r"^[lI|4]:", "1:", val)
            unit = wm.group("unit") or "titer"
            rng = wm.group("range") or "< 1:80"
            rng = re.sub(r"(?:[lI|4]:)", "1:", rng)
            flag = wm.group("flag") or ""
            status, note = determine_lab_status(test, val, rng, flag)

            rows.append({
                "test": test,
                "value": val,
                "unit": unit,
                "reference_range": rng,
                "status": status,
                "range_note": note,
                "page": page_no,
                "bbox": [0, 0, 0, 0],
                "source_line": line,
                "quote_ok": True,
                "extraction_method": source_mode
            })
            continue

        # 2. Check flexible lab pattern
        lm = FLEX_LAB_PATTERN.search(line)
        if lm:
            test = lm.group("test").strip()
            if any(w in test.lower() for w in ["patient", "doctor", "referred", "report", "specimen"]):
                continue
            val = lm.group("value").strip()
            val = re.sub(r"^[lI|4]:", "1:", val)
            unit = (lm.group("unit") or "").strip()
            unit_map = {
                "ful": "/uL", "fuL": "/uL", "/ul": "/uL",
                "mnvhr": "mm/hr", "mmvhr": "mm/hr", "mn/hr": "mm/hr",
                "mgldl": "mg/dL", "gldl": "g/dL"
            }
            if unit.lower() in unit_map:
                unit = unit_map[unit.lower()]
            rng = (lm.group("range") or "").strip()
            rng = re.sub(r"(?:[lI|4]:)", "1:", rng)
            flag = lm.group("flag_mid") or lm.group("flag_end") or ""

            status, note = determine_lab_status(test, val, rng, flag)
            rows.append({
                "test": test,
                "value": val,
                "unit": unit,
                "reference_range": rng,
                "status": status,
                "range_note": note,
                "page": page_no,
                "bbox": [0, 0, 0, 0],
                "source_line": line,
                "quote_ok": quote_check(val, line),
                "extraction_method": source_mode
            })

    return rows


def extract_medications_from_text(raw_text, source_mode="ocr"):
    """
    Identify and extract structured prescription medicines:
    - medicine_name
    - dosage / strength
    - frequency
    - timing
    - duration
    - route
    - instructions
    - source_line
    """
    medications = []
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    for i, line in enumerate(lines):
        lower_line = line.lower()
        if any(h in lower_line for h in ["medicine status", "beneficiary id", "cghs toll-free", "play store", "download the", "chronic disease"]):
            continue
        if lower_line.startswith(("dr.", "doctor", "name:", "patient:", "date:", "opd prescription", "planned visit", "dosage & timing:", "dosage:", "frequency:", "timing:", "instructions:", "general clinical", "advice:")):
            continue

        has_prefix = bool(re.search(r"\b" + COMMON_MEDICINE_PREFIXES + r"\b", lower_line))
        has_known_med = any(med.lower() in lower_line for med in COMMON_MEDICINE_NAMES)
        has_dose = bool(DOSAGE_PATTERN.search(line))
        has_freq = any(re.search(pat, lower_line) for pat, _ in FREQUENCY_PATTERNS)
        is_numbered = bool(re.match(r"^\d+[\.\)]\s*", line))

        is_med_line = (
            (is_numbered and (has_dose or has_freq or has_known_med))
            or (has_prefix and (has_dose or has_known_med))
            or has_known_med
            or (has_dose and has_freq)
        )
        if not is_med_line:
            continue

        # Lookahead for continuation lines (e.g. Dosage & Timing, Instructions)
        next_lines = []
        j = i + 1
        while j < len(lines) and len(next_lines) < 3:
            nxt = lines[j]
            nxt_low = nxt.lower()
            if re.match(r"^\d+[\.\)]\s*", nxt) or nxt_low.startswith(("rx", "tab ", "cap ", "inj ", "dr.", "patient", "general ", "advice")):
                break
            next_lines.append(nxt)
            j += 1

        clean_line = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        continuation_text = " ".join(next_lines)
        full_context = f"{clean_line} {continuation_text}".strip()

        # 1. Extract dosage/strength
        dose_m = DOSAGE_PATTERN.search(clean_line) or DOSAGE_PATTERN.search(full_context)
        dosage = dose_m.group(1).strip() if dose_m else "Not specified"

        # 2. Extract frequency
        frequency = "Not specified"
        for pat, repl in FREQUENCY_PATTERNS:
            fm = re.search(pat, full_context, re.IGNORECASE)
            if fm:
                frequency = repl if repl else fm.group(0).capitalize()
                break

        # 3. Extract timing
        timing = "Not specified"
        for pat, repl in TIMING_PATTERNS:
            tm = re.search(pat, full_context, re.IGNORECASE)
            if tm:
                timing = repl
                break

        # 4. Extract duration
        dur_m = DURATION_PATTERN.search(full_context)
        if dur_m:
            if dur_m.group(1) and dur_m.group(2):
                num = dur_m.group(1)
                unit_str = dur_m.group(2).lower()
                unit = "days" if unit_str.startswith("d") else "weeks" if unit_str.startswith("w") else "months" if unit_str.startswith("m") else unit_str
                duration = f"{num} {unit}"
            else:
                duration = dur_m.group(0).strip().upper()
        else:
            duration = "Not specified"

        # 5. Extract route
        route = "Not specified"
        for pat, repl in ROUTE_PATTERNS:
            rm = re.search(pat, full_context, re.IGNORECASE)
            if rm:
                route = repl
                break
        if route == "Not specified":
            if any(p in full_context.lower() for p in ["tab", "tablet", "cap", "capsule", "syp", "syrup"]):
                route = "Oral"
            elif "sachet" in full_context.lower() or "ors" in full_context.lower():
                route = "Oral Solution"
            elif any(p in full_context.lower() for p in ["oint", "cream", "gel", "lotion", "apply"]):
                route = "Topical"
            elif "shampoo" in full_context.lower():
                route = "Topical / Shampoo"

        # 6. Extract instructions
        instructions = "Not specified"
        inst_m = re.search(r"instructions?\s*[:\-–]\s*([^\n\r]+)", continuation_text, re.IGNORECASE)
        if inst_m:
            instructions = inst_m.group(1).strip()
        else:
            inst_inline = re.search(r"\b(apply\s+[^,\.\n\-]+|take\s+with\s+[^,\.\n\-]+|dissolve\s+[^,\.\n\-]+|rinse\s+[^,\.\n\-]+)", full_context, re.IGNORECASE)
            if inst_inline:
                instructions = inst_inline.group(1).strip()
            elif timing != "Not specified":
                instructions = f"Take {timing.lower()}"

        # 7. Extract medicine name
        med_name = clean_line
        # Remove numbers at start
        med_name = re.sub(r"^\d+\s+", "", med_name)
        med_name = re.sub(r"^(?:tab(?:let)?\.?|cap(?:sule)?\.?|syp(?:rup)?\.?|inj(?:ection)?\.?|oint(?:ment)?\.?)\s+", "", med_name, flags=re.IGNORECASE)

        for sep in [" - ", " – ", " — ", " : ", " / "]:
            if sep in med_name:
                parts = med_name.split(sep)
                med_name = parts[0]
                break

        if dosage != "Not specified" and dosage in med_name:
            med_name = med_name.replace(dosage, "").strip()

        med_name = re.sub(r"[-–—,;:/\s]+$", "", med_name).strip()
        med_name = re.sub(r"\b(?:w/\s*\d+|od|bd|tds|qid|hs|sos)\b.*$", "", med_name, flags=re.IGNORECASE).strip()
        med_name = re.sub(r"[=|\\]+.*$", "", med_name).strip()
        med_name = re.sub(r"\b(?:once|twice|thrice|daily|od|bd|tds|1-0-1|1-0-0|1-1-1)\b.*$", "", med_name, flags=re.IGNORECASE).strip()
        med_name = re.sub(r"\s+", " ", med_name).strip()

        if len(med_name) >= 3 and not any(w == med_name.lower() for w in ["medicine", "dosage", "frequency", "rx", "name", "total"]):
            medications.append({
                "medicine_name": med_name,
                "dosage": dosage,
                "frequency": frequency,
                "timing": timing,
                "duration": duration,
                "route": route,
                "instructions": instructions,
                "source_line": line,
                "extraction_method": source_mode
            })

    return medications


def extract_medical_findings(text, lab_rows, med_rows, doc_type):
    """
    Identify and organize important medical information:
    - Abnormal lab values
    - Diagnostic observations
    - Mentioned medical conditions
    - Relevant clinical recommendations
    - Automated insights (clearly labelled as requiring doctor verification)
    """
    findings = []
    text_lower = text.lower()

    # 1. Abnormal lab values
    for lab in lab_rows:
        if lab.get("status") in ["High", "Low"]:
            findings.append({
                "category": "abnormal_lab",
                "title": f"Abnormal {lab['test']}: {lab['value']} {lab.get('unit', '')}",
                "detail": f"Observed result {lab['value']} {lab.get('unit', '')} is {lab.get('status', '').upper()} (Reference: {lab.get('reference_range', 'Normal')}).",
                "severity": "high" if lab.get("status") == "High" else "warning",
                "source_line": lab.get("source_line", ""),
                "is_automated": 1
            })

    # 2. Diagnostic observations from text (e.g. Impression, Diagnosis, Conclusion)
    imp_match = re.search(r"(?:impression|conclusion|interpretation|diagnosis)\s*[:\-–]\s*([^\n\r]+(?:\n[^\n\r]+)?)", text, re.IGNORECASE)
    if imp_match:
        imp_text = imp_match.group(1).strip()
        findings.append({
            "category": "diagnostic_observation",
            "title": "Clinical Diagnostic Impression",
            "detail": imp_text,
            "severity": "info",
            "source_line": imp_match.group(0),
            "is_automated": 0
        })

    # 3. Mentioned conditions
    condition_keywords = [
        ("Typhoid / Enteric Fever", ["typhoid", "enteric fever", "s. typhi", "salmonella"]),
        ("Iron Deficiency Anemia", ["iron deficiency", "microcytic hypochromic", "low ferritin", "low hemoglobin"]),
        ("Diabetes Mellitus", ["diabetes", "hyperglycemia", "diabetic", "elevated hba1c"]),
        ("Hypertension", ["hypertension", "high blood pressure", "htn"]),
        ("Dyslipidemia", ["dyslipidemia", "hypercholesterolemia", "elevated triglycerides"]),
        ("Seborrheic Dermatitis / Fungal", ["tinea", "dermatitis", "seborrheic", "scalp infection"]),
    ]
    for cond_name, kws in condition_keywords:
        if any(kw in text_lower for kw in kws):
            findings.append({
                "category": "condition",
                "title": f"Mentioned Clinical Condition: {cond_name}",
                "detail": f"Document context and lab parameters correspond with {cond_name}.",
                "severity": "warning",
                "source_line": cond_name,
                "is_automated": 1
            })

    # 4. Clinical recommendations
    rec_match = re.search(r"(?:recommendation|advice|plan|suggested)\s*[:\-–]\s*([^\n\r]+)", text, re.IGNORECASE)
    if rec_match:
        findings.append({
            "category": "recommendation",
            "title": "Document Clinical Recommendation",
            "detail": rec_match.group(1).strip(),
            "severity": "info",
            "source_line": rec_match.group(0),
            "is_automated": 0
        })

    # 5. Automated preliminary clinical insight
    abnormal_count = sum(1 for l in lab_rows if l.get("status") in ["High", "Low"])
    med_count = len(med_rows)
    insight_text = ""
    if any("s. typhi" in l.get("test", "").lower() and l.get("status") == "High" for l in lab_rows):
        insight_text = "Elevated Salmonella serology (Widal) titers observed alongside acute inflammatory markers. Suggestive of active enteric infection; recommend clinical correlation with febrile illness timeline."
    elif any("haemoglobin" in l.get("test", "").lower() or "hemoglobin" in l.get("test", "").lower() for l in lab_rows) and abnormal_count > 0:
        insight_text = "Hematological indices indicate out-of-range red cell parameters. Recommend assessing for underlying nutritional deficiency or chronic blood loss."
    elif med_count > 0:
        insight_text = f"Identified {med_count} prescribed medication(s) from document. Verify adherence and check for potential cross-sensitivities or duplicate therapies."

    if insight_text:
        findings.append({
            "category": "insight",
            "title": "Automated Preliminary Clinical Insight (Requires Doctor Verification)",
            "detail": insight_text,
            "severity": "info",
            "source_line": "AI-Assisted Preliminary Analysis (Non-diagnostic)",
            "is_automated": 1
        })

    return findings


def process_report_file(file_path):
    """
    Process any supported document (text PDF, scanned PDF, JPG, PNG).
    Returns a dict with:
        status: 'success' | 'warning' | 'error'
        doc_type: string
        extracted_rows: list of extracted lab items
        extracted_medications: list of extracted prescription medicines
        document_findings: list of abnormal findings and insights
        raw_text: full extracted text
        pages_processed: int
        findings_count: int
        message: informative message
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "status": "error",
            "doc_type": "Unknown",
            "extracted_rows": [],
            "extracted_medications": [],
            "document_findings": [],
            "raw_text": "",
            "pages_processed": 0,
            "findings_count": 0,
            "message": f"File not found on disk: {path}"
        }

    ext = path.suffix.lower()

    if ext == ".pdf":
        all_text_list = []
        all_lab_rows = []
        pages_count = 1

        # 1. Attempt digital extraction via pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages_count = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages, 1):
                    p_text = page.extract_text(layout=False) or ""
                    # Check if page has sufficient text content
                    clean_text_chars = len(re.sub(r"\s+", "", p_text))
                    if clean_text_chars >= 40:
                        all_text_list.append(f"--- Page {page_idx} ---\n" + p_text)
                        # Extract labs from page digital text
                        p_labs = parse_lab_lines(p_text, page_no=page_idx, source_mode="pdf_digital")
                        all_lab_rows.extend(p_labs)
                    else:
                        # Scanned PDF page fallback: render to image and run OCR
                        if is_tesseract_available():
                            try:
                                pdfium_doc = pypdfium2.PdfDocument(str(path))
                                pil_image = pdfium_doc[page_idx - 1].render(scale=2.5).to_pil()
                                ocr_text = ocr_image(pil_image)
                                all_text_list.append(f"--- Page {page_idx} (OCR) ---\n" + ocr_text)
                                p_labs = parse_lab_lines(ocr_text, page_no=page_idx, source_mode="ocr_scanned_pdf")
                                all_lab_rows.extend(p_labs)
                            except Exception:
                                pass
        except Exception:
            pass

        # Also check structured extract_pdf if standard layout
        if not all_lab_rows:
            try:
                pdf_rows = extract_pdf(str(path))
                if pdf_rows:
                    all_lab_rows.extend(pdf_rows)
                    if not all_text_list:
                        all_text_list.append("\n".join(r.get("source_line", "") for r in pdf_rows))
            except Exception:
                pass

        full_text = "\n\n".join(all_text_list)
        doc_type = identify_document_type(full_text, path.name)
        med_rows = extract_medications_from_text(full_text, source_mode="pdf_text")
        findings = extract_medical_findings(full_text, all_lab_rows, med_rows, doc_type)
        findings_count = len(all_lab_rows) + len(med_rows) + len(findings)

        if not full_text.strip() and not all_lab_rows:
            return {
                "status": "warning",
                "doc_type": "PDF Document",
                "extracted_rows": [],
                "extracted_medications": [],
                "document_findings": [],
                "raw_text": "",
                "pages_processed": pages_count,
                "findings_count": 0,
                "message": "Document uploaded, but no text or clinical data could be extracted. Please ensure the document is clear."
            }

        return {
            "status": "success",
            "doc_type": doc_type,
            "extracted_rows": all_lab_rows,
            "extracted_medications": med_rows,
            "document_findings": findings,
            "raw_text": full_text,
            "pages_processed": pages_count,
            "findings_count": findings_count,
            "message": f"Processed {doc_type}: {len(all_lab_rows)} lab result(s), {len(med_rows)} medication(s) identified."
        }

    elif ext in (".png", ".jpg", ".jpeg"):
        if not is_tesseract_available():
            return {
                "status": "warning",
                "doc_type": "Medical Image",
                "extracted_rows": [],
                "extracted_medications": [],
                "document_findings": [],
                "raw_text": "",
                "pages_processed": 1,
                "findings_count": 0,
                "message": "Tesseract OCR engine is not configured. Cannot extract text from image."
            }

        try:
            with Image.open(path) as img:
                ocr_text = ocr_image(img)

            if not ocr_text.strip():
                return {
                    "status": "warning",
                    "doc_type": "Medical Image",
                    "extracted_rows": [],
                    "extracted_medications": [],
                    "document_findings": [],
                    "raw_text": "",
                    "pages_processed": 1,
                    "findings_count": 0,
                    "message": "OCR could not read text from the image. Please take a clearer, well-lit photograph."
                }

            doc_type = identify_document_type(ocr_text, path.name)
            lab_rows = parse_lab_lines(ocr_text, page_no=1, source_mode="ocr_image")
            med_rows = extract_medications_from_text(ocr_text, source_mode="ocr_image")
            findings = extract_medical_findings(ocr_text, lab_rows, med_rows, doc_type)
            findings_count = len(lab_rows) + len(med_rows) + len(findings)

            return {
                "status": "success" if (lab_rows or med_rows) else "warning",
                "doc_type": doc_type,
                "extracted_rows": lab_rows,
                "extracted_medications": med_rows,
                "document_findings": findings,
                "raw_text": ocr_text,
                "pages_processed": 1,
                "findings_count": findings_count,
                "message": f"Processed {doc_type}: {len(lab_rows)} lab result(s), {len(med_rows)} medication(s) extracted."
            }
        except Exception as e:
            return {
                "status": "error",
                "doc_type": "Medical Image",
                "extracted_rows": [],
                "extracted_medications": [],
                "document_findings": [],
                "raw_text": "",
                "pages_processed": 1,
                "findings_count": 0,
                "message": f"Image OCR error: {e}"
            }
    else:
        return {
            "status": "error",
            "doc_type": "Unsupported",
            "extracted_rows": [],
            "extracted_medications": [],
            "document_findings": [],
            "raw_text": "",
            "pages_processed": 0,
            "findings_count": 0,
            "message": f"Unsupported file format: {ext}"
        }
