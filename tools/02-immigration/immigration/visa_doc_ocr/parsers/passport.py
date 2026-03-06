"""Passport MRZ parser with HKSAR / BN(O) / Mainland / foreign passport support."""

from __future__ import annotations

import re
from typing import Any


def _check_digit(data: str) -> int:
    """Compute an MRZ check digit over *data* using 7-3-1 weighting."""
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(data):
        if ch == "<":
            val = 0
        elif ch.isdigit():
            val = int(ch)
        elif ch.isalpha():
            val = ord(ch.upper()) - 55
        else:
            val = 0
        total += val * weights[i % 3]
    return total % 10


def decode_mrz(lines: list[str]) -> dict[str, Any]:
    """Decode a 2-line TD3 (passport) MRZ.

    Line 1: P<ISSUING_STATESURNAME<<GIVEN<NAMES<<<...
    Line 2: DOC_NUMBER<CHECK  NATIONALITY  DOB  CHECK  SEX  EXPIRY  CHECK  ...

    Returns dict with: doc_type_code, issuing_state, surname, given_names,
    doc_number, nationality, date_of_birth, sex, expiry_date, valid_checks.
    """
    result: dict[str, Any] = {
        "doc_type_code": None,
        "issuing_state": None,
        "surname": None,
        "given_names": None,
        "doc_number": None,
        "nationality": None,
        "date_of_birth": None,
        "sex": None,
        "expiry_date": None,
        "valid_checks": {},
    }

    if len(lines) < 2:
        return result

    line1 = lines[0].replace(" ", "").ljust(44, "<")
    line2 = lines[1].replace(" ", "").ljust(44, "<")

    result["doc_type_code"] = line1[0:2].replace("<", "")
    result["issuing_state"] = line1[2:5].replace("<", "")

    name_field = line1[5:44]
    parts = name_field.split("<<", 1)
    result["surname"] = parts[0].replace("<", " ").strip()
    if len(parts) > 1:
        result["given_names"] = parts[1].replace("<", " ").strip()

    doc_num_raw = line2[0:9]
    doc_num_check = line2[9] if len(line2) > 9 else ""
    result["doc_number"] = doc_num_raw.replace("<", "").strip()
    if doc_num_check.isdigit():
        result["valid_checks"]["doc_number"] = _check_digit(doc_num_raw) == int(doc_num_check)

    result["nationality"] = line2[10:13].replace("<", "") if len(line2) > 12 else None

    dob_raw = line2[13:19] if len(line2) > 18 else ""
    dob_check = line2[19] if len(line2) > 19 else ""
    if dob_raw and dob_raw.isdigit():
        result["date_of_birth"] = f"{dob_raw[4:6]}/{dob_raw[2:4]}/{dob_raw[0:2]}"
        if dob_check.isdigit():
            result["valid_checks"]["dob"] = _check_digit(dob_raw) == int(dob_check)

    result["sex"] = line2[20] if len(line2) > 20 else None

    exp_raw = line2[21:27] if len(line2) > 26 else ""
    exp_check = line2[27] if len(line2) > 27 else ""
    if exp_raw and exp_raw.isdigit():
        result["expiry_date"] = f"{exp_raw[4:6]}/{exp_raw[2:4]}/{exp_raw[0:2]}"
        if exp_check.isdigit():
            result["valid_checks"]["expiry"] = _check_digit(exp_raw) == int(exp_check)

    return result


ISSUING_STATE_MAP = {
    "CHN": "Chinese",
    "HKG": "HKSAR",
    "GBR": "British",
    "GBD": "BN(O)",
    "GBN": "BN(O)",
    "TWN": "Taiwanese",
}


def _cross_validate(mrz_data: dict[str, Any], visual_fields: dict[str, Any]) -> list[str]:
    """Cross-validate MRZ-decoded fields against visual-zone OCR text."""
    warnings: list[str] = []
    if mrz_data.get("surname") and visual_fields.get("surname"):
        if mrz_data["surname"].upper() != visual_fields["surname"].upper():
            warnings.append(f"Surname mismatch: MRZ='{mrz_data['surname']}' vs VZ='{visual_fields['surname']}'")
    if mrz_data.get("doc_number") and visual_fields.get("doc_number"):
        if mrz_data["doc_number"] != visual_fields["doc_number"]:
            warnings.append(f"Doc number mismatch: MRZ='{mrz_data['doc_number']}' vs VZ='{visual_fields['doc_number']}'")
    return warnings


