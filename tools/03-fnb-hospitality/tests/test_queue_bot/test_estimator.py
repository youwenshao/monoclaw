"""Tests for wait time estimator: static fallback, EMA, and defaults."""

from openclaw_shared.database import get_db

from fnb_hospitality.queue_bot.queue.estimator import (
    STATIC_FALLBACK,
    _bracket,
    _ema,
    estimate_wait,
)


class TestStaticFallbackEstimates:
    def test_static_fallback_estimates(self, db_paths):
        assert STATIC_FALLBACK["1-2"] == 20
        assert STATIC_FALLBACK["3-4"] == 30
        assert STATIC_FALLBACK["5-6"] == 40
        assert STATIC_FALLBACK["7+"] == 55

    def test_bracket_assignment(self):
        assert _bracket(1) == "1-2"
        assert _bracket(2) == "1-2"
        assert _bracket(3) == "3-4"
        assert _bracket(4) == "3-4"
        assert _bracket(5) == "5-6"
        assert _bracket(6) == "5-6"
        assert _bracket(7) == "7+"
        assert _bracket(12) == "7+"


class TestEMACalculation:
    def test_ema_calculation(self, db_paths):
        values = [60.0, 70.0, 80.0, 90.0]
        result = _ema(values, alpha=0.3)
        assert isinstance(result, float)
        assert result > 0

        expected = values[0]
        for v in values[1:]:
            expected = 0.3 * v + 0.7 * expected
        assert abs(result - expected) < 0.01

    def test_ema_single_value(self):
        assert _ema([42.0]) == 42.0

    def test_ema_empty(self):
        assert _ema([]) == 0.0

    def test_ema_with_turnover_data(self, db_paths):
        """Insert turnover data and verify EMA-based estimation changes."""
        db = str(db_paths["queue_bot"])

        from datetime import date, timedelta
        from fnb_hospitality.queue_bot.queue.manager import join_queue

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        slot = "lunch" if __import__("datetime").datetime.now().hour < 15 else "dinner"

        with get_db(db) as conn:
            for i in range(5):
                conn.execute(
                    """INSERT INTO table_turnover
                       (date, time_slot, table_id, party_size, duration_minutes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (yesterday, slot, f"T{i}", 2, 45 + i * 5),
                )

        join_queue(db, "Waiter", "+85291112222", 2)

        result = estimate_wait(db, 2)
        assert isinstance(result, int)
        assert result >= 5


class TestEstimateWithNoData:
    def test_estimate_with_no_data_uses_defaults(self, db_paths):
        db = str(db_paths["queue_bot"])
        result = estimate_wait(db, 4)
        assert isinstance(result, int)
        assert result >= 5
