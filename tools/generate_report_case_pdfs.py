from __future__ import annotations

import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(r"C:\Users\Dell\Desktop\ELLL\Team_404-Vision")
OUT = ROOT / "output" / "pdf" / "report_case_dataset"
OUT.mkdir(parents=True, exist_ok=True)
TRUTH = ROOT / "tmp" / "report_case_dataset_truth.json"
TRUTH.parent.mkdir(parents=True, exist_ok=True)

PANELS = [
    ("Complete Blood Count", [
        ("Haemoglobin", "g/dL", 12.0, 15.0, 13.5), ("WBC count", "/uL", 4000, 11000, 7500),
        ("Platelet count", "/uL", 150000, 450000, 280000), ("RBC count", "million/uL", 4.2, 5.4, 4.8),
        ("MCV", "fL", 80, 100, 90), ("Neutrophils", "%", 40, 75, 58)]),
    ("Diabetes and Lipid Panel", [
        ("HbA1c", "%", 4.0, 5.6, 5.1), ("Fasting glucose", "mg/dL", 70, 99, 86),
        ("Total cholesterol", "mg/dL", 120, 199, 165), ("LDL cholesterol", "mg/dL", 50, 99, 82),
        ("HDL cholesterol", "mg/dL", 40, 80, 52), ("Triglycerides", "mg/dL", 50, 149, 105)]),
    ("Renal Function Panel", [
        ("Creatinine", "mg/dL", 0.6, 1.2, 0.9), ("Urea", "mg/dL", 15, 40, 26),
        ("Sodium", "mmol/L", 135, 145, 139), ("Potassium", "mmol/L", 3.5, 5.1, 4.2),
        ("Bicarbonate", "mmol/L", 22, 29, 25), ("eGFR", "mL/min/1.73m2", 60, 120, 92)]),
    ("Liver Function Panel", [
        ("Total bilirubin", "mg/dL", 0.3, 1.2, 0.7), ("Direct bilirubin", "mg/dL", 0.0, 0.3, 0.1),
        ("AST", "U/L", 10, 40, 24), ("ALT", "U/L", 7, 56, 28),
        ("Alkaline phosphatase", "U/L", 44, 147, 92), ("Albumin", "g/dL", 3.5, 5.0, 4.2)]),
    ("Thyroid Profile", [
        ("TSH", "uIU/mL", 0.4, 4.5, 2.1), ("Free T4", "ng/dL", 0.8, 1.8, 1.2),
        ("Free T3", "pg/mL", 2.3, 4.2, 3.1), ("Anti-TPO", "IU/mL", 0, 35, 12),
        ("Total T4", "ug/dL", 5.0, 12.0, 8.4), ("Total T3", "ng/dL", 80, 200, 132)]),
    ("Basic Metabolic Panel", [
        ("Random glucose", "mg/dL", 70, 140, 104), ("Calcium", "mg/dL", 8.5, 10.5, 9.3),
        ("Sodium", "mmol/L", 135, 145, 139), ("Potassium", "mmol/L", 3.5, 5.1, 4.1),
        ("Chloride", "mmol/L", 98, 107, 102), ("Creatinine", "mg/dL", 0.6, 1.2, 0.9)]),
    ("Iron and Vitamin Panel", [
        ("Ferritin", "ng/mL", 20, 250, 90), ("Serum iron", "ug/dL", 60, 170, 105),
        ("TIBC", "ug/dL", 240, 450, 330), ("Vitamin B12", "pg/mL", 200, 900, 430),
        ("Vitamin D", "ng/mL", 20, 50, 31), ("Folate", "ng/mL", 3.0, 17.0, 8.2)]),
    ("Inflammation Panel", [
        ("CRP", "mg/L", 0, 10, 3.0), ("ESR", "mm/hr", 0, 20, 9),
        ("Procalcitonin", "ng/mL", 0, 0.5, 0.12), ("WBC count", "/uL", 4000, 11000, 7200),
        ("Neutrophils", "%", 40, 75, 56), ("Lymphocytes", "%", 20, 45, 34)]),
]

