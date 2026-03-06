"""Prompt templates for defect classification and analysis."""

from __future__ import annotations

DEFECT_CATEGORIES = [
    "water_seepage",
    "concrete_spalling",
    "plumbing",
    "electrical",
    "lift",
    "window",
    "common_area",
    "structural",
    "other",
]

DEFECT_CLASSIFICATION_PROMPT = (
    "You are a Hong Kong construction defect classifier. "
    "Given a description of a building defect, classify it into exactly one category.\n\n"
    "Categories:\n"
    "- water_seepage: water leaks, dampness, mould caused by water ingress\n"
    "- concrete_spalling: flaking, chipping, exposed rebar on concrete surfaces\n"
    "- plumbing: pipe leaks, drainage blockages, water supply issues\n"
    "- electrical: wiring faults, power outages, faulty switches or sockets\n"
    "- lift: elevator malfunctions, noise, door issues\n"
    "- window: broken glass, frame damage, seal failures, hinges\n"
    "- common_area: damage to lobbies, corridors, staircases, facilities\n"
    "- structural: cracks in walls/columns/beams, settlement, foundation issues\n"
    "- other: anything that does not fit the above\n\n"
    "Respond with ONLY the category name, nothing else."
)


def format_classification_prompt(description: str) -> str:
    """Build user prompt for defect classification."""
    return f"Classify this building defect:\n\n{description}"
