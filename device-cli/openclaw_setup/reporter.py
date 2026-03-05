"""Uploads test results to Supabase in real-time."""

from datetime import datetime, timezone
from typing import Optional
from supabase import create_client


class TestReporter:
    def __init__(self, device_id: str, supabase_url: str, supabase_key: str):
        self.device_id = device_id
        self.supabase = create_client(supabase_url, supabase_key)
        self.results: list[dict] = []

    def report_result(
        self,
        category: str,
        test_name: str,
        status: str,
        details: Optional[dict] = None,
        duration_ms: Optional[int] = None,
    ):
        result = {
            "device_id": self.device_id,
            "category": category,
            "test_name": test_name,
            "status": status,
            "details": details or {},
            "duration_ms": duration_ms,
        }
        self.results.append(result)
        try:
            self.supabase.table("device_test_results").insert(result).execute()
        except Exception as e:
            print(f"Warning: Failed to upload result for {test_name}: {e}")

    def upload_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")
        warnings = sum(1 for r in self.results if r["status"] == "warning")
        skipped = sum(1 for r in self.results if r["status"] == "skipped")

        overall = "pass" if failed == 0 else "fail"

        summary = {
            "device_id": self.device_id,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "skipped": skipped,
            "overall_status": overall,
            "full_report_json": {
                "results": self.results,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        try:
            self.supabase.table("device_test_summaries").insert(summary).execute()
        except Exception as e:
            print(f"Warning: Failed to upload summary: {e}")

        return overall

    def update_device_status(self, status: str):
        try:
            update_data = {"setup_status": status}
            if status in ("passed", "failed"):
                update_data["setup_completed_at"] = datetime.now(timezone.utc).isoformat()
            self.supabase.table("devices").update(update_data).eq("id", self.device_id).execute()
        except Exception as e:
            print(f"Warning: Failed to update device status: {e}")
