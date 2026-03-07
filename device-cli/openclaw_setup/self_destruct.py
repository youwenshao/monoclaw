"""Removes all CLI traces after technician confirmation."""

import os
import sys
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from supabase import create_client

console = Console()


class SelfDestruct:
    def __init__(self, device_id: str, supabase_url: str, supabase_key: str):
        self.device_id = device_id
        self.supabase = create_client(supabase_url, supabase_key)

    def run(self):
        console.print("\n[bold]Pre-flight checks...[/bold]")

        if not self._verify_tests_passed():
            console.print("[bold red]Cannot finalize: tests have not all passed.[/bold red]")
            console.print("Run 'openclaw-setup test' first and resolve all failures.")
            sys.exit(1)

        console.print("[green]All tests passed.[/green]")

        self._update_device_status("shipped")
        self._update_order_status()

        console.print("\n[bold]Beginning self-destruct sequence...[/bold]")

        self._remove_credentials()
        self._remove_setup_logs()
        self._print_shipping_checklist()
        self._uninstall_self()

    def _verify_tests_passed(self) -> bool:
        result = self.supabase.table("device_test_summaries") \
            .select("overall_status") \
            .eq("device_id", self.device_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if not result.data:
            return False
        return result.data[0]["overall_status"] == "pass"

    def _update_device_status(self, status: str):
        console.print(f"  Updating device status to: {status}")
        self.supabase.table("devices").update(
            {"setup_status": status}
        ).eq("id", self.device_id).execute()

    def _update_order_status(self):
        device = self.supabase.table("devices") \
            .select("order_id") \
            .eq("id", self.device_id) \
            .single() \
            .execute()

        if device.data:
            order_id = device.data["order_id"]
            self.supabase.table("orders").update(
                {"status": "ready"}
            ).eq("id", order_id).execute()

            self.supabase.table("order_status_history").insert({
                "order_id": order_id,
                "from_status": "testing",
                "to_status": "ready",
                "notes": "Device passed all tests, ready for shipping",
            }).execute()

    def _remove_credentials(self):
        cred_path = Path("/opt/openclaw/.setup-credentials")
        if cred_path.exists():
            try:
                cred_path.unlink()
                console.print("  [green]Removed setup credentials[/green]")
            except PermissionError:
                # Fallback to sudo rm if the directory is root-owned
                subprocess.run(["sudo", "rm", "-f", str(cred_path)], check=True)
                console.print("  [green]Removed setup credentials (via sudo)[/green]")

    def _remove_setup_logs(self):
        log_dir = Path("/tmp/openclaw-setup")
        if log_dir.exists():
            shutil.rmtree(log_dir)
            console.print("  [green]Removed setup logs[/green]")

    def _print_shipping_checklist(self):
        console.print("\n[bold yellow]Technician Shipping Checklist:[/bold yellow]")
        console.print("  [ ] Power cable included")
        console.print("  [ ] Device exterior cleaned")
        console.print("  [ ] Packaging secure")
        console.print("  [ ] Shipping label attached")
        console.print("  [ ] Client notification sent")
        console.print("  [ ] Order status updated to 'shipped' after dispatch")

    def _uninstall_self(self):
        console.print("\n[bold]Uninstalling openclaw-setup CLI...[/bold]")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", "openclaw-setup"],
                capture_output=True,
            )
            console.print("  [green]CLI package uninstalled[/green]")
        except Exception:
            console.print("  [yellow]Manual uninstall may be required: pip uninstall openclaw-setup[/yellow]")

        pip_cache = Path.home() / ".cache" / "pip"
        if pip_cache.exists():
            for cached in pip_cache.rglob("openclaw*"):
                try:
                    if cached.is_file():
                        cached.unlink()
                    elif cached.is_dir():
                        shutil.rmtree(cached)
                except Exception:
                    pass

        console.print("\n[bold green]Self-destruct complete.[/bold green]")
        console.print("The openclaw-setup CLI has been removed from this device.")
