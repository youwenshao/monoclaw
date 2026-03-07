import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path("/opt/openclaw/state/onboarding.json")


def _read_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def _write_state(state: dict) -> dict:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))
    return state


def _default_state() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "phase": 0,
        "step": 0,
        "completed_phases": [],
        "profile": None,
        "voice_enabled": True,
        "onboarding_completed": False,
        "created_at": now,
        "updated_at": now,
    }


def get_onboarding_state() -> dict:
    state = _read_state()
    if not state.get("created_at"):
        state = _default_state()
        _write_state(state)
    return state


def get_profile() -> dict:
    state = _read_state()
    return state.get("profile") or {}


def save_profile(data: dict) -> dict:
    state = _read_state()
    state["profile"] = data
    return _write_state(state)


def update_progress(phase: int, step: int, completed: bool) -> dict:
    state = _read_state()
    state["phase"] = phase
    state["step"] = step
    if completed and phase not in state.get("completed_phases", []):
        state.setdefault("completed_phases", []).append(phase)
    return _write_state(state)


def mark_complete() -> dict:
    state = _read_state()
    state["onboarding_completed"] = True
    return _write_state(state)
