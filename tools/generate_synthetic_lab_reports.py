from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

OUT = Path(r"C:\Users\Dell\Desktop\ELLL\Team_404-Vision\output\pdf")
OUT.mkdir(parents=True, exist_ok=True)

REPORTS = [
    {
        "file": "synthetic_cbc_report.pdf", "id": "SYN-CBC-001", "patient": "Kiran Vale", "age": "34 years", "sex": "Female", "title": "Complete Blood Count", "layout": "classic",
        "tests": [("Haemoglobin", "10.8", "g/dL", "12.0-15.0"), ("WBC count", "13200", "/uL", "4000-11000"), ("Platelet count", "245000", "/uL", "150000-450000"), ("RBC count", "3.9", "million/uL", "4.2-5.4"), ("MCV", "78", "fL", "80-100"), ("Neutrophils", "78", "%", "40-75")]
    },
    {
        "file": "synthetic_metabolic_report.pdf", "id": "SYN-MET-002", "patient": "Mira Solan", "age": "46 years", "sex": "Female", "title": "Basic Metabolic Panel", "layout": "grid",
        "tests": [("Fasting glucose", "146", "mg/dL", "70-99"), ("Creatinine", "1.3", "mg/dL", "0.6-1.2"), ("Urea", "42", "mg/dL", "15-40"), ("Sodium", "133", "mmol/L", "135-145"), ("Potassium", "4.7", "mmol/L", "3.5-5.1"), ("Calcium", "8.7", "mg/dL", "8.5-10.5"), ("Chloride", "101", "mmol/L", "98-107")]
    },
    {
        "file": "synthetic_diabetes_lipid_report.pdf", "id": "SYN-DIA-003", "patient": "Dev Arin", "age": "52 years", "sex": "Male", "title": "Diabetes and Lipid Review", "layout": "cards",
        "tests": [("HbA1c", "8.4", "%", "4.0-5.6"), ("Estimated average glucose", "194", "mg/dL", "68-114"), ("Total cholesterol", "228", "mg/dL", "<200"), ("LDL cholesterol", "146", "mg/dL", "<100"), ("HDL cholesterol", "38", "mg/dL", ">=40"), ("Triglycerides", "220", "mg/dL", "<150")]
    },
    {
        "file": "synthetic_thyroid_report.pdf", "id": "SYN-THY-004", "patient": "Tara Nivan", "age": "29 years", "sex": "Female", "title": "Thyroid Profile", "layout": "classic",
        "tests": [("TSH", "7.8", "uIU/mL", "0.4-4.5"), ("Free T4", "0.7", "ng/dL", "0.8-1.8"), ("Free T3", "2.4", "pg/mL", "2.3-4.2"), ("Anti-TPO", "85", "IU/mL", "<35")]
    },
    {
        "file": "synthetic_liver_report.pdf", "id": "SYN-LFT-005", "patient": "Rhea Kaal", "age": "41 years", "sex": "Female", "title": "Liver Function Panel", "layout": "two_column",
        "tests": [("Total bilirubin", "1.6", "mg/dL", "0.3-1.2"), ("Direct bilirubin", "0.5", "mg/dL", "<0.3"), ("AST", "58", "U/L", "10-40"), ("ALT", "72", "U/L", "7-56"), ("Alkaline phosphatase", "138", "U/L", "44-147"), ("Albumin", "3.4", "g/dL", "3.5-5.0")]
    },
    {
        "file": "synthetic_renal_report.pdf", "id": "SYN-REN-006", "patient": "Aman Vero", "age": "63 years", "sex": "Male", "title": "Renal and Electrolyte Panel", "layout": "grid",
        "tests": [("Creatinine", "2.1", "mg/dL", "0.6-1.2"), ("eGFR", "38", "mL/min/1.73m2", ">=60"), ("Urea", "64", "mg/dL", "15-40"), ("Sodium", "139", "mmol/L", "135-145"), ("Potassium", "5.4", "mmol/L", "3.5-5.1"), ("Urine albumin-creatinine ratio", "110", "mg/g", "<30"), ("Bicarbonate", "21", "mmol/L", "22-29")]
    },
]

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#284B45"), alignment=TA_LEFT, spaceAfter=8))
styles.add(ParagraphStyle(name="Synthetic", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#9A3412"), alignment=TA_CENTER, leading=13))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#4B5563")))
styles.add(ParagraphStyle(name="CardValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#284B45")))
styles.add(ParagraphStyle(name="CardLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=TA_CENTER))

def patient_block(r):
    data = [
        [Paragraph(f"<b>Patient</b><br/>{r['patient']}", styles["Small"]), Paragraph(f"<b>Age / Sex</b><br/>{r['age']} / {r['sex']}", styles["Small"]), Paragraph(f"<b>Report ID</b><br/>{r['id']}", styles["Small"])],
        [Paragraph("<b>Collected</b><br/>27 October 2026, 08:30", styles["Small"]), Paragraph("<b>Reported</b><br/>27 October 2026, 14:10", styles["Small"]), Paragraph("<b>Specimen</b><br/>Synthetic digital record", styles["Small"])],
    ]
    t = Table(data, colWidths=[58*mm, 58*mm, 58*mm], rowHeights=[15*mm, 15*mm])
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F7F1E6")), ("BOX", (0,0), (-1,-1), 0.7, colors.HexColor("#D8CDBB")), ("INNERGRID", (0,0), (-1,-1), 0.35, colors.HexColor("#E6DED1")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 8)]))
    return t

def result_table(r, accent):
    rows = [["Test", "Result", "Unit", "Reference range"]] + [list(x) for x in r["tests"]]
    t = Table(rows, colWidths=[68*mm, 30*mm, 38*mm, 42*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), accent), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 9), ("LEADING", (0,0), (-1,-1), 12),
        ("ALIGN", (1,1), (1,-1), "RIGHT"), ("ALIGN", (2,1), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAF7F1")]), ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    return t

def result_cards(r):
    cards = []
    for name, value, unit, ref in r["tests"]:
        card = Table([[Paragraph(name, styles["CardLabel"])], [Paragraph(f"{value} <font size=8>{unit}</font>", styles["CardValue"])], [Paragraph(f"Reference: {ref}", styles["Small"]) ]], colWidths=[56*mm], rowHeights=[11*mm, 14*mm, 10*mm])
        card.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FFFDF8")), ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#B7C9C4")), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        cards.append(card)
    rows = [cards[i:i+3] for i in range(0, len(cards), 3)]
    while len(rows[-1]) < 3:
        rows[-1].append(Spacer(56*mm, 1))
    outer = Table(rows, colWidths=[59*mm]*3, hAlign="LEFT")
    outer.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 1.5*mm), ("RIGHTPADDING", (0,0), (-1,-1), 1.5*mm), ("TOPPADDING", (0,0), (-1,-1), 2*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2*mm)]))
    return outer

