"""Tests for SOAP generator and ICD-10 coding."""

from medical_dental.scribe_ai.structuring.soap_generator import SoapGenerator
from medical_dental.scribe_ai.structuring.icd_coder import IcdCoder


def test_soap_generator_returns_all_sections():
    generator = SoapGenerator()
    result = generator._heuristic_segment(
        "Patient complains of sore throat for 3 days.\n"
        "Temperature 37.5°C, BP 120/80 mmHg.\n"
        "Assessment: Upper respiratory tract infection.\n"
        "Plan: Paracetamol 500mg QID. Review in 5 days."
    )
    assert "subjective" in result
    assert "objective" in result
    assert "assessment" in result
    assert "plan" in result
    assert all(isinstance(v, str) for v in result.values())


def test_icd_coder_urti():
    coder = IcdCoder()
    results = coder.suggest_codes("upper respiratory tract infection")
    assert len(results) > 0
    codes = [r["code"] for r in results]
    assert "J06.9" in codes


def test_icd_coder_hypertension():
    coder = IcdCoder()
    results = coder.suggest_codes("hypertension")
    assert len(results) > 0
    codes = [r["code"] for r in results]
    assert "I10" in codes


def test_icd_coder_diabetes():
    coder = IcdCoder()
    results = coder.suggest_codes("diabetes")
    assert len(results) > 0
    codes = [r["code"] for r in results]
    assert "E11.9" in codes


def test_icd_coder_dental():
    coder = IcdCoder()
    results = coder.suggest_codes("dental examination")
    assert len(results) > 0
    codes = [r["code"] for r in results]
    assert "Z01.2" in codes
