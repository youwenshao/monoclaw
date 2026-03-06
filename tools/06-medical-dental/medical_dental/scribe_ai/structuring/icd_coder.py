"""ICD-10 code suggestion engine using fuzzy string matching."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


ICD10_CODES: dict[str, str] = {
    "J06.9": "Acute upper respiratory infection, unspecified (URTI)",
    "J20.9": "Acute bronchitis, unspecified",
    "J18.9": "Pneumonia, unspecified organism",
    "J45.9": "Asthma, unspecified",
    "J30.1": "Allergic rhinitis due to pollen",
    "I10": "Essential (primary) hypertension",
    "I25.1": "Atherosclerotic heart disease",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "E78.0": "Pure hypercholesterolaemia",
    "E03.9": "Hypothyroidism, unspecified",
    "K21.0": "Gastro-oesophageal reflux disease with oesophagitis",
    "K29.7": "Gastritis, unspecified",
    "K08.1": "Loss of teeth due to accident, extraction or local periodontal disease",
    "K02.1": "Dentine caries",
    "K04.0": "Pulpitis",
    "K05.1": "Chronic gingivitis",
    "K05.3": "Chronic periodontitis",
    "Z01.2": "Dental examination and cleaning",
    "M54.5": "Low back pain",
    "G43.9": "Migraine, unspecified",
    "L30.9": "Dermatitis, unspecified (eczema)",
    "N39.0": "Urinary tract infection, site not specified",
    "B34.9": "Viral infection, unspecified",
    "R50.9": "Fever, unspecified",
    "R51": "Headache",
    "F41.9": "Anxiety disorder, unspecified",
    "F32.9": "Depressive episode, unspecified",
    "Z00.0": "General adult medical examination",
    "R10.4": "Other and unspecified abdominal pain",
    "R05": "Cough",
}

KEYWORD_MAP: dict[str, list[str]] = {
    "J06.9": ["urti", "upper respiratory", "sore throat", "runny nose", "common cold", "cold", "flu-like"],
    "J20.9": ["bronchitis", "chest infection", "productive cough"],
    "J18.9": ["pneumonia", "lung infection"],
    "J45.9": ["asthma", "wheeze", "wheezing", "bronchospasm"],
    "J30.1": ["allergic rhinitis", "hay fever", "nasal allergy"],
    "I10": ["hypertension", "high blood pressure", "htn", "elevated bp"],
    "I25.1": ["coronary artery disease", "cad", "ischaemic heart", "ihd"],
    "E11.9": ["type 2 diabetes", "dm", "diabetes mellitus", "t2dm", "niddm"],
    "E78.0": ["hypercholesterolaemia", "hypercholesterolemia", "high cholesterol", "dyslipidaemia"],
    "E03.9": ["hypothyroidism", "underactive thyroid", "low thyroid"],
    "K21.0": ["gerd", "reflux", "acid reflux", "gord", "heartburn"],
    "K29.7": ["gastritis", "stomach inflammation"],
    "K08.1": ["tooth loss", "tooth extraction", "missing tooth", "edentulous"],
    "K02.1": ["dental caries", "cavity", "tooth decay"],
    "K04.0": ["pulpitis", "tooth nerve", "toothache"],
    "K05.1": ["gingivitis", "gum inflammation", "gum disease"],
    "K05.3": ["periodontitis", "periodontal disease", "gum infection"],
    "Z01.2": ["dental exam", "dental check", "dental cleaning", "scaling", "prophylaxis"],
    "M54.5": ["low back pain", "lbp", "lumbar pain", "back pain"],
    "G43.9": ["migraine", "severe headache"],
    "L30.9": ["eczema", "dermatitis", "skin rash", "atopic dermatitis"],
    "N39.0": ["uti", "urinary tract infection", "cystitis", "dysuria"],
    "B34.9": ["viral infection", "viral illness", "viral fever"],
    "R50.9": ["fever", "pyrexia", "febrile"],
    "R51": ["headache", "cephalgia"],
    "F41.9": ["anxiety", "anxious", "panic", "generalised anxiety"],
    "F32.9": ["depression", "depressive", "low mood", "depressed"],
    "Z00.0": ["general check", "health check", "medical exam", "annual check"],
    "R10.4": ["abdominal pain", "stomach ache", "tummy pain", "belly pain"],
    "R05": ["cough", "persistent cough", "dry cough"],
}


class IcdCoder:
    """Suggest ICD-10 codes for diagnosis text using fuzzy matching."""

    def __init__(self) -> None:
        self._codes = dict(ICD10_CODES)
        self._keywords = dict(KEYWORD_MAP)

    def suggest_codes(
        self,
        diagnosis_text: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Return ranked ICD-10 code suggestions for the given diagnosis text."""
        if not diagnosis_text or not diagnosis_text.strip():
            return []

        query = diagnosis_text.lower().strip()
        scored: dict[str, float] = {}

        for code, keywords in self._keywords.items():
            keyword_score = self._keyword_match_score(query, keywords)
            if keyword_score > 0:
                scored[code] = max(scored.get(code, 0), keyword_score)

        for code, description in self._codes.items():
            desc_lower = description.lower()
            seq_score = SequenceMatcher(None, query, desc_lower).ratio()
            if seq_score > 0.35:
                scored[code] = max(scored.get(code, 0), seq_score)

        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:max_results]

        return [
            {
                "code": code,
                "description": self._codes[code],
                "confidence": round(score, 3),
            }
            for code, score in ranked
            if score > 0.25
        ]

    @staticmethod
    def _keyword_match_score(query: str, keywords: list[str]) -> float:
        best = 0.0
        for kw in keywords:
            if kw in query:
                length_ratio = len(kw) / max(len(query), 1)
                best = max(best, 0.6 + 0.4 * length_ratio)
            else:
                partial = SequenceMatcher(None, query, kw).ratio()
                if partial > 0.6:
                    best = max(best, partial * 0.8)
        return best

    def add_codes(self, codes: dict[str, str], keywords: dict[str, list[str]] | None = None) -> None:
        """Extend the built-in code dictionary with additional entries."""
        self._codes.update(codes)
        if keywords:
            for code, kws in keywords.items():
                existing = self._keywords.get(code, [])
                self._keywords[code] = list(set(existing + kws))
