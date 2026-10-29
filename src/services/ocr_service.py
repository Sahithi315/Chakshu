"""OCR and report processing pipeline supporting text-based PDFs, scanned PDFs, and images."""
from pathlib import Path
import io
import re
import shutil
import subprocess
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2

from src.reports.extract import extract_pdf, outside_listed_range, quote_check

# Regular expressions for lab test parsing
LAB_LINE_PATTERN = re.compile(
    r"^(?P<test>[A-Za-z0-9\s\(\)/_\-\.,]+?)\s+"
    r"(?P<value>-?\d+(?:\.\d+)?)\s+"
    r"(?P<unit>[a-zA-Z/%mgdLmmolUL\^\d]+)\s+"
    r"(?P<range>(?:\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?|[<>]=?\s*\d+(?:\.\d+)?))"
    r"(?:\s+(?P<flag>HIGH|LOW|NORMAL|IN_RANGE|ABNORMAL|\*))?",
    re.IGNORECASE
)

COMMON_TEST_NAMES = [
    "Hemoglobin", "HbA1c", "Fasting Blood Sugar", "Post Prandial Blood Sugar", "Random Blood Sugar",
    "Creatinine", "Blood Urea", "Uric Acid", "Total Cholesterol", "HDL Cholesterol", "LDL Cholesterol",
    "Triglycerides", "Total Bilirubin", "Direct Bilirubin", "SGOT", "SGPT", "Alkaline Phosphatase",
    "Total Protein", "Albumin", "Globulin", "WBC Count", "RBC Count", "Platelet Count", "ESR",
    "TSH", "Free T3", "Free T4", "Sodium", "Potassium", "Chloride", "Calcium", "Urine Routine"
]


def is_tesseract_available():
    """Check if tesseract binary is accessible."""
    if shutil.which("tesseract"):
        return True
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def preprocess_image(image):
    """Enhance document image contrast and sharpness for optimal OCR."""
    if image.mode != "L":
        gray = image.convert("L")
    else:
        gray = image

    # Automatic contrast stretching
    stretched = ImageOps.autocontrast(gray, cutoff=2)
    # Enhance sharpness slightly
    sharp = ImageEnhance.Sharpness(stretched).enhance(1.8)
    return sharp


def ocr_image(image):
    """Run Tesseract OCR on a PIL Image object."""
    preprocessed = preprocess_image(image)
    try:
        import pytesseract
        text = pytesseract.image_to_string(preprocessed, config="--psm 6")
        return text
    except Exception:
        # Fallback to direct tesseract subprocess
        with io.BytesIO() as bio:
            preprocessed.save(bio, format="PNG")
            bio.seek(0)
            res = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "6"],
                input=bio.read(),
                capture_output=True,
                check=True
            )
            return res.stdout.decode("utf-8", errors="replace")


def parse_lab_lines(raw_text, page_no=1, source_mode="ocr"):
    """Parse raw OCR or PDF text into structured lab records."""
    rows = []
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    for line in lines:
        # Check standard line pattern: <Test> <Value> <Unit> <Range> [Flag]
        m = LAB_LINE_PATTERN.search(line)
        if m:
            test = m.group("test").strip()
            # Filter out non-test boilerplate words
            if any(w in test.lower() for w in ["patient", "doctor", "age", "date", "sample", "token", "signature"]):
                continue
            val = m.group("value").strip()
            unit = m.group("unit").strip()
            rng = m.group("range").replace(" ", "").strip()

            range_note = "outside listed range" if outside_listed_range(val, rng) else ""
            rows.append({
                "test": test,
                "value": val,
                "unit": unit,
                "reference_range": rng,
                "range_note": range_note,
                "page": page_no,
                "bbox": [0, 0, 0, 0],
                "source_line": line,
                "quote_ok": quote_check(val, line),
                "extraction_method": source_mode
            })
    return rows


