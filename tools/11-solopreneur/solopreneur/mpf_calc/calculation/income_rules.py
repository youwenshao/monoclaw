"""Rules for determining relevant income components under MPF Ordinance."""

from __future__ import annotations

from decimal import Decimal

EXCLUDED_COMPONENTS = frozenset({
    "severance",
    "long_service_payment",
    "housing_allowance_noncash",
})

_RELEVANT_COMPONENTS = frozenset({
    "basic_salary",
    "overtime",
    "commission",
    "bonus",
    "other_income",
})


def compute_relevant_income(
    basic_salary: Decimal,
    overtime: Decimal = Decimal("0"),
    commission: Decimal = Decimal("0"),
    bonus: Decimal = Decimal("0"),
    other_income: Decimal = Decimal("0"),
) -> Decimal:
    """Sum all relevant income components for MPF calculation."""
    return basic_salary + overtime + commission + bonus + other_income


def is_relevant_income_component(component_name: str) -> bool:
    """Check whether a named component counts toward relevant income."""
    normalised = component_name.lower().strip()
    if normalised in EXCLUDED_COMPONENTS:
        return False
    return normalised in _RELEVANT_COMPONENTS
