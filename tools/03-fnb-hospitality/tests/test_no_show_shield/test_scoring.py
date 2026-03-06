"""Tests for reliability scoring, blacklisting, and no-show prediction."""

from datetime import date

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import init_mona_db

from fnb_hospitality.no_show_shield.scoring.reliability import (
    calculate_score,
)
from fnb_hospitality.no_show_shield.scoring.blacklist import (
    check_and_blacklist,
)
from fnb_hospitality.no_show_shield.scoring.predictor import (
    _rule_based_predict,
    SCORE_NUMERIC,
)


def _insert_guest(conn, phone, name, total, completed, no_shows, late_cancel=0):
    today = date.today().isoformat()
    conn.execute(
        """INSERT INTO guests
           (phone, name, total_bookings, completed, no_shows,
            late_cancellations, reliability_score, last_visit)
           VALUES (?, ?, ?, ?, ?, ?, 'B', ?)""",
        (phone, name, total, completed, no_shows, late_cancel, today),
    )


class TestReliabilityScoreA:
    def test_reliability_score_a(self, db_paths):
        """Guest with >90% completion should be A."""
        db = str(db_paths["no_show_shield"])
        with get_db(db) as conn:
            _insert_guest(conn, "+85291111111", "High Scorer", 10, 10, 0)
        score = calculate_score(db, "+85291111111")
        assert score == "A"


class TestReliabilityScoreC:
    def test_reliability_score_c(self, db_paths):
        """Guest with 50-70% completion should be C."""
        db = str(db_paths["no_show_shield"])
        with get_db(db) as conn:
            _insert_guest(conn, "+85292222222", "Mid Scorer", 10, 6, 4)
        score = calculate_score(db, "+85292222222")
        assert score == "C"


class TestReliabilityScoreMinimumBookings:
    def test_reliability_score_minimum_bookings(self, db_paths):
        """Guests with fewer than 3 bookings should default to B."""
        db = str(db_paths["no_show_shield"])
        with get_db(db) as conn:
            _insert_guest(conn, "+85293333333", "Newbie", 2, 0, 2)
        score = calculate_score(db, "+85293333333")
        assert score == "B"

    def test_unknown_guest_defaults_to_b(self, db_paths):
        db = str(db_paths["no_show_shield"])
        score = calculate_score(db, "+85299999999")
        assert score == "B"


class TestBlacklistAfterThreshold:
    def test_blacklist_after_threshold(self, db_paths):
        """Guest with 3+ no-shows should be auto-blacklisted."""
        db = str(db_paths["no_show_shield"])
        init_mona_db(db)
        with get_db(db) as conn:
            _insert_guest(conn, "+85294444444", "Bad Guest", 6, 3, 3)

        result = check_and_blacklist(db, "+85294444444", no_show_threshold=3)
        assert result is True

        with get_db(db) as conn:
            row = conn.execute(
                "SELECT is_blacklisted FROM guests WHERE phone = '+85294444444'"
            ).fetchone()
        assert row[0] == 1

    def test_not_blacklisted_below_threshold(self, db_paths):
        db = str(db_paths["no_show_shield"])
        with get_db(db) as conn:
            _insert_guest(conn, "+85295555555", "OK Guest", 5, 4, 1)

        result = check_and_blacklist(db, "+85295555555", no_show_threshold=3)
        assert result is False


class TestPredictorRuleBasedHeuristics:
    def test_predictor_rule_based_heuristics(self, db_paths):
        """Low reliability score should produce elevated risk."""
        features = [
            float(SCORE_NUMERIC["D"]),  # score_num = 1
            8.0,                         # large party
            5.0,                         # Saturday (weekend)
            200.0,                       # long lead time hours
            5.0,                         # low commitment channel
        ]
        result = _rule_based_predict(features)

        assert "risk_score" in result
        assert "prediction" in result
        assert "risk_factors" in result
        assert result["model_type"] == "rule_based"
        assert result["risk_score"] > 0.35, "High-risk features should produce elevated score"
        assert result["prediction"] in ("medium", "high")
        assert "low_reliability_score" in result["risk_factors"]

    def test_predictor_low_risk_guest(self, db_paths):
        features = [
            float(SCORE_NUMERIC["A"]),  # score_num = 4
            2.0,                         # small party
            2.0,                         # Wednesday
            24.0,                        # reasonable lead time
            0.0,                         # whatsapp (committed)
        ]
        result = _rule_based_predict(features)
        assert result["prediction"] == "low"
        assert result["risk_score"] < 0.35
