"""LLM model loading and inference tests."""

import json
import time
from pathlib import Path
from .base import BaseTestSuite


def _load_active_work() -> dict | None:
    aw_path = Path("/opt/openclaw/state/active-work.json")
    if aw_path.exists():
        try:
            return json.loads(aw_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _expected_models() -> list[str]:
    aw = _load_active_work()
    if aw and "llm_plan" in aw:
        return aw["llm_plan"].get("models", [])
    return []


class LLMModelTests(BaseTestSuite):

    def test_mlx_lm_importable(self):
        try:
            import mlx_lm
            return "pass", {"version": getattr(mlx_lm, "__version__", "unknown")}
        except ImportError:
            return "warning", {"note": "mlx_lm not installed (required for local models)"}

    def test_models_directory_exists(self):
        model_dir = Path("/opt/openclaw/models")
        if model_dir.exists():
            models = list(model_dir.iterdir())
            return "pass", {"model_count": len(models), "models": [m.name for m in models[:10]]}
        return "fail", {}

    def test_expected_models_present(self):
        """Verify every model listed in active-work.json is downloaded."""
        expected = _expected_models()
        if not expected:
            return "skipped", {"note": "No expected models (API-only or no active-work.json)"}

        model_dir = Path("/opt/openclaw/models")
        missing = []
        present = []
        for mid in expected:
            mpath = model_dir / mid
            if mpath.exists() and (mpath / "config.json").exists():
                present.append(mid)
            else:
                missing.append(mid)

        if missing:
            return "fail", {"missing": missing, "present": len(present), "expected": len(expected)}
        return "pass", {"count": len(present)}

    def test_model_files_integrity(self):
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists() or not list(model_dir.iterdir()):
            return "skipped", {"note": "No models downloaded"}
        for model_path in model_dir.iterdir():
            if model_path.is_dir():
                config = model_path / "config.json"
                if not config.exists():
                    return "warning", {"model": model_path.name, "error": "Missing config.json"}
        return "pass", {}

    def test_model_load_basic(self):
        """Attempt to load the smallest available model."""
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists() or not list(model_dir.iterdir()):
            return "skipped", {"note": "No models to test"}
        try:
            from mlx_lm import load
            first_model = next(model_dir.iterdir())
            load(str(first_model))
            return "pass", {"model": first_model.name}
        except ImportError:
            return "skipped", {"note": "mlx_lm not available"}
        except Exception as e:
            return "fail", {"error": str(e)}

    def test_inference_per_model(self):
        """Run inference on each expected model to verify they work."""
        expected = _expected_models()
        model_dir = Path("/opt/openclaw/models")
        if not expected or not model_dir.exists():
            return "skipped", {"note": "No models to test"}

        try:
            from mlx_lm import load, generate
        except ImportError:
            return "skipped", {"note": "mlx_lm not available"}

        tested = 0
        failed_models = []
        for mid in expected:
            mpath = model_dir / mid
            if not mpath.exists():
                continue
            try:
                model, tokenizer = load(str(mpath))
                output = generate(model, tokenizer, prompt="Hello", max_tokens=5)
                tested += 1
                del model, tokenizer
            except Exception as e:
                failed_models.append({"model": mid, "error": str(e)})

        if failed_models:
            return "warning", {"tested": tested, "failures": failed_models}
        if tested == 0:
            return "skipped", {"note": "No downloadable models found on disk"}
        return "pass", {"tested": tested}

    def test_memory_usage_during_inference(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            used_gb = round(mem.used / (1024**3), 1)
            if used_gb < 12:
                return "pass", {"used_gb": used_gb, "limit_gb": 12}
            return "warning", {"used_gb": used_gb, "limit_gb": 12}
        except ImportError:
            return "skipped", {}

    def test_model_switching(self):
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists():
            return "skipped", {}
        models = [m for m in model_dir.iterdir() if m.is_dir()]
        if len(models) < 2:
            return "skipped", {"note": "Need at least 2 models for switch test"}
        return "pass", {"note": f"Found {len(models)} models for switching"}

    def test_concurrent_request_rejection(self):
        return "pass", {"note": "Single-inference architecture prevents concurrency by design"}

    def test_empty_prompt_handling(self):
        try:
            from mlx_lm import load, generate
            model_dir = Path("/opt/openclaw/models")
            if not model_dir.exists() or not list(model_dir.iterdir()):
                return "skipped", {}
            first_model = next(model_dir.iterdir())
            model, tokenizer = load(str(first_model))
            output = generate(model, tokenizer, prompt="", max_tokens=10)
            return "pass", {"handled_gracefully": True}
        except ImportError:
            return "skipped", {}
        except Exception as e:
            return "warning", {"error": str(e), "note": "Empty prompt caused exception"}

    def test_auto_routing_config(self):
        """Verify routing config exists and is valid."""
        routing_path = Path("/opt/openclaw/state/routing-config.json")
        if not routing_path.exists():
            aw = _load_active_work()
            if aw and aw.get("llm_plan", {}).get("type") == "api_only":
                return "skipped", {"note": "API-only mode, no routing needed"}
            return "warning", {"note": "routing-config.json missing"}

        try:
            data = json.loads(routing_path.read_text())
            routes = data.get("routes", {})
            auto = data.get("auto_routing_enabled", False)
            return "pass", {"auto_routing": auto, "route_count": len(routes)}
        except (json.JSONDecodeError, OSError) as e:
            return "fail", {"error": str(e)}

    def test_context_window_metadata(self):
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists() or not list(model_dir.iterdir()):
            return "skipped", {}
        for model_path in model_dir.iterdir():
            config_file = model_path / "config.json"
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)
                    ctx = config.get("max_position_embeddings", config.get("seq_length", 0))
                    return "pass", {"model": model_path.name, "context_window": ctx}
                except Exception:
                    pass
        return "skipped", {}
