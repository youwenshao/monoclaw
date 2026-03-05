"""Test runner orchestrating all test categories."""

import time
from rich.console import Console
from rich.table import Table

from ..reporter import TestReporter
from .hardware import HardwareTests
from .macos_env import MacOSEnvironmentTests
from .openclaw_core import OpenClawCoreTests
from .llm_tests import LLMModelTests
from .voice import VoiceSystemTests
from .security import SecurityTests
from .stress_edge import StressEdgeCaseTests

console = Console()


class TestRunner:
    def __init__(self, device_id: str, supabase_url: str, supabase_key: str):
        self.reporter = TestReporter(device_id, supabase_url, supabase_key)
        self.categories = [
            ("hardware", HardwareTests),
            ("macos_environment", MacOSEnvironmentTests),
            ("openclaw_core", OpenClawCoreTests),
            ("llm_models", LLMModelTests),
            ("voice_system", VoiceSystemTests),
            ("security", SecurityTests),
            ("stress_edge_cases", StressEdgeCaseTests),
        ]

    def run_all(self) -> bool:
        console.print("\n[bold]Starting comprehensive device test suite...[/bold]\n")
        start = time.time()
        category_results = {}

        for category_name, test_class in self.categories:
            console.print(f"\n[bold cyan]>>> {category_name.upper().replace('_', ' ')} <<<[/bold cyan]")
            suite = test_class(self.reporter, category_name)
            results = suite.run()
            category_results[category_name] = results
            passed = sum(1 for r in results if r["status"] == "pass")
            failed = sum(1 for r in results if r["status"] == "fail")
            console.print(f"  Results: [green]{passed} passed[/green], [red]{failed} failed[/red], {len(results)} total")

        elapsed = time.time() - start
        overall = self.reporter.upload_summary()
        self.reporter.update_device_status("passed" if overall == "pass" else "failed")

        self._print_summary(category_results, elapsed, overall)
        return overall == "pass"

    def _print_summary(self, category_results: dict, elapsed: float, overall: str):
        console.print(f"\n{'='*60}")
        table = Table(title="Test Suite Summary")
        table.add_column("Category", style="bold")
        table.add_column("Passed", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Warnings", style="yellow")
        table.add_column("Total")

        total_p, total_f, total_w, total_t = 0, 0, 0, 0
        for cat, results in category_results.items():
            p = sum(1 for r in results if r["status"] == "pass")
            f = sum(1 for r in results if r["status"] == "fail")
            w = sum(1 for r in results if r["status"] == "warning")
            t = len(results)
            total_p += p; total_f += f; total_w += w; total_t += t
            table.add_row(cat.replace("_", " ").title(), str(p), str(f), str(w), str(t))

        table.add_row("TOTAL", str(total_p), str(total_f), str(total_w), str(total_t), style="bold")
        console.print(table)
        console.print(f"\nCompleted in {elapsed:.1f}s")
        status_color = "green" if overall == "pass" else "red"
        console.print(f"Overall: [{status_color}]{overall.upper()}[/{status_color}]")
