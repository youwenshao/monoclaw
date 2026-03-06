"""Tests for database schema initialization and seeding."""

from openclaw_shared.database import get_db


class TestInitAllDatabases:
    def test_init_all_databases_creates_all_files(self, db_paths):
        expected = {
            "table_master",
            "queue_bot",
            "no_show_shield",
            "sommelier_memory",
            "shared",
            "mona_events",
        }
        assert set(db_paths.keys()) == expected
        for name, path in db_paths.items():
            assert path.exists(), f"{name} db file missing at {path}"

    def test_table_master_schema(self, db_paths):
        with get_db(db_paths["table_master"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in ("tables", "bookings", "booking_analytics"):
            assert expected in tables, f"Missing table: {expected}"

    def test_queue_bot_schema(self, db_paths):
        with get_db(db_paths["queue_bot"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in (
            "queue_entries",
            "table_turnover",
            "queue_analytics",
            "notifications",
        ):
            assert expected in tables, f"Missing table: {expected}"

    def test_no_show_shield_schema(self, db_paths):
        with get_db(db_paths["no_show_shield"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in ("guests", "confirmations", "waitlist", "no_show_predictions"):
            assert expected in tables, f"Missing table: {expected}"

    def test_sommelier_memory_schema(self, db_paths):
        with get_db(db_paths["sommelier_memory"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in (
            "sm_guests",
            "dietary_info",
            "celebrations",
            "visits",
            "preferences",
        ):
            assert expected in tables, f"Missing table: {expected}"

    def test_shared_schema(self, db_paths):
        with get_db(db_paths["shared"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "shared_guests" in tables

    def test_seed_all(self, seeded_db_paths):
        with get_db(seeded_db_paths["table_master"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] > 0

        with get_db(seeded_db_paths["queue_bot"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM queue_entries").fetchone()[0] > 0
            assert (
                conn.execute("SELECT COUNT(*) FROM table_turnover").fetchone()[0] > 0
            )

        with get_db(seeded_db_paths["no_show_shield"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0] > 0

        with get_db(seeded_db_paths["sommelier_memory"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM sm_guests").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM dietary_info").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM celebrations").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0] > 0
