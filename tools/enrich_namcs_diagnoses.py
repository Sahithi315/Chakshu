"""Add ICD-10-CM titles and plain-language explanations to the 2024 NAMCS Stata public-use data."""

import argparse
from collections import Counter
import gzip
import io
import re
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {
    2024: (
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2024-Update/"
        "icd10cm-Codes-Descriptions-April-2024.zip",
        "icd10cm-order-April-2024.txt",
    ),
    2025: (
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2025/"
        "ICD10-CM%20Code%20Descriptions%202025.zip",
        "icd10cm-order-2025.txt",
    ),
}
DIAGNOSIS_COLUMNS = [f"DX{slot}" for slot in range(1, 31)]


# Explain the recorded wording only. Keep qualifiers and avoid inferring
# specific findings from a broad code or an encounter-for-screening code.
PLAIN_LANGUAGE = {
    "Tinea unguium": "Fungal infection of a fingernail or toenail.",
    "Tinea pedis": "Athlete's foot, a fungal infection of the skin of the foot.",
    "Tinea corporis": "Ringworm, a fungal infection of the skin on the body.",
    "Essential (primary) hypertension": "High blood pressure with no identified secondary cause.",
    "Mixed hyperlipidemia": "More than one type of blood fat, such as cholesterol and triglycerides, is high.",
    "Hyperlipidemia, unspecified": "High levels of fats in the blood. The specific type is not recorded.",
    "Hypothyroidism, unspecified": "An underactive thyroid. The specific type is not recorded.",
    "Elevated blood-pressure reading, without diagnosis of hypertension":
        "A high blood pressure reading was recorded without a diagnosis of high blood pressure.",
    "Dietary counseling and surveillance": "Advice about eating habits and follow-up on diet.",
    "Occlusion and stenosis of carotid artery": "Narrowing or blockage of an artery in the neck that supplies the brain.",
    "Onychogryphosis": "An unusually thick, curved nail.",
    "Cervicalgia": "Neck pain.",
    "Cervical disc disorder, unspecified": "A problem with a disc in the neck. The specific type is not recorded.",
    "Trigger finger": "A finger or thumb that catches or locks when bent or straightened.",
    "Allergy status to sulfonamides": "A sulfonamide (sulfa drug) allergy is recorded.",
    "Dental caries, unspecified": "Tooth decay, also called cavities. The specific type is not recorded.",
    "Abnormal glucose": "A blood sugar finding outside the expected range.",
    "Nicotine dependence": "Dependence on nicotine.",
    "Insomnia": "Difficulty falling asleep, staying asleep, or getting enough quality sleep.",
    "Sleep apnea": "Breathing repeatedly stops or becomes shallow during sleep.",
    "Constipation": "Bowel movements that are difficult, infrequent, or both.",
    "Pain in joint": "Pain in one or more joints.",
    "Pain in limb, hand, foot, fingers and toes": "Pain in an arm, leg, hand, foot, finger, or toe.",
    "Other malaise and fatigue": "Feeling unwell or unusually tired.",
    "Chronic pain, not elsewhere classified": "Ongoing pain recorded under a general chronic pain code.",
    "Encounter for immunization": "A visit for vaccination.",
    "Encounter for general adult medical examination": "A routine adult health check.",
    "Encounter for newborn, infant and child health examinations": "A routine health check for a newborn, infant, or child.",
    "Encounter for dental examination and cleaning": "A visit for a dental checkup and cleaning.",
    "Generalized anxiety disorder": "Persistent, excessive worry about everyday situations.",
    "Post-traumatic stress disorder (PTSD)": "A mental health condition that can follow a traumatic experience.",
    "Other injury of unspecified body region": "An injury was recorded without a specific body location.",
    "Other specified personal risk factors, not elsewhere classified":
        "A personal health risk factor was recorded under a general risk-factor code.",
    "Urinary tract infection, site not specified": "An infection in the urinary system. The exact location is not recorded.",
    "Acute upper respiratory infection, unspecified":
        "A short-term infection of the nose, throat, or upper airways. The specific type is not recorded.",
    "Acute pharyngitis, unspecified": "A sore, inflamed throat that started recently. The cause is not recorded in this code.",
    "Iron deficiency anemia, unspecified": "Anemia caused by too little iron. The specific type is not recorded.",
    "Mild intermittent asthma": "Mild asthma with symptoms that occur from time to time.",
    "Body mass index [BMI]": "Body mass index (BMI), a number based on height and weight.",
    "Body mass index [BMI] 40 or greater, adult": "An adult body mass index (BMI) of 40 or higher.",
    "Body mass index [BMI] 30-39, adult": "An adult body mass index (BMI) in the 30 to 39 range.",
    "Body mass index [BMI] 20-29, adult": "An adult body mass index (BMI) in the 20 to 29 range.",
    "Body mass index [BMI] pediatric": "Body mass index (BMI) for a child or adolescent.",
    "Chronic kidney disease, stage 3 (moderate)": "Long-term kidney disease with moderately reduced kidney function.",
    "Dysuria": "Pain or discomfort when urinating.",
    "Other microscopic hematuria": "Blood in the urine detected by testing, without visible blood.",
    "Contusion of toe without damage to nail": "A bruised toe with no damage to the toenail.",
    "Encounter for screening for malignant neoplasm of breast": "A visit to screen for breast cancer.",
    "Encounter for screening for malignant neoplasm of intestinal tract": "A visit to screen for cancer of the intestinal tract.",
    "Encounter for screening examination for mental health and behavioral disorders":
        "A visit to screen for mental health or behavioral conditions.",
    "Encounter for screening, unspecified": "A screening visit. The type of screening is not recorded.",
    "Cramp and spasm": "An involuntary tightening or contraction of a muscle.",
}
PLAIN_TERMS = {
    "type 2 diabetes mellitus": "type 2 diabetes",
    "ophthalmic complications": "eye complications",
    "neurological complications": "nerve or nervous system complications",
    "gastro-esophageal reflux disease": "acid reflux disease",
    "esophagitis": "inflammation of the tube that carries food to the stomach",
    "allergic rhinitis": "nasal allergy symptoms",
    "acute sinusitis": "short-term sinus inflammation",
    "chronic obstructive pulmonary disease": "chronic obstructive lung disease (COPD)",
    "hypertension": "high blood pressure",
    "hypercholesterolemia": "high cholesterol",
    "hypothyroidism": "underactive thyroid",
    "dysuria": "pain or discomfort when urinating",
    "hematuria": "blood in the urine",
    "dyspnea": "shortness of breath",
    "dysphagia": "difficulty swallowing",
    "edema": "swelling from fluid buildup",
    "contusion": "bruise",
    "malignant neoplasm": "cancer",
    "encounter for screening for": "visit to screen for",
}
TERM_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in PLAIN_TERMS) + r")(?!\w)", re.IGNORECASE
)