def parse_passport(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse passport OCR output, extracting both visual zone and MRZ data.

    Returns dict with: surname, given_names, nationality, doc_number, date_of_birth,
    expiry_date, passport_type, mrz (decoded MRZ dict), warnings, field_confidences.
    """
    lines = ocr_result.get("lines", [])

    result: dict[str, Any] = {
        "surname": None,
        "given_names": None,
        "nationality": None,
        "doc_number": None,
        "date_of_birth": None,
        "expiry_date": None,
        "passport_type": "foreign",
        "mrz": None,
        "warnings": [],
        "field_confidences": {},
    }

    mrz_lines: list[str] = []
    visual_fields: dict[str, Any] = {}

    mrz_pattern = re.compile(r"^[A-Z0-9<]{30,}$")
    doc_num_pattern = re.compile(r"(?:No\.?|Number)\s*:?\s*([A-Z]?\d{7,9})", re.IGNORECASE)
    name_pattern = re.compile(r"(?:Surname|姓)\s*[:/]?\s*([A-Z][A-Za-z\s]+)", re.IGNORECASE)
    given_pattern = re.compile(r"(?:Given\s*names?|名)\s*[:/]?\s*([A-Z][A-Za-z\s]+)", re.IGNORECASE)
    nationality_pattern = re.compile(r"(?:Nationality|國籍)\s*:?\s*([A-Z][A-Za-z]+)", re.IGNORECASE)
    dob_pattern = re.compile(r"(?:birth|出生)\s*:?\s*(\d{1,2}\s*[A-Z]{3}\s*\d{4}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)
    expiry_pattern = re.compile(r"(?:expiry|屆滿)\s*:?\s*(\d{1,2}\s*[A-Z]{3}\s*\d{4}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)

    for line in lines:
        text = line.get("text", "").strip()
        conf = line.get("confidence", 0.0)

        cleaned = text.replace(" ", "")
        if mrz_pattern.match(cleaned) and len(cleaned) >= 36:
            mrz_lines.append(cleaned)
            continue

        m = name_pattern.search(text)
        if m and not result["surname"]:
            result["surname"] = m.group(1).strip()
            visual_fields["surname"] = result["surname"]
            result["field_confidences"]["surname"] = conf

        m = given_pattern.search(text)
        if m and not result["given_names"]:
            result["given_names"] = m.group(1).strip()
            result["field_confidences"]["given_names"] = conf

        m = nationality_pattern.search(text)
        if m and not result["nationality"]:
            result["nationality"] = m.group(1).strip()
            result["field_confidences"]["nationality"] = conf

        m = doc_num_pattern.search(text)
        if m and not result["doc_number"]:
            result["doc_number"] = m.group(1).strip()
            visual_fields["doc_number"] = result["doc_number"]
            result["field_confidences"]["doc_number"] = conf

        m = dob_pattern.search(text)
        if m and not result["date_of_birth"]:
            result["date_of_birth"] = m.group(1).strip()
            result["field_confidences"]["date_of_birth"] = conf

        m = expiry_pattern.search(text)
        if m and not result["expiry_date"]:
            result["expiry_date"] = m.group(1).strip()
            result["field_confidences"]["expiry_date"] = conf

        text_upper = text.upper()
        if "HKSAR" in text_upper or "HONG KONG SPECIAL" in text_upper:
            result["passport_type"] = "HKSAR"
        elif "BN(O)" in text_upper or "BRITISH NATIONAL (OVERSEAS)" in text_upper:
            result["passport_type"] = "BN(O)"
        elif "TRAVEL PERMIT" in text_upper or "往來港澳通行證" in text:
            result["passport_type"] = "mainland_travel_permit"

    if len(mrz_lines) >= 2:
        mrz_data = decode_mrz(mrz_lines[-2:])
        result["mrz"] = mrz_data

        if not result["surname"] and mrz_data.get("surname"):
            result["surname"] = mrz_data["surname"]
        if not result["given_names"] and mrz_data.get("given_names"):
            result["given_names"] = mrz_data["given_names"]
        if not result["doc_number"] and mrz_data.get("doc_number"):
            result["doc_number"] = mrz_data["doc_number"]
        if not result["nationality"] and mrz_data.get("nationality"):
            result["nationality"] = ISSUING_STATE_MAP.get(mrz_data["nationality"], mrz_data["nationality"])

        result["warnings"] = _cross_validate(mrz_data, visual_fields)

    return result
