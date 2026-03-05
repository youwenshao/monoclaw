"""Base class for test categories."""

import time
from typing import Optional
from rich.console import Console

console = Console()


class BaseTestSuite:
    def __init__(self, reporter, category: str):
        self.reporter = reporter
        self.category = category
        self.results: list[dict] = []

    def run(self) -> list[dict]:
        for method_name in dir(self):
            if method_name.startswith("test_"):
                test_name = method_name.replace("test_", "").replace("_", " ").title()
                start = time.time()
                try:
                    result = getattr(self, method_name)()
                    duration_ms = int((time.time() - start) * 1000)
                    if isinstance(result, tuple):
                        status, details = result
                    elif isinstance(result, str):
                        status, details = result, {}
                    else:
                        status, details = "pass", {}
                    self._record(test_name, status, details, duration_ms)
                except Exception as e:
                    duration_ms = int((time.time() - start) * 1000)
                    self._record(test_name, "fail", {"error": str(e)}, duration_ms)
        return self.results

    def _record(self, test_name: str, status: str, details: Optional[dict], duration_ms: int):
        icon = {"pass": "[green]PASS[/green]", "fail": "[red]FAIL[/red]",
                "warning": "[yellow]WARN[/yellow]", "skipped": "[dim]SKIP[/dim]"}
        console.print(f"  {icon.get(status, status)} {test_name} ({duration_ms}ms)")
        self.reporter.report_result(self.category, test_name, status, details, duration_ms)
        self.results.append({"test_name": test_name, "status": status, "details": details})