def process_report_file(file_path):
    """
    Process any supported document (text PDF, scanned PDF, JPG, PNG).
    Returns a dict with:
        status: 'success' | 'warning' | 'error'
        extracted_rows: list of extracted test items
        raw_text: full extracted text
        pages_processed: int
        message: informative message
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "status": "error",
            "extracted_rows": [],
            "raw_text": "",
            "pages_processed": 0,
            "message": f"File not found on disk: {path}"
        }

    ext = path.suffix.lower()

    if ext == ".pdf":
        # 1. Attempt digital text PDF extraction first
        try:
            pdf_rows = extract_pdf(str(path))
            if pdf_rows:
                # Successfully extracted structured rows from text PDF
                return {
                    "status": "success",
                    "extracted_rows": pdf_rows,
                    "raw_text": "\n".join(r.get("source_line", "") for r in pdf_rows),
                    "pages_processed": max((r.get("page", 1) for r in pdf_rows), default=1),
                    "message": f"Extracted {len(pdf_rows)} lab records via structured PDF parser."
                }
        except Exception:
            pdf_rows = []

        # 2. Scanned PDF fallback via OCR
        if not is_tesseract_available():
            return {
                "status": "warning",
                "extracted_rows": [],
                "raw_text": "",
                "pages_processed": 0,
                "message": "Scanned PDF detected, but Tesseract OCR is not installed. Text could not be extracted."
            }

        try:
            pdf = pypdfium2.PdfDocument(str(path))
            all_rows = []
            full_text_list = []
            for page_idx, page in enumerate(pdf, 1):
                pil_image = page.render(scale=2.0).to_pil()
                page_text = ocr_image(pil_image)
                full_text_list.append(f"--- Page {page_idx} ---\n" + page_text)
                rows = parse_lab_lines(page_text, page_no=page_idx, source_mode="ocr_scanned_pdf")
                all_rows.extend(rows)

            full_text = "\n\n".join(full_text_list)
            if not full_text.strip():
                return {
                    "status": "warning",
                    "extracted_rows": [],
                    "raw_text": "",
                    "pages_processed": len(pdf),
                    "message": "OCR did not detect legible text in the scanned PDF. Please upload a clearer document."
                }

            return {
                "status": "success" if all_rows else "warning",
                "extracted_rows": all_rows,
                "raw_text": full_text,
                "pages_processed": len(pdf),
                "message": f"Scanned PDF processed via OCR: {len(all_rows)} lab records identified."
            }
        except Exception as e:
            return {
                "status": "error",
                "extracted_rows": [],
                "raw_text": "",
                "pages_processed": 0,
                "message": f"Failed to process PDF via OCR: {e}"
            }

    elif ext in (".png", ".jpg", ".jpeg"):
        if not is_tesseract_available():
            return {
                "status": "warning",
                "extracted_rows": [],
                "raw_text": "",
                "pages_processed": 1,
                "message": "Tesseract OCR engine is not configured. Cannot extract text from image."
            }

        try:
            with Image.open(path) as img:
                ocr_text = ocr_image(img)

            if not ocr_text.strip():
                return {
                    "status": "warning",
                    "extracted_rows": [],
                    "raw_text": "",
                    "pages_processed": 1,
                    "message": "OCR could not read any text from the photograph. Please take a clearer, well-lit photo."
                }

            rows = parse_lab_lines(ocr_text, page_no=1, source_mode="ocr_image")
            return {
                "status": "success" if rows else "warning",
                "extracted_rows": rows,
                "raw_text": ocr_text,
                "pages_processed": 1,
                "message": f"Image OCR completed: {len(rows)} clinical results identified."
            }
        except Exception as e:
            return {
                "status": "error",
                "extracted_rows": [],
                "raw_text": "",
                "pages_processed": 1,
                "message": f"Image OCR error: {e}"
            }
    else:
        return {
            "status": "error",
            "extracted_rows": [],
            "raw_text": "",
            "pages_processed": 0,
            "message": f"Unsupported file extension: {ext}"
        }
