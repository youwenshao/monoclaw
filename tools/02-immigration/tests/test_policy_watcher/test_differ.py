"""Tests for PolicyWatcher diff and classification."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from immigration.policy_watcher.analysis.differ import (
    compute_diff,
    generate_content_hash,
    has_content_changed,
)
from immigration.policy_watcher.analysis.classifier import (
    classify_urgency,
    detect_affected_schemes,
)


class TestDiffer:
    """Policy differ tests per prompt criteria."""

    def test_identical_text_no_change(self):
        h1 = generate_content_hash("identical text")
        h2 = generate_content_hash("identical text")
        assert not has_content_changed(h1, h2)

    def test_different_text_detected(self):
        h1 = generate_content_hash("old policy text")
        h2 = generate_content_hash("new policy text")
        assert has_content_changed(h1, h2)

    def test_compute_diff_additions(self):
        result = compute_diff("original text\nline two", "original text\nline two\nnew line added")
        assert len(result["additions"]) > 0 or result["change_count"] > 0

    def test_compute_diff_deletions(self):
        result = compute_diff("line one\nline two\nline three", "line one\nline three")
        assert len(result["deletions"]) > 0 or result["change_count"] > 0

    def test_compute_diff_no_change(self):
        result = compute_diff("same text", "same text")
        assert result["change_count"] == 0


class TestClassifier:
    """Urgency classification tests per prompt criteria."""

    def test_quota_change_is_urgent(self):
        summary = "QMAS annual quota reduced from 4000 to 2000"
        urgency = classify_urgency(summary, "QMAS")
        assert urgency == "urgent"

    def test_salary_change_is_important(self):
        summary = "GEP minimum salary threshold increased to HK$25,000"
        urgency = classify_urgency(summary, "GEP")
        assert urgency in ("important", "urgent")

    def test_procedural_is_routine(self):
        summary = "Minor update to application form layout for ID990A"
        urgency = classify_urgency(summary, "GEP")
        assert urgency == "routine"

    def test_detect_gep_scheme(self):
        schemes = detect_affected_schemes(
            "The General Employment Policy salary requirements have been updated"
        )
        assert "GEP" in schemes

    def test_detect_qmas_scheme(self):
        schemes = detect_affected_schemes(
            "Quality Migrant Admission Scheme quota announcement"
        )
        assert "QMAS" in schemes

    def test_detect_multiple_schemes(self):
        schemes = detect_affected_schemes(
            "Changes to TTPS university list and IANG eligibility criteria"
        )
        assert "TTPS" in schemes
        assert "IANG" in schemes
