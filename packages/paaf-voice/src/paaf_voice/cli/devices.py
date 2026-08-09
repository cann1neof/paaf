# SPDX-License-Identifier: Apache-2.0
"""Audio device management CLI command (VOICE-09)."""

from typing import Any

import click
from rich.console import Console
from rich.table import Table

from paaf_voice.cli.models import voice_cli


def get_audio_devices() -> list[dict[str, Any]]:
    """Query system audio hardware devices via sounddevice.query_devices()."""
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        results: list[dict[str, Any]] = []
        if isinstance(devices, dict):
            devices = [devices]
        for idx, dev in enumerate(devices):
            results.append(
                {
                    "index": dev.get("index", idx),
                    "name": str(dev.get("name", f"Device {idx}")),
                    "max_input_channels": int(dev.get("max_input_channels", 0)),
                    "max_output_channels": int(dev.get("max_output_channels", 0)),
                    "default_sample_rate": float(dev.get("default_samplerate", 44100.0)),
                    "is_default_input": dev.get("is_default_input", False),
                    "is_default_output": dev.get("is_default_output", False),
                }
            )
        return results
    except Exception:
        # Fallback when sounddevice or PortAudio driver is unavailable
        return []


@voice_cli.command(name="list-devices")
def list_devices_cmd() -> None:
    """List connected audio input (mic) and output (speaker) devices (VOICE-09)."""
    console = Console()
    devices = get_audio_devices()

    console.print("[bold]Connected Audio Hardware Devices[/bold] (VOICE-09)")

    if not devices:
        console.print("[yellow]No audio devices detected or PortAudio runtime unavailable.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Index", style="dim", justify="right")
    table.add_column("Device Name", style="cyan")
    table.add_column("In Ch", style="green", justify="right")
    table.add_column("Out Ch", style="green", justify="right")
    table.add_column("Sample Rate (Hz)", style="yellow", justify="right")
    table.add_column("Role", style="magenta")

    for idx, dev in enumerate(devices):
        roles = []
        if dev.get("is_default_input"):
            roles.append("Default Input")
        if dev.get("is_default_output"):
            roles.append("Default Output")
        role_str = ", ".join(roles) if roles else ""

        rate = float(dev.get("default_sample_rate", dev.get("default_samplerate", 44100.0)))
        table.add_row(
            str(dev.get("index", idx)),
            str(dev.get("name", f"Device {idx}")),
            str(dev.get("max_input_channels", 0)),
            str(dev.get("max_output_channels", 0)),
            f"{rate:.0f}",
            role_str,
        )

    console.print(table)
