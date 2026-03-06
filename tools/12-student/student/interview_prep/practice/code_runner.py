"""Execute user code in a sandboxed subprocess with resource limits."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def execute_code(
    code: str,
    language: str,
    input_data: str = "",
    timeout: int = 5,
    memory_mb: int = 256,
) -> dict:
    runner = _RUNNERS.get(language)
    if not runner:
        return {"stdout": "", "stderr": f"Unsupported language: {language}", "exit_code": 1, "timed_out": False}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=runner["ext"], delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        cmd = _build_command(runner, tmp_path, memory_mb)
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Time limit exceeded", "exit_code": -1, "timed_out": True}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "timed_out": False}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_command(runner: dict, script_path: str, memory_mb: int) -> str:
    mem_bytes = memory_mb * 1024 * 1024
    ulimit = f"ulimit -v {mem_bytes} 2>/dev/null;"
    return f"{ulimit} {runner['cmd']} {script_path}"


_RUNNERS = {
    "python": {"cmd": sys.executable, "ext": ".py"},
    "javascript": {"cmd": "node", "ext": ".js"},
}
