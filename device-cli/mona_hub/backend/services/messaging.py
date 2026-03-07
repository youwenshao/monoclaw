import json
from pathlib import Path

MESSAGING_DIR = Path("/opt/openclaw/config/messaging")


def get_messaging_config() -> dict:
    configs = {}
    if not MESSAGING_DIR.exists():
        return configs
    for f in MESSAGING_DIR.glob("*.json"):
        try:
            configs[f.stem] = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return configs


def save_messaging_config(platform: str, config: dict):
    MESSAGING_DIR.mkdir(parents=True, exist_ok=True)
    path = MESSAGING_DIR / f"{platform}.json"
    path.write_text(json.dumps(config, indent=2))
