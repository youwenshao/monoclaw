"""Three-pass matching engine: exact SKU → fuzzy description → LLM semantic."""

from __future__ import annotations

from typing import Any


class MatchingEngine:
    """Reconcile manifest items against warehouse receipt items using a 3-pass approach."""

    def __init__(self, fuzzy_threshold: int = 80, llm: Any = None) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.llm = llm

    def match(
        self,
        manifest_items: list[dict[str, Any]],
        receipt_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unmatched_m = list(range(len(manifest_items)))
        unmatched_r = list(range(len(receipt_items)))
        results: list[dict[str, Any]] = []

        # Pass 1: exact SKU
        exact_pairs = self._exact_sku_match(manifest_items, receipt_items)
        for mi, ri in exact_pairs:
            if mi in unmatched_m and ri in unmatched_r:
                unmatched_m.remove(mi)
                unmatched_r.remove(ri)
                results.append(self._build_result(
                    manifest_items[mi], receipt_items[ri], confidence=1.0, match_method="exact_sku",
                ))

        # Pass 2: fuzzy description
        if unmatched_m and unmatched_r:
            remaining_m = [(i, manifest_items[i]) for i in unmatched_m]
            remaining_r = [(i, receipt_items[i]) for i in unmatched_r]
            fuzzy_pairs = self._fuzzy_description_match(remaining_m, remaining_r, self.fuzzy_threshold)
            for mi, ri, score in fuzzy_pairs:
                if mi in unmatched_m and ri in unmatched_r:
                    unmatched_m.remove(mi)
                    unmatched_r.remove(ri)
                    results.append(self._build_result(
                        manifest_items[mi], receipt_items[ri],
                        confidence=score / 100.0, match_method="fuzzy_description",
                    ))

        # Pass 3: LLM semantic
        if unmatched_m and unmatched_r and self.llm:
            remaining_m = [(i, manifest_items[i]) for i in unmatched_m]
            remaining_r = [(i, receipt_items[i]) for i in unmatched_r]
            llm_pairs = self._llm_semantic_match(remaining_m, remaining_r)
            for mi, ri, score in llm_pairs:
                if mi in unmatched_m and ri in unmatched_r:
                    unmatched_m.remove(mi)
                    unmatched_r.remove(ri)
                    results.append(self._build_result(
                        manifest_items[mi], receipt_items[ri],
                        confidence=score, match_method="llm_semantic",
                    ))

        for mi in unmatched_m:
            item = manifest_items[mi]
            results.append({
                "manifest_item": item,
                "receipt_item": None,
                "match_confidence": 0.0,
                "variance": -(item.get("quantity") or 0),
                "status": "unmatched_manifest",
                "match_method": None,
            })

        for ri in unmatched_r:
            item = receipt_items[ri]
            results.append({
                "manifest_item": None,
                "receipt_item": item,
                "match_confidence": 0.0,
                "variance": item.get("quantity_received") or 0,
                "status": "unmatched_receipt",
                "match_method": None,
            })

        return results

    # ── Pass 1: Exact SKU ──────────────────────────────────────────────────

    def _exact_sku_match(
        self,
        manifest: list[dict[str, Any]],
        receipt: list[dict[str, Any]],
    ) -> list[tuple[int, int]]:
        receipt_sku_map: dict[str, list[int]] = {}
        for idx, item in enumerate(receipt):
            sku = (item.get("sku") or "").strip().upper()
            if sku:
                receipt_sku_map.setdefault(sku, []).append(idx)

        pairs: list[tuple[int, int]] = []
        used_receipt: set[int] = set()

        for mi, item in enumerate(manifest):
            sku = (item.get("sku") or "").strip().upper()
            if not sku or sku not in receipt_sku_map:
                continue
            for ri in receipt_sku_map[sku]:
                if ri not in used_receipt:
                    pairs.append((mi, ri))
                    used_receipt.add(ri)
                    break

        return pairs

    # ── Pass 2: Fuzzy description ──────────────────────────────────────────

    def _fuzzy_description_match(
        self,
        unmatched_manifest: list[tuple[int, dict[str, Any]]],
        unmatched_receipt: list[tuple[int, dict[str, Any]]],
        threshold: int,
    ) -> list[tuple[int, int, float]]:
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return self._fallback_description_match(unmatched_manifest, unmatched_receipt, threshold)

        pairs: list[tuple[int, int, float]] = []
        used_receipt: set[int] = set()

        candidates: list[tuple[int, int, float]] = []
        for mi, m_item in unmatched_manifest:
            m_desc = (m_item.get("description") or m_item.get("item_description") or "").lower()
            if not m_desc:
                continue
            for ri, r_item in unmatched_receipt:
                if ri in used_receipt:
                    continue
                r_desc = (r_item.get("description") or r_item.get("item_description") or "").lower()
                if not r_desc:
                    continue
                score = fuzz.token_sort_ratio(m_desc, r_desc)
                if score >= threshold:
                    candidates.append((mi, ri, score))

        candidates.sort(key=lambda x: x[2], reverse=True)
        used_manifest: set[int] = set()

        for mi, ri, score in candidates:
            if mi not in used_manifest and ri not in used_receipt:
                pairs.append((mi, ri, score))
                used_manifest.add(mi)
                used_receipt.add(ri)

        return pairs

    def _fallback_description_match(
        self,
        unmatched_manifest: list[tuple[int, dict[str, Any]]],
        unmatched_receipt: list[tuple[int, dict[str, Any]]],
        threshold: int,
    ) -> list[tuple[int, int, float]]:
        """Simple token overlap fallback when rapidfuzz is unavailable."""
        pairs: list[tuple[int, int, float]] = []
        used_receipt: set[int] = set()

        for mi, m_item in unmatched_manifest:
            m_tokens = set((m_item.get("description") or "").lower().split())
            if not m_tokens:
                continue
            best_ri, best_score = -1, 0.0
            for ri, r_item in unmatched_receipt:
                if ri in used_receipt:
                    continue
                r_tokens = set((r_item.get("description") or "").lower().split())
                if not r_tokens:
                    continue
                overlap = len(m_tokens & r_tokens)
                total = max(len(m_tokens | r_tokens), 1)
                score = (overlap / total) * 100
                if score > best_score:
                    best_score = score
                    best_ri = ri
            if best_score >= threshold and best_ri >= 0:
                pairs.append((mi, best_ri, best_score))
                used_receipt.add(best_ri)

        return pairs

    # ── Pass 3: LLM semantic ──────────────────────────────────────────────

    def _llm_semantic_match(
        self,
        unmatched_manifest: list[tuple[int, dict[str, Any]]],
        unmatched_receipt: list[tuple[int, dict[str, Any]]],
    ) -> list[tuple[int, int, float]]:
        if not self.llm:
            return []

        manifest_descs = [
            {"index": mi, "description": m.get("description", ""), "sku": m.get("sku", "")}
            for mi, m in unmatched_manifest
        ]
        receipt_descs = [
            {"index": ri, "description": r.get("description", ""), "sku": r.get("sku", "")}
            for ri, r in unmatched_receipt
        ]

        prompt = (
            "Match shipping manifest items to warehouse receipt items. "
            "Return JSON array of {manifest_index, receipt_index, confidence} "
            "where confidence is 0.0-1.0. Only include confident matches (>0.6).\n\n"
            f"Manifest items: {manifest_descs}\n\n"
            f"Receipt items: {receipt_descs}"
        )

        try:
            import json
            response = self.llm.invoke(prompt)
            text = response if isinstance(response, str) else getattr(response, "content", str(response))
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                matches = json.loads(text[start:end])
                return [
                    (m["manifest_index"], m["receipt_index"], float(m["confidence"]))
                    for m in matches
                    if float(m.get("confidence", 0)) > 0.6
                ]
        except Exception:
            pass

        return []

    # ── Result builder ─────────────────────────────────────────────────────

    def _build_result(
        self,
        manifest_item: dict[str, Any],
        receipt_item: dict[str, Any],
        confidence: float,
        match_method: str,
    ) -> dict[str, Any]:
        m_qty = manifest_item.get("quantity") or 0
        r_qty = receipt_item.get("quantity_received") or 0
        variance = r_qty - m_qty
        condition = (receipt_item.get("condition") or "good").lower()

        if condition == "damaged":
            status = "damaged"
        elif abs(variance) < 0.001:
            status = "matched"
        elif variance < 0:
            status = "shortage"
        else:
            status = "overage"

        return {
            "manifest_item": manifest_item,
            "receipt_item": receipt_item,
            "match_confidence": round(confidence, 3),
            "variance": round(variance, 2),
            "status": status,
            "match_method": match_method,
        }