def explain_title(title):
    label, category, _ = title.partition(" [broader category]")
    explanation = PLAIN_LANGUAGE.get(label)
    if explanation is None:
        rewritten = TERM_PATTERN.sub(lambda term: PLAIN_TERMS[term.group().lower()], label)
        if rewritten == label:
            return None
        explanation = rewritten[0].upper() + rewritten[1:] + "."
    if category:
        return f"Broader category only. {explanation}"
    return explanation


def load_titles(year, local_archive=None):
    url, member = REFERENCES[year]
    if local_archive:
        zip_contents = local_archive.read_bytes()
    else:
        with urlopen(url, timeout=30) as response:
            zip_contents = response.read()
    titles = {}
    with ZipFile(io.BytesIO(zip_contents)) as archive, archive.open(member) as order_file:
        for line in order_file:
            code = line[6:13].decode("ascii").strip()
            if len(code) in (3, 4):
                titles[code] = line[77:].decode("utf-8").strip()
    return titles


def enrich_dataset(source, output, titles_2024, titles_2025):
    if output.resolve() == source.resolve():
        raise ValueError("Choose an output path separate from the original Stata file")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".tmp")
    unmapped = Counter()
    encounters = mapped_count = category_count = explanation_count = 0
    titles_2024 = pd.Series(titles_2024)
    titles_2025 = pd.Series(titles_2025)
    categories_2024 = titles_2024[titles_2024.index.str.len() == 3] + " [broader category]"
    categories_2025 = titles_2025[titles_2025.index.str.len() == 3] + " [broader category]"

    unique_titles = set(pd.concat([titles_2024, titles_2025, categories_2024, categories_2025]))
    explanations = {title: explain_title(title) for title in unique_titles}
    explanations = pd.Series({title: text for title, text in explanations.items() if text is not None})

    try:
        with pd.read_stata(source, chunksize=20_000, convert_categoricals=False) as reader:
            with gzip.open(partial, "wt", encoding="utf-8", newline="", compresslevel=3) as stream:
                for chunk in reader:
                    labels = {}
                    late_year = chunk["MONTH"].between(10, 12)
                    for field in DIAGNOSIS_COLUMNS:
                        codes = chunk[field].astype("string").str.strip().str.upper()
                        present = codes.notna() & ~codes.isin(["", "-9"])
                        titles = codes.map(titles_2024)
                        titles.loc[late_year] = codes.loc[late_year].map(titles_2025)
                        mapped_count += int((present & titles.notna()).sum())
                        needs_category = present & titles.isna() & codes.str.len().eq(4)
                        category_codes = codes.loc[needs_category].str[:3]
                        category_titles = category_codes.map(categories_2024)
                        late_categories = late_year.loc[needs_category]
                        category_titles.loc[late_categories] = category_codes.loc[late_categories].map(categories_2025)
                        category_count += int(category_titles.notna().sum())
                        titles.loc[needs_category] = category_titles
                        unmapped.update(codes[present & titles.isna()].tolist())
                        labels[f"{field}_LABEL"] = titles.where(present).mask(
                            present & titles.isna(), "Unmapped ICD-10-CM code"
                        )
                        plain_text = labels[f"{field}_LABEL"].map(explanations)
                        labels[f"{field}_EXPLANATION"] = plain_text
                        explanation_count += int(plain_text.notna().sum())
                    pd.concat([chunk, pd.DataFrame(labels, index=chunk.index)], axis=1).to_csv(
                        stream, index=False, header=encounters == 0
                    )
                    encounters += len(chunk)
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)

    print(f"Visits: {encounters:,}")
    print(f"Direct title matches: {mapped_count:,}")
    print(f"Broader category matches: {category_count:,}")
    print(f"Diagnosis entries with plain-language explanations: {explanation_count:,}")
    print(f"Unmapped diagnosis entries: {sum(unmapped.values()):,} across {len(unmapped):,} codes")
    for code, count in unmapped.most_common(20):
        print(f"  {code}: {count:,}")
    print(output.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "namcshc2024_stata.dta")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "namcshc2024_with_diagnosis_explanations.csv.gz")
    parser.add_argument("--fy2024-archive", type=Path)
    parser.add_argument("--fy2025-archive", type=Path)
    args = parser.parse_args()
    enrich_dataset(
        args.source, args.output,
        load_titles(2024, args.fy2024_archive), load_titles(2025, args.fy2025_archive),
    )


if __name__ == "__main__":
    main()
