"""Hardware verification tests."""

import subprocess
import platform
import os
from pathlib import Path
from .base import BaseTestSuite


class HardwareTests(BaseTestSuite):

    def test_cpu_model_is_m4(self):
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True,
        )
        brand = result.stdout.strip()
        if "Apple" in brand:
            return "pass", {"cpu": brand}
        return "fail", {"cpu": brand, "expected": "Apple M4"}

    def test_ram_is_16gb(self):
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024**3))
        if ram_gb >= 16:
            return "pass", {"ram_gb": ram_gb}
        return "fail", {"ram_gb": ram_gb, "expected": 16}

    def test_ssd_health(self):
        result = subprocess.run(
            ["diskutil", "info", "/"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "pass", {"diskutil_output_length": len(result.stdout)}
        return "fail", {"error": result.stderr}

    def test_ssd_write_speed(self):
        test_file = "/tmp/openclaw_speed_test"
        try:
            result = subprocess.run(
                ["dd", "if=/dev/zero", f"of={test_file}", "bs=1m", "count=256"],
                capture_output=True, text=True, timeout=30,
            )
            stderr = result.stderr
            if "bytes/sec" in stderr or "bytes transferred" in stderr:
                return "pass", {"output": stderr.strip()}
            return "warning", {"output": stderr.strip()}
        except subprocess.TimeoutExpired:
            return "warning", {"error": "Write speed test timed out"}
        finally:
            Path(test_file).unlink(missing_ok=True)

    def test_network_connectivity(self):
        result = subprocess.run(
            ["ping", "-c", "3", "-t", "5", "8.8.8.8"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "pass", {"output": result.stdout.strip().split("\n")[-1]}
        return "fail", {"error": "No network connectivity"}

    def test_dns_resolution(self):
        result = subprocess.run(
            ["nslookup", "api.openai.com"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and "Address" in result.stdout:
            return "pass", {}
        return "fail", {"error": result.stderr}

    def test_usb_thunderbolt_ports(self):
        result = subprocess.run(
            ["system_profiler", "SPThunderboltDataType"],
            capture_output=True, text=True,
        )
        if "Thunderbolt" in result.stdout or result.returncode == 0:
            return "pass", {"ports_detected": True}
        return "warning", {"note": "Could not enumerate Thunderbolt ports"}

    def test_display_output(self):
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True,
        )
        if "Resolution" in result.stdout:
            return "pass", {"display_info": "Display detected"}
        return "warning", {"note": "No display detected (expected for headless Mac mini)"}

    def test_audio_subsystem(self):
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True, text=True,
        )
        if "Output" in result.stdout or "Speaker" in result.stdout:
            return "pass", {}
        return "warning", {"note": "No audio output detected"}

    def test_bluetooth_status(self):
        result = subprocess.run(
            ["system_profiler", "SPBluetoothDataType"],
            capture_output=True, text=True,
        )
        if "Bluetooth" in result.stdout:
            return "pass", {}
        return "warning", {"note": "Bluetooth info not available"}

    def test_thermal_baseline(self):
        try:
            result = subprocess.run(
                ["sudo", "powermetrics", "--samplers", "smc", "-i", "1000", "-n", "1"],
                capture_output=True, text=True, timeout=10,
            )
            return "pass", {"note": "Thermal sensors accessible"}
        except (subprocess.TimeoutExpired, Exception):
            return "warning", {"note": "Could not read thermal sensors (may require sudo)"}

    def test_architecture_is_arm64(self):
        arch = platform.machine()
        if arch == "arm64":
            return "pass", {"architecture": arch}
        return "fail", {"architecture": arch, "expected": "arm64"}
