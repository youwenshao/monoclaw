"""Auto-fill application form fields from researcher profile and scheme info."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def populate_form_fields(
    db_path: str | Path,
    researcher_id: int,
    scheme_id: int,
) -> dict:
    """Return a dict of pre-filled field values for a grant application.

    Combines researcher profile data with scheme metadata to produce
    key-value pairs suitable for populating PDF / Word form fields.
    """
    with get_db(db_path) as conn:
        researcher = conn.execute(
            "SELECT * FROM researchers WHERE id = ?", (researcher_id,)
        ).fetchone()
        scheme = conn.execute(
            "SELECT * FROM grant_schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
        pubs = conn.execute(
            """SELECT * FROM publications
               WHERE researcher_id = ?
               ORDER BY year DESC""",
            (researcher_id,),
        ).fetchall()

    if not researcher:
        return {}

    r = dict(researcher)
    fields: dict[str, Any] = {
        "pi_name_en": r.get("name_en", ""),
        "pi_name_tc": r.get("name_tc", ""),
        "pi_title": r.get("title", ""),
        "pi_department": r.get("department", ""),
        "pi_institution": r.get("institution", ""),
        "pi_email": r.get("email", ""),
        "pi_orcid": r.get("orcid", ""),
        "pi_research_interests": r.get("research_interests", ""),
        "pi_appointment_date": r.get("appointment_date", ""),
    }

    if scheme:
        s = dict(scheme)
        fields.update({
            "scheme_name": s.get("scheme_name", ""),
            "scheme_code": s.get("scheme_code", ""),
            "agency": s.get("agency", ""),
            "funding_range": s.get("typical_funding_range", ""),
            "max_duration_years": s.get("duration_years", ""),
            "eligibility_notes": s.get("eligibility_notes", ""),
        })

    pub_list = [dict(p) for p in pubs]
    total_citations = sum(p.get("citation_count", 0) or 0 for p in pub_list)
    corresponding = [p for p in pub_list if p.get("is_corresponding_author")]
    recent_five_years = [p for p in pub_list if p.get("year") and p["year"] >= _current_year() - 5]

    fields.update({
        "total_publications": len(pub_list),
        "total_citations": total_citations,
        "corresponding_author_count": len(corresponding),
        "publications_last_5_years": len(recent_five_years),
        "publication_list_formatted": generate_publication_list(db_path, researcher_id),
    })

    return fields


def _current_year() -> int:
    from datetime import date
    return date.today().year


def generate_publication_list(
    db_path: str | Path,
    researcher_id: int,
    format: str = "rgc",
) -> str:
    """Format a publication list for a grant application.

    Args:
        db_path: Path to the grant_tracker database.
        researcher_id: The researcher whose publications to format.
        format: Style — currently ``"rgc"`` (RGC standard) or ``"plain"``.

    Returns:
        Formatted publication list as a single string.
    """
    with get_db(db_path) as conn:
        pubs = conn.execute(
            """SELECT * FROM publications
               WHERE researcher_id = ?
               ORDER BY year DESC, title ASC""",
            (researcher_id,),
        ).fetchall()

    if not pubs:
        return ""

    if format == "plain":
        return _format_plain(pubs)
    return _format_rgc(pubs)


def _format_rgc(pubs: list[Any]) -> str:
    lines: list[str] = []
    for i, row in enumerate(pubs, 1):
        p = dict(row)
        authors = p.get("authors", "")
        title = p.get("title", "")
        journal = p.get("journal", "")
        year = p.get("year", "")
        doi = p.get("doi", "")
        citations = p.get("citation_count")
        corr = " *" if p.get("is_corresponding_author") else ""

        entry = f"{i}. {authors}{corr} ({year}). {title}. {journal}."
        if doi:
            entry += f" DOI: {doi}."
        if citations is not None:
            entry += f" [Citations: {citations}]"
        lines.append(entry)

    header = f"Publication List ({len(pubs)} items)\n{'=' * 40}"
    return header + "\n" + "\n\n".join(lines)


def _format_plain(pubs: list[Any]) -> str:
    lines: list[str] = []
    for row in pubs:
        p = dict(row)
        lines.append(
            f"{p.get('authors', '')} ({p.get('year', '')}). "
            f"{p.get('title', '')}. {p.get('journal', '')}."
        )
    return "\n".join(lines)