def two_column(r):
    mid = (len(r["tests"]) + 1) // 2
    blocks = []
    for subset in (r["tests"][:mid], r["tests"][mid:]):
        rows = [["Test", "Result", "Range"]] + [[a, f"{b} {c}", d] for a,b,c,d in subset]
        t = Table(rows, colWidths=[45*mm, 28*mm, 27*mm])
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#6B4F3B")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTNAME", (0,1), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 8.5), ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8CDBB")), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
        blocks.append(t)
    outer = Table([[blocks[0], blocks[1]]], colWidths=[89*mm, 89*mm])
    outer.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm)]))
    return outer

def build_report(r):
    path = OUT / r["file"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm, title=r["title"], author="Synthetic dataset generator")
    story = [Paragraph("SYNTHETIC LABORATORY REPORT - NOT FOR CLINICAL USE", styles["Synthetic"]), Spacer(1, 4*mm), Paragraph("Nivara Diagnostic Centre", styles["ReportTitle"]), Paragraph("Training artifact containing invented identities and values", styles["Small"]), Spacer(1, 5*mm), patient_block(r), Spacer(1, 6*mm), Paragraph(r["title"], styles["Heading2"]), Spacer(1, 2*mm)]
    if r["layout"] == "cards":
        story.append(result_cards(r))
    elif r["layout"] == "two_column":
        story.append(two_column(r))
    else:
        accent = colors.HexColor("#284B45") if r["layout"] == "classic" else colors.HexColor("#355C7D")
        story.append(result_table(r, accent))
    story += [Spacer(1, 8*mm), Paragraph("This document is entirely synthetic. It is designed only for software development, extraction testing and demonstration. It is not a medical report and must not be used for diagnosis or treatment.", styles["Small"]), Spacer(1, 4*mm), Paragraph("Digitally generated PDF. No scan or patient photograph is included.", styles["Small"])]
    doc.build(story)
    return path

for report in REPORTS:
    print(build_report(report))