PATIENTS = [
    "Ari Vellan", "Mira Tovan", "Dev Niral", "Tara Solen", "Rhea Kivan", "Aman Varel",
    "Nila Oran", "Kabir Selan", "Ira Vedin", "Rohan Teral", "Sana Miro", "Neil Aven",
    "Diya Loren", "Arun Veyan", "Meera Kalen", "Vivaan Rilo", "Kavya Nerin", "Rehan Soval",
    "Anya Darel", "Vihaan Meren", "Sara Vilon", "Naman Erel", "Riya Toran", "Arav Silen",
]

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Synthetic", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#9A3412"), alignment=TA_CENTER, leading=13))
styles.add(ParagraphStyle(name="SmallGray", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#4B5563")))
styles.add(ParagraphStyle(name="CardValue2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=17, alignment=TA_CENTER, textColor=colors.HexColor("#284B45")))
styles.add(ParagraphStyle(name="CardLabel2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, alignment=TA_CENTER))

def rounded(value: float, unit: str):
    if unit in {"/uL", "pg/mL", "ug/dL", "mm/hr", "U/L", "%", "mL/min/1.73m2"} and abs(value) >= 10:
        return int(round(value))
    return round(value, 2 if abs(value) < 1 else 1)

def generate_results(panel, report_index):
    title, tests = panel
    patient_slot = report_index % 8
    visit = report_index // 8
    pattern = (patient_slot + visit) % 4
    rows = []
    for j, (name, unit, low, high, base) in enumerate(tests):
        value = base
        if pattern == 1 and j in (0, 3):
            value = high + (high - low) * (0.18 + 0.03 * (report_index % 3))
        elif pattern == 2 and j in (1, 4):
            value = low - (high - low) * (0.12 + 0.02 * (report_index % 4))
        elif pattern == 3:
            if j in (0, 2): value = high + (high - low) * 0.28
            if j in (1, 5): value = low - (high - low) * 0.18
        value = rounded(value, unit)
        flag = "LOW" if value < low else "HIGH" if value > high else "IN_RANGE"
        rows.append({"test_id": f"T{j+1:02d}", "test": name, "value": value, "unit": unit, "range_low": low, "range_high": high, "reference_range": f"{low:g}-{high:g}", "flag": flag})
    return rows

def patient_table(report):
    data = [
        [Paragraph(f"<b>Patient</b><br/>{report['patient']}", styles["SmallGray"]), Paragraph(f"<b>Age / Sex</b><br/>{report['age']} / {report['sex']}", styles["SmallGray"]), Paragraph(f"<b>Report ID</b><br/>{report['report_id']}", styles["SmallGray"])],
        [Paragraph(f"<b>Collected</b><br/>{report['collected']}", styles["SmallGray"]), Paragraph(f"<b>Reported</b><br/>{report['reported']}", styles["SmallGray"]), Paragraph("<b>Specimen</b><br/>Synthetic digital record", styles["SmallGray"])],
    ]
    t = Table(data, colWidths=[58*mm, 58*mm, 58*mm], rowHeights=[15*mm, 15*mm])
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F7F1E6")), ("BOX", (0,0), (-1,-1), 0.7, colors.HexColor("#D8CDBB")), ("INNERGRID", (0,0), (-1,-1), 0.35, colors.HexColor("#E6DED1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 8)]))
    return t

def standard_table(results, color):
    rows = [["Test", "Result", "Unit", "Reference range", "Flag"]] + [[x["test"], str(x["value"]), x["unit"], x["reference_range"], x["flag"]] for x in results]
    t = Table(rows, colWidths=[59*mm, 25*mm, 35*mm, 36*mm, 24*mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), color), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTNAME", (0,1), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 8.5), ("ALIGN", (1,1), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAF7F1")]), ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D1D5DB")), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    return t

def card_table(results):
    cards = []
    for x in results:
        card = Table([[Paragraph(x["test"], styles["CardLabel2"])], [Paragraph(f"{x['value']} <font size=7>{x['unit']}</font>", styles["CardValue2"])], [Paragraph(f"Range {x['reference_range']} | {x['flag']}", styles["SmallGray"])]], colWidths=[56*mm], rowHeights=[10*mm, 13*mm, 10*mm])
        card.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FFFDF8")), ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#B7C9C4")), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        cards.append(card)
    return Table([cards[:3], cards[3:6]], colWidths=[59*mm]*3, style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 1.5*mm), ("RIGHTPADDING", (0,0), (-1,-1), 1.5*mm), ("TOPPADDING", (0,0), (-1,-1), 2*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2*mm)]))

