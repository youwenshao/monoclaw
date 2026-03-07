#!/usr/bin/env python3
"""OpenClaw Setup CLI — provision, test, and finalize Mac devices for MonoClaw."""

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="1.0.0")
def main():
    """OpenClaw device provisioning CLI for MonoClaw technicians."""
    pass


@main.command()
@click.option("--order-id", help="Supabase order UUID (or set OPENCLAW_ORDER_ID)")
@click.option("--email", help="Client email to look up most recent order")
@click.option("--serial", help="Mac serial number (or set OPENCLAW_SERIAL)")
@click.option("--supabase-url", envvar="SUPABASE_URL", required=True)
@click.option("--supabase-key", envvar="SUPABASE_SERVICE_KEY", required=True)
def provision(order_id: str, email: str, serial: str, supabase_url: str, supabase_key: str):
    """Set up OpenClaw on a new Mac device.

    Provide either --order-id or --email to identify the order.
    """
    order_id = order_id or os.environ.get("OPENCLAW_ORDER_ID")
    serial = serial or os.environ.get("OPENCLAW_SERIAL")

    if not serial:
        console.print("[bold red]Error:[/bold red] Provide --serial or set OPENCLAW_SERIAL.")
        sys.exit(1)

    if not order_id and not email:
        console.print("[bold red]Error:[/bold red] Provide --order-id (or OPENCLAW_ORDER_ID) or --email to identify the order.")
        sys.exit(1)

    if not order_id and email:
        from supabase import create_client
        from .order_fetcher import OrderFetcher
        console.print(f"[bold blue]Looking up order for {email}...[/bold blue]")
        sb = create_client(supabase_url, supabase_key)
        fetcher = OrderFetcher(sb)
        spec = fetcher.fetch_by_email(email)
        order_id = spec.order_id
        console.print(f"[green]Found order: {order_id}[/green]")

    from .provisioner import Provisioner

    console.print("[bold blue]MonoClaw Device Provisioner[/bold blue]")
    console.print(f"Order: {order_id}")
    console.print(f"Serial: {serial}")

    provisioner = Provisioner(
        order_id=order_id,
        serial_number=serial,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )
    success = provisioner.run()
    sys.exit(0 if success else 1)


@main.command()
@click.option("--device-id", required=True, help="Supabase device UUID")
@click.option("--supabase-url", envvar="SUPABASE_URL", required=True)
@click.option("--supabase-key", envvar="SUPABASE_SERVICE_KEY", required=True)
def test(device_id: str, supabase_url: str, supabase_key: str):
    """Run comprehensive test suite on a provisioned device."""
    from .test_suite.runner import TestRunner

    console.print("[bold blue]MonoClaw Device Test Suite[/bold blue]")
    console.print(f"Device: {device_id}")

    runner = TestRunner(
        device_id=device_id,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )
    success = runner.run_all()
    sys.exit(0 if success else 1)


@main.command()
def status():
    """Show current provisioning/test status."""
    import json
    import os
    from pathlib import Path

    state_file = Path("/opt/openclaw/state/active-work.json")
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        console.print_json(json.dumps(state, indent=2))
    else:
        console.print("[yellow]No active provisioning state found.[/yellow]")


@main.command()
@click.option("--device-id", required=True, help="Supabase device UUID")
@click.option("--supabase-url", envvar="SUPABASE_URL", required=True)
@click.option("--supabase-key", envvar="SUPABASE_SERVICE_KEY", required=True)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation (for automated one-click setup)")
def finalize(device_id: str, supabase_url: str, supabase_key: str, yes: bool):
    """Finalize setup and self-destruct the CLI tool."""
    if not yes:
        click.confirm("This will permanently remove the setup CLI. Continue?", abort=True)

    from .self_destruct import SelfDestruct

    console.print("[bold red]MonoClaw Finalizer[/bold red]")

    destroyer = SelfDestruct(
        device_id=device_id,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )
    destroyer.run()


@main.command()
def device_id():
    """Print device_id from setup credentials (for scripting after provision)."""
    cred_path = Path("/opt/openclaw/.setup-credentials")
    if not cred_path.exists():
        console.print("[bold red]Error:[/bold red] No setup credentials found. Run provision first.")
        sys.exit(1)
    try:
        data = json.loads(cred_path.read_text())
        did = data.get("device_id")
        if not did:
            console.print("[bold red]Error:[/bold red] device_id not in credentials.")
            sys.exit(1)
        print(did)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
