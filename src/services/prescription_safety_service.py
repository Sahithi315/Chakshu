"""Transparent, non-autonomous prescription completeness and safety checks."""
import re

RULESET_VERSION = "demo-2026-10-29"

INTERACTION_RULES = [
    ({"warfarin"}, {"aspirin"}, "Documented combination may increase bleeding risk."),
    ({"sildenafil", "tadalafil"}, {"nitroglycerin", "isosorbide"}, "PDE-5 inhibitor and nitrate combination may cause severe hypotension."),
    ({"spironolactone"}, {"potassium"}, "Combination may increase the risk of hyperkalaemia."),
    ({"methotrexate"}, {"trimethoprim", "cotrimoxazole"}, "Combination may increase antifolate toxicity.")
]

ALLERGY_ALIASES = {
    "penicillin": {"penicillin", "amoxicillin", "ampicillin"},
    "sulfa": {"sulfamethoxazole", "cotrimoxazole"},
    "aspirin": {"aspirin"}
}


def _tokens(value):
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _normalized_name(value):
    ignored = {"tablet", "tablets", "tab", "capsule", "capsules", "cap", "syrup", "injection", "mg", "ml", "mcg"}
    return " ".join(token for token in re.findall(r"[a-z]+", str(value or "").lower()) if token not in ignored)


def check_prescription_safety(medications, allergies=""):
    medicines = medications if isinstance(medications, list) else []
    issues = []
    normalized = []

    for index, medicine in enumerate(medicines):
        name = str(medicine.get("name") or "").strip()
        if not name and not any(str(value or "").strip() for value in medicine.values()):
            continue
        normalized_name = _normalized_name(name)
        normalized.append((index, normalized_name, _tokens(name)))
        missing = [field for field in ("name", "strength", "dose", "frequency", "duration") if not str(medicine.get(field) or "").strip()]
        if missing:
            issues.append({
                "id": f"incomplete-{index}", "type": "incomplete", "severity": "needs_input",
                "title": f"Incomplete instructions for {name or f'medicine {index + 1}'}",
                "message": f"Add: {', '.join(missing)}.", "medication_indexes": [index]
            })

    seen = {}
    for index, name, _ in normalized:
        if not name:
            continue
        if name in seen:
            issues.append({
                "id": f"duplicate-{seen[name]}-{index}", "type": "duplicate", "severity": "review",
                "title": "Possible duplicate medicine", "message": f"{name.title()} appears more than once.",
                "medication_indexes": [seen[name], index]
            })
        else:
            seen[name] = index

    allergy_text = str(allergies or "").lower()
    if allergy_text and not any(marker in allergy_text for marker in ("no known", "none", "not recorded", "unknown")):
        allergy_terms = _tokens(allergy_text)
        for index, name, medicine_terms in normalized:
            matched = set()
            for allergy, aliases in ALLERGY_ALIASES.items():
                if allergy in allergy_terms and aliases & medicine_terms:
                    matched.add(allergy)
            matched.update(allergy_terms & medicine_terms)
            if matched:
                issues.append({
                    "id": f"allergy-{index}", "type": "allergy", "severity": "high",
                    "title": "Allergy match requires review",
                    "message": f"{name.title()} matches recorded allergy text: {', '.join(sorted(matched))}.",
                    "medication_indexes": [index]
                })

    for left, right, message in INTERACTION_RULES:
        left_matches = [(i, name) for i, name, terms in normalized if left & terms]
        right_matches = [(i, name) for i, name, terms in normalized if right & terms]
        for left_item in left_matches:
            for right_item in right_matches:
                if left_item[0] == right_item[0]:
                    continue
                issues.append({
                    "id": f"interaction-{left_item[0]}-{right_item[0]}", "type": "interaction", "severity": "high",
                    "title": "Documented interaction requires review",
                    "message": f"{left_item[1].title()} + {right_item[1].title()}: {message}",
                    "medication_indexes": [left_item[0], right_item[0]]
                })

    return {
        "status": "review_required" if issues else "no_issues_found",
        "issues": issues,
        "checked_medications": len(normalized),
        "ruleset_version": RULESET_VERSION,
        "coverage_note": "Limited decision support only. A result with no issues is not proof that the prescription is safe."
    }
