"""Safety inspection checklist templates and scoring engine."""

from __future__ import annotations

import logging

logger = logging.getLogger("openclaw.construction.safety_form.inspections.checklist")

CATEGORY_WEIGHTS: dict[str, float] = {
    "housekeeping": 1.0,
    "ppe": 1.5,
    "scaffolding": 2.0,
    "excavation": 2.0,
    "lifting": 2.0,
    "fire_precautions": 1.5,
}

_DEFAULT_CHECKLIST: list[dict] = [
    # Housekeeping
    {"category": "housekeeping", "description": "Access routes and walkways clear of obstruction"},
    {"category": "housekeeping", "description": "Waste materials properly segregated and disposed"},
    {"category": "housekeeping", "description": "Material storage areas tidy and organised"},
    {"category": "housekeeping", "description": "Adequate lighting in work areas and stairwells"},
    # PPE
    {"category": "ppe", "description": "All workers wearing safety helmets on site"},
    {"category": "ppe", "description": "High-visibility vests worn in vehicle movement areas"},
    {"category": "ppe", "description": "Safety boots worn by all personnel"},
    {"category": "ppe", "description": "Eye/ear protection used where required"},
    {"category": "ppe", "description": "Fall arrest harness worn for work above 2m"},
    # Scaffolding
    {"category": "scaffolding", "description": "Scaffolding erected by competent person with permit"},
    {"category": "scaffolding", "description": "Guard rails and toe boards in place"},
    {"category": "scaffolding", "description": "Bamboo scaffolding ties and ledgers secure"},
    {"category": "scaffolding", "description": "Access ladders properly secured to scaffold"},
    # Excavation
    {"category": "excavation", "description": "Excavation edges barricaded with guard rails"},
    {"category": "excavation", "description": "Shoring/bracing adequate for excavation depth"},
    {"category": "excavation", "description": "Underground services located and marked before digging"},
    # Lifting
    {"category": "lifting", "description": "Crane/hoist valid examination certificate displayed"},
    {"category": "lifting", "description": "Lifting gear inspected and load rated"},
    {"category": "lifting", "description": "Exclusion zone established under lifting area"},
    {"category": "lifting", "description": "Banksman/signaller in position during lifting ops"},
    # Fire Precautions
    {"category": "fire_precautions", "description": "Fire extinguishers accessible and serviced"},
    {"category": "fire_precautions", "description": "Hot work permit obtained where applicable"},
    {"category": "fire_precautions", "description": "Flammable materials stored in designated areas"},
    {"category": "fire_precautions", "description": "Emergency evacuation routes clearly signposted"},
]

_BUILDING_EXTRAS: list[dict] = [
    {"category": "scaffolding", "description": "Catch fan / safety net below external scaffolding"},
    {"category": "lifting", "description": "Tower crane anti-collision device functional"},
    {"category": "ppe", "description": "Respiratory protection for concrete cutting / grinding"},
]

_CIVIL_EXTRAS: list[dict] = [
    {"category": "excavation", "description": "Dewatering system operational and monitored"},
    {"category": "excavation", "description": "Slope stability measures in place"},
    {"category": "lifting", "description": "Piling rig exclusion zone maintained"},
]

_RENOVATION_EXTRAS: list[dict] = [
    {"category": "housekeeping", "description": "Noise and dust containment measures in place"},
    {"category": "fire_precautions", "description": "Existing fire services not obstructed"},
    {"category": "ppe", "description": "Asbestos awareness check completed (pre-1990 buildings)"},
]


def get_default_checklist() -> list[dict]:
    """Return the default safety checklist items."""
    return [item.copy() for item in _DEFAULT_CHECKLIST]


def get_checklist_for_site_type(site_type: str) -> list[dict]:
    """Return checklist items tailored to the site type.

    site_type: 'building', 'civil', or 'renovation'
    """
    base = get_default_checklist()

    extras_map = {
        "building": _BUILDING_EXTRAS,
        "civil": _CIVIL_EXTRAS,
        "renovation": _RENOVATION_EXTRAS,
    }

    extras = extras_map.get(site_type.lower(), [])
    for item in extras:
        base.append(item.copy())

    logger.debug("Checklist for %s: %d items", site_type, len(base))
    return base


def calculate_inspection_score(items: list[dict]) -> float:
    """Calculate a weighted inspection score.

    Each item should have 'category' and 'status' (pass/fail/na) keys.
    Returns a percentage score (0-100). Items marked 'na' are excluded.
    """
    category_scores: dict[str, dict[str, int]] = {}

    for item in items:
        cat = item.get("category", "other")
        status = item.get("status", "pending")
        if cat not in category_scores:
            category_scores[cat] = {"passed": 0, "applicable": 0}
        if status == "na":
            continue
        category_scores[cat]["applicable"] += 1
        if status == "pass":
            category_scores[cat]["passed"] += 1

    total_weighted = 0.0
    total_weight = 0.0

    for cat, counts in category_scores.items():
        if counts["applicable"] == 0:
            continue
        weight = CATEGORY_WEIGHTS.get(cat, 1.0)
        cat_score = counts["passed"] / counts["applicable"]
        total_weighted += cat_score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    score = (total_weighted / total_weight) * 100
    logger.debug("Inspection score: %.1f%% (categories=%d)", score, len(category_scores))
    return round(score, 1)
