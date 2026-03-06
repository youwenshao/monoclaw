"""Link re-export declarations to their matching original import declarations."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.trade-doc-ai.reexport")


class ReexportLinker:
    """Find and link matching import declarations for re-export filings.

    HK Customs requires re-export TDECs to reference the original import
    declaration.  This service matches by product HS code, shipper/consignee,
    and value to suggest the most likely original import.
    """

    def find_matching_import(
        self, db_path: str | Path, re_export_declaration: dict
    ) -> list[dict]:
        """Find import declarations that could be the origin of a re-export.

        Matching criteria (ranked):
        1. Exact HS code overlap in declaration items
        2. Same consignee on the import as shipper on re-export
        3. Chronological — import date before re-export date
        """
        hs_codes = re_export_declaration.get("hs_codes", [])
        shipper = re_export_declaration.get("shipper", "")
        re_export_date = re_export_declaration.get("declaration_date", "")

        if not hs_codes and not shipper:
            return []

        with get_db(db_path) as conn:
            candidates: list[dict] = []

            if hs_codes:
                placeholders = ",".join("?" * len(hs_codes))
                rows = conn.execute(
                    f"""SELECT DISTINCT td.*
                        FROM trade_declarations td
                        JOIN declaration_items di ON di.declaration_id = td.id
                        WHERE td.declaration_type = 'import'
                          AND di.hs_code IN ({placeholders})
                        ORDER BY td.created_at DESC
                        LIMIT 20""",  # noqa: S608
                    hs_codes,
                ).fetchall()
                candidates.extend([dict(r) for r in rows])

            if shipper and not candidates:
                rows = conn.execute(
                    """SELECT * FROM trade_declarations
                       WHERE declaration_type = 'import'
                         AND consignee LIKE ?
                       ORDER BY created_at DESC LIMIT 10""",
                    (f"%{shipper}%",),
                ).fetchall()
                candidates.extend([dict(r) for r in rows])

        seen_ids: set[int] = set()
        unique: list[dict] = []
        for c in candidates:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                score = self._score_match(c, re_export_declaration)
                c["match_score"] = score
                unique.append(c)

        unique.sort(key=lambda x: x["match_score"], reverse=True)
        return unique[:5]

    def link_declarations(
        self, db_path: str | Path, import_id: int, reexport_id: int
    ) -> dict:
        """Link a re-export declaration to its originating import.

        Updates the trade_declarations.linked_import_id field.
        Returns the updated re-export declaration.
        """
        with get_db(db_path) as conn:
            import_row = conn.execute(
                "SELECT id, declaration_type FROM trade_declarations WHERE id = ?",
                (import_id,),
            ).fetchone()
            if not import_row or import_row["declaration_type"] != "import":
                raise ValueError(f"Declaration {import_id} is not an import declaration")

            reexport_row = conn.execute(
                "SELECT id, declaration_type FROM trade_declarations WHERE id = ?",
                (reexport_id,),
            ).fetchone()
            if not reexport_row or reexport_row["declaration_type"] != "re_export":
                raise ValueError(f"Declaration {reexport_id} is not a re-export declaration")

            conn.execute(
                "UPDATE trade_declarations SET linked_import_id = ? WHERE id = ?",
                (import_id, reexport_id),
            )

            updated = conn.execute(
                "SELECT * FROM trade_declarations WHERE id = ?", (reexport_id,)
            ).fetchone()

        logger.info("Linked re-export %d to import %d", reexport_id, import_id)
        return dict(updated)

    @staticmethod
    def _score_match(import_decl: dict, re_export_decl: dict) -> float:
        """Score how well an import matches a re-export (0.0 - 1.0)."""
        score = 0.0

        if import_decl.get("consignee") and re_export_decl.get("shipper"):
            if import_decl["consignee"].lower() == re_export_decl["shipper"].lower():
                score += 0.4

        import_date = import_decl.get("created_at", "")
        re_date = re_export_decl.get("declaration_date", "")
        if import_date and re_date and str(import_date)[:10] <= str(re_date)[:10]:
            score += 0.2

        import_value = import_decl.get("total_value", 0)
        re_value = re_export_decl.get("total_value", 0)
        if import_value and re_value:
            ratio = min(import_value, re_value) / max(import_value, re_value)
            score += ratio * 0.3

        if import_decl.get("currency") == re_export_decl.get("currency"):
            score += 0.1

        return min(score, 1.0)
