"""Submission checklist generation for grant applications."""

from __future__ import annotations


SCHEME_CHECKLISTS: dict[str, list[dict]] = {
    "GRF": [
        {"item": "GRF Application Form (GRF1)", "required": True, "category": "form", "notes": "Complete all sections; e-submission via RGC portal"},
        {"item": "Research Proposal (max 15 pages excl. references)", "required": True, "category": "proposal", "notes": "Include objectives, methodology, timetable, significance"},
        {"item": "Budget Justification", "required": True, "category": "budget", "notes": "Itemised budget with justification for each category"},
        {"item": "PI's CV (max 2 pages)", "required": True, "category": "cv", "notes": "Use RGC prescribed format"},
        {"item": "Publication List (last 5 years)", "required": True, "category": "cv", "notes": "Mark PI/corresponding author with asterisk"},
        {"item": "Track Record (max 1 page)", "required": True, "category": "cv", "notes": "Summarise research achievements and grant history"},
        {"item": "Ethical Approval (if applicable)", "required": False, "category": "ethics", "notes": "Human subjects, animal experiments, or biosafety"},
        {"item": "Co-PI Agreement Forms", "required": False, "category": "form", "notes": "Required if involving Co-PIs from other institutions"},
        {"item": "Equipment Quotations", "required": False, "category": "budget", "notes": "For equipment items over HK$100,000"},
        {"item": "Research Postgraduate Student Supervision Plan", "required": False, "category": "proposal", "notes": "If RPg support is requested"},
        {"item": "Institutional Endorsement", "required": True, "category": "admin", "notes": "Must be endorsed before external deadline"},
    ],
    "ECS": [
        {"item": "ECS Application Form (ECS1)", "required": True, "category": "form", "notes": "PI must be within first 3 years of first substantive appointment"},
        {"item": "Research Proposal (max 15 pages excl. references)", "required": True, "category": "proposal", "notes": "Include objectives, methodology, timetable, significance"},
        {"item": "Budget Justification", "required": True, "category": "budget", "notes": "Itemised budget; max HK$1.3M including on-costs"},
        {"item": "PI's CV (max 2 pages)", "required": True, "category": "cv", "notes": "Use RGC prescribed format; highlight early-career status"},
        {"item": "Publication List", "required": True, "category": "cv", "notes": "All publications since PhD completion"},
        {"item": "Mentor Statement (if applicable)", "required": False, "category": "form", "notes": "Letter from senior mentor if PI is very junior"},
        {"item": "Ethical Approval (if applicable)", "required": False, "category": "ethics", "notes": "Human subjects, animal experiments, or biosafety"},
        {"item": "Appointment Confirmation Letter", "required": True, "category": "admin", "notes": "Proof of first appointment date from institution"},
        {"item": "Institutional Endorsement", "required": True, "category": "admin", "notes": "Must be endorsed before external deadline"},
    ],
    "CRF": [
        {"item": "CRF Application Form", "required": True, "category": "form", "notes": "Must involve PIs from at least 2 UGC-funded institutions"},
        {"item": "Research Proposal (max 20 pages)", "required": True, "category": "proposal", "notes": "Include justification for collaboration"},
        {"item": "Budget from All Participating Institutions", "required": True, "category": "budget", "notes": "Consolidated and per-institution budgets"},
        {"item": "CVs of All PIs", "required": True, "category": "cv", "notes": "Max 2 pages each; RGC format"},
        {"item": "Collaboration Agreement (draft)", "required": True, "category": "form", "notes": "Outline roles, IP, resource sharing"},
        {"item": "Publication Lists of All PIs", "required": True, "category": "cv", "notes": "Last 5 years; joint publications highlighted"},
        {"item": "Letters of Support from External Partners", "required": False, "category": "form", "notes": "Industry or international partners if applicable"},
        {"item": "Ethical Approval (if applicable)", "required": False, "category": "ethics", "notes": "From all participating institutions"},
        {"item": "Institutional Endorsements (all institutions)", "required": True, "category": "admin", "notes": "Each institution must endorse separately"},
    ],
    "ITF": [
        {"item": "ITF Application Form", "required": True, "category": "form", "notes": "Via ITF online system"},
        {"item": "Detailed Project Proposal", "required": True, "category": "proposal", "notes": "Include market analysis, deliverables, and commercialisation plan"},
        {"item": "Budget Breakdown", "required": True, "category": "budget", "notes": "Manpower, equipment, and other costs"},
        {"item": "Project Team CVs", "required": True, "category": "cv", "notes": "PI and all Co-Is"},
        {"item": "Industry Sponsor Confirmation (if UICP)", "required": False, "category": "form", "notes": "Cash contribution commitment from sponsor"},
        {"item": "IP Agreement Draft", "required": False, "category": "form", "notes": "IP ownership and licensing arrangements"},
        {"item": "Letters of Intent from End-users", "required": False, "category": "form", "notes": "Demonstrate demand for project output"},
        {"item": "Institutional Endorsement", "required": True, "category": "admin", "notes": "From applicant's institution"},
    ],
    "NSFC": [
        {"item": "NSFC Application Form (Chinese version)", "required": True, "category": "form", "notes": "Via NSFC ISIS online system; Chinese required for most programmes"},
        {"item": "Research Proposal", "required": True, "category": "proposal", "notes": "Follow NSFC prescribed format"},
        {"item": "Budget Table", "required": True, "category": "budget", "notes": "NSFC budget categories; amounts in RMB"},
        {"item": "PI's CV", "required": True, "category": "cv", "notes": "NSFC format; include Mainland collaboration history"},
        {"item": "Publication List (last 5 years)", "required": True, "category": "cv", "notes": "Highlight publications with Mainland co-authors"},
        {"item": "Mainland Collaborator Agreement", "required": True, "category": "form", "notes": "Required for joint schemes; signed by both parties"},
        {"item": "Institutional Endorsement (HK side)", "required": True, "category": "admin", "notes": "From HK institution research office"},
        {"item": "Mainland Institution Confirmation", "required": True, "category": "admin", "notes": "For joint schemes with Mainland partners"},
    ],
}


def generate_checklist(scheme_code: str) -> list[dict]:
    """Return the submission checklist for a grant scheme.

    Each item is a dict with keys: item, required, category, notes.
    If the scheme_code is not in the pre-defined lists, returns a
    generic checklist.

    Args:
        scheme_code: The grant scheme identifier (e.g. "GRF", "ECS").

    Returns:
        List of checklist item dicts.
    """
    normalised = scheme_code.upper().strip()

    for key, checklist in SCHEME_CHECKLISTS.items():
        if normalised == key or normalised.startswith(key):
            return checklist

    return [
        {"item": "Application Form", "required": True, "category": "form", "notes": "Check agency website for latest version"},
        {"item": "Research Proposal", "required": True, "category": "proposal", "notes": "Follow agency guidelines for page limit and format"},
        {"item": "Budget Justification", "required": True, "category": "budget", "notes": "Itemised breakdown with justification"},
        {"item": "PI's CV", "required": True, "category": "cv", "notes": "Agency-prescribed format if available"},
        {"item": "Publication List", "required": True, "category": "cv", "notes": "Recent publications relevant to the project"},
        {"item": "Ethical Approval (if applicable)", "required": False, "category": "ethics", "notes": "Human subjects, animals, biosafety"},
        {"item": "Institutional Endorsement", "required": True, "category": "admin", "notes": "Contact research office for internal deadline"},
    ]
