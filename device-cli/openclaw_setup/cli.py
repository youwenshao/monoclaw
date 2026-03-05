#!/usr/bin/env python3
"""OpenClaw Setup CLI — provision, test, and finalize Mac devices for MonoClaw."""

import click
import sys
from rich.console import Console

console = Console()

@click.group()
@click.version_option(version="1.0.0")
def main():
    """OpenClaw device provisioning CLI for MonoClaw technicians."""
    pass


@main.command()
@click.option("--order-id", required=True, help="Supabase order UUID")
@click.option("--serial", required=True, help="Mac serial number")
@click.option("--supabase-url", envvar="SUPABASE_URL", required=True)
@click.option("--supabase-key", envvar="SUPABASE_SERVICE_KEY", required=True)
def provision(order_id: str, serial: str, supabase_url: str, supabase_key: str):
    """Set up OpenClaw on a new Mac device."""
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
@click.confirmation_option(prompt="This will permanently remove the setup CLI. Continue?")
def finalize(device_id: str, supabase_url: str, supabase_key: str):
    """Finalize setup and self-destruct the CLI tool."""
    from .self_destruct import SelfDestruct

    console.print("[bold red]MonoClaw Finalizer[/bold red]")

    destroyer = SelfDestruct(
        device_id=device_id,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )
    destroyer.run()


if __name__ == "__main__":
    main()
