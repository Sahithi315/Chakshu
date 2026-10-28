"""Validate one writer tab exported from Google Sheets as CSV.

Usage:
    python validate_symptom_csv.py path/to/writer_tab.csv --role train
    python validate_symptom_csv.py path/to/private_test.csv --role test

This script checks structure and inline-markup syntax. It does not judge whether
the selected words are clinically or linguistically correct; that remains part
of human annotation review.
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REQUIRED_COLUMNS = ["id", "author", "text_marked", "source"]
MARK_RE = re.compile(r"\[([^\[\]{}]+)\]\{([SNDV])\}")
ANY_TAG_RE = re.compile(r"\{([^{}]+)\}")


CsvRow = Dict[str, Optional[str]]


def cell(row: CsvRow, column: str) -> str:
    """Return a stripped CSV cell, treating missing values as empty strings."""
    return (row.get(column) or "").strip()


def read_rows(path: Path) -> Tuple[List[CsvRow], List[str]]:
    """Read and structurally validate a CSV without leaking parser tracebacks."""
    if path.suffix.lower() != ".csv":
        return [], [f"Expected a .csv file, received: {path.name}"]
    if not path.exists():
        return [], [f"CSV file not found: {path}"]
    if not path.is_file():
        return [], [f"CSV path is not a file: {path}"]

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            fieldnames = reader.fieldnames
            if fieldnames != REQUIRED_COLUMNS:
                return [], [
                    f"Expected columns {REQUIRED_COLUMNS}, found {fieldnames}"
                ]

            rows: List[CsvRow] = []
            for line_number, raw_row in enumerate(reader, start=2):
                if None in raw_row:
                    return [], [
                        f"Row {line_number}: too many values for the four-column header"
                    ]
                rows.append(
                    {column: raw_row.get(column) for column in REQUIRED_COLUMNS}
                )
            return rows, []
    except UnicodeDecodeError:
        return [], [
            "The file is not valid UTF-8 CSV text. Export the worksheet as "
            "CSV UTF-8 and try again."
        ]
    except csv.Error as error:
        return [], [f"Could not parse CSV: {error}"]
    except OSError as error:
        return [], [f"Could not read CSV file: {error}"]


def validate(path: Path, role: str) -> List[str]:
    issues: List[str] = []
    rows, read_issues = read_rows(path)
    if read_issues:
        return read_issues

    expected_rows = 120 if role == "test" else None
    denied_minimum = 50 if role == "test" else 35
    if expected_rows is not None and len(rows) != expected_rows:
        issues.append(f"TEST must contain 120 rows; found {len(rows)}")
    if role == "train" and len(rows) not in (5, 100):
        issues.append(
            "TRAIN tab should contain 5 calibration rows or about 100 final "
            f"rows; found {len(rows)}"
        )

    ids = [cell(row, "id") for row in rows]
    duplicates = [key for key, count in Counter(ids).items() if key and count > 1]
    if duplicates:
        issues.append(f"Duplicate IDs: {', '.join(duplicates[:10])}")

    denied_rows = 0
    for index, row in enumerate(rows, start=2):
        text = cell(row, "text_marked")
        source = cell(row, "source").lower()
        if not cell(row, "id") or not cell(row, "author") or not text:
            issues.append(f"Row {index}: id, author, and text_marked are required")
        if source not in {"human", "llm"}:
            issues.append(f"Row {index}: source must be human or llm")
        if role == "test" and source != "human":
            issues.append(f"Row {index}: TEST content must have source human")

        tags = ANY_TAG_RE.findall(text)
        invalid_tags = sorted(set(tags) - {"S", "N", "D", "V"})
        if invalid_tags:
            issues.append(f"Row {index}: invalid tags {invalid_tags}")

        spans = list(MARK_RE.finditer(text))
        reconstructed = MARK_RE.sub("", text)
        if any(character in reconstructed for character in "[]{}"):
            issues.append(f"Row {index}: malformed or unbalanced inline markup")
        if not spans:
            issues.append(f"Row {index}: no valid labelled spans found")
        for match in spans:
            phrase, tag = match.group(1), match.group(2)
            if not phrase.strip():
                issues.append(f"Row {index}: empty {tag} span")
            negation_pattern = r"(?i)^\s*(no|not|denies|denied|without)\b"
            if tag == "N" and re.match(negation_pattern, phrase):
                issues.append(
                    f"Row {index}: negation word is inside the N span: {phrase!r}"
                )
        if any(match.group(2) == "N" for match in spans):
            denied_rows += 1

    if len(rows) > 5 and denied_rows < denied_minimum:
        issues.append(
            f"Only {denied_rows} rows contain a denied symptom; "
            f"minimum is {denied_minimum}"
        )
    print(f"Rows: {len(rows)}")
    print(f"Rows with denied symptoms: {denied_rows}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--role", choices=["train", "test"], required=True)
    args = parser.parse_args()
    problems = validate(args.csv_path, args.role)
    if problems:
        print("FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

