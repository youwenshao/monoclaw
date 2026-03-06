"""Abstract form interface and factory for ImmD form definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class FormDefinition(ABC):
    """Base class for all Immigration Department form definitions."""

    form_type: str = ""
    form_name: str = ""
    version: str = ""

    @abstractmethod
    def get_field_list(self) -> list[dict[str, Any]]:
        """Return ordered list of form fields.

        Each dict contains:
            name        – internal field key
            label       – display label (English)
            page        – page number on the PDF form
            max_chars   – character limit for the field
            required    – whether the field is mandatory
            field_type  – 'text' | 'date' | 'checkbox' | 'number'
            format_hint – guidance shown to the user (e.g. 'DD/MM/YYYY')
        """

    @abstractmethod
    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        """Validate populated field values.

        Returns {"valid": bool, "errors": [...], "warnings": [...]}.
        Each error/warning is {"field": str, "message": str}.
        """

    @abstractmethod
    def get_checklist(self) -> list[dict[str, Any]]:
        """Return the list of required supporting documents.

        Each dict: {"name": str, "required": bool, "notes": str}.
        """

    # ── Helpers available to all subclasses ─────────────────────────

    @staticmethod
    def _field(
        name: str,
        label: str,
        *,
        page: int = 1,
        max_chars: int = 80,
        required: bool = True,
        field_type: str = "text",
        format_hint: str = "",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "label": label,
            "page": page,
            "max_chars": max_chars,
            "required": required,
            "field_type": field_type,
            "format_hint": format_hint,
        }

    def _validate_common(self, field_values: dict[str, Any]) -> dict[str, Any]:
        """Run generic validations shared across all forms."""
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        for field in self.get_field_list():
            name = field["name"]
            value = field_values.get(name)

            if field["required"] and not value:
                errors.append({"field": name, "message": f"{field['label']} is required"})
                continue

            if value is None:
                continue

            str_val = str(value)

            if field["max_chars"] and len(str_val) > field["max_chars"]:
                errors.append({
                    "field": name,
                    "message": f"{field['label']} exceeds {field['max_chars']} characters",
                })

            if field["field_type"] == "text" and str_val.isascii() and str_val != str_val.upper():
                warnings.append({
                    "field": name,
                    "message": f"{field['label']} should be in BLOCK CAPITALS",
                })

            if field["field_type"] == "date" and str_val:
                if not _is_valid_date(str_val):
                    errors.append({
                        "field": name,
                        "message": f"{field['label']} must be DD/MM/YYYY",
                    })

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _is_valid_date(val: str) -> bool:
    """Check DD/MM/YYYY format."""
    import re

    if not re.match(r"^\d{2}/\d{2}/\d{4}$", val):
        return False
    day, month, year = int(val[:2]), int(val[3:5]), int(val[6:])
    if month < 1 or month > 12 or day < 1 or day > 31 or year < 1900:
        return False
    return True


# ── Factory ────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[FormDefinition]] = {}


def register_form(cls: type[FormDefinition]) -> type[FormDefinition]:
    """Class decorator to register a form definition."""
    _REGISTRY[cls.form_type] = cls
    return cls


def get_form_definition(form_type: str) -> FormDefinition:
    """Instantiate a FormDefinition by its type code."""
    # Ensure all form modules are imported so the registry is populated
    _ensure_loaded()
    key = form_type.upper()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown form type: {form_type!r}. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[key]()


_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    import importlib
    for mod in ("id990a", "id990b", "gep", "asmtp", "qmas", "iang"):
        importlib.import_module(f"immigration.form_autofill.forms.{mod}")
    _loaded = True