def two_column(results):
    blocks = []
    for subset in (results[:3], results[3:6]):
        rows = [["Test", "Result", "Range"]] + [[x["test"], f"{x['value']} {x['unit']}", x["reference_range"]] for x in subset]
        t = Table(rows, colWidths=[45*mm, 30*mm, 27*mm])
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#6B4F3B")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTNAME", (0,1), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 8), ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8CDBB")), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
        blocks.append(t)
    return Table([[blocks[0], blocks[1]]], colWidths=[89*mm, 89*mm], style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm)]))

def build_pdf(report):
    path = OUT / report["file"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm, title=report["panel"], author="Synthetic dataset generator")
    story = [Paragraph("SYNTHETIC LABORATORY REPORT - NOT FOR CLINICAL USE", styles["Synthetic"]), Spacer(1, 4*mm), Paragraph(report["facility"], styles["Heading1"]), Paragraph("Invented identity and values for document-extraction testing", styles["SmallGray"]), Spacer(1, 5*mm), patient_table(report), Spacer(1, 6*mm), Paragraph(report["panel"], styles["Heading2"]), Spacer(1, 2*mm)]
    if report["layout"] == "cards": story.append(card_table(report["results"]))
    elif report["layout"] == "two_column": story.append(two_column(report["results"]))
    else: story.append(standard_table(report["results"], colors.HexColor("#284B45") if report["layout"] == "classic" else colors.HexColor("#355C7D")))
    story += [Spacer(1, 8*mm), Paragraph("Entirely synthetic. Use only for software development and evaluation. Do not use for diagnosis or treatment.", styles["SmallGray"]), Paragraph("Digitally generated PDF; not a photograph or scan.", styles["SmallGray"])]
    doc.build(story)

reports = []
layouts = ["classic", "compact", "cards", "two_column"]
facilities = ["Nivara Diagnostic Centre", "Aster Vale Laboratory", "Meridian Path Services", "Sanjeevani Test Centre"]
for i in range(24):
    patient_slot = i % 8
    visit = i // 8
    panel = PANELS[patient_slot]
    report = {
        "report_id": f"SYN-RPT-{i+1:03d}", "file": f"synthetic_report_{i+1:03d}.pdf", "patient": PATIENTS[patient_slot],
        "patient_id": f"SYN-P-{patient_slot+1:03d}", "age": f"{22 + (patient_slot*7)%52} years", "sex": "Female" if patient_slot % 2 == 0 else "Male",
        "collected": f"{3 + visit*8 + patient_slot:02d} October 2026, 08:{10 + patient_slot:02d}", "reported": f"{3 + visit*8 + patient_slot:02d} October 2026, 14:{5 + patient_slot:02d}",
        "facility": facilities[patient_slot % len(facilities)], "panel": panel[0], "layout": layouts[(patient_slot + visit) % len(layouts)],
        "results": generate_results(panel, i), "source": "llm", "review_status": "synthetic_extraction_truth"
    }
    build_pdf(report)
    reports.append(report)

TRUTH.write_text(json.dumps({"reports": reports}, indent=2), encoding="utf-8")
print(json.dumps({"pdf_count": len(reports), "result_rows": sum(len(r["results"]) for r in reports), "truth": str(TRUTH), "output": str(OUT)}, indent=2))

