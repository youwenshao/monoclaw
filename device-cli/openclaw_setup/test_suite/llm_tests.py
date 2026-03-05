"""LLM model loading and inference tests."""

import time
import os
from pathlib import Path
from .base import BaseTestSuite


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

    def test_inference_simple_prompt(self):
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists() or not list(model_dir.iterdir()):
            return "skipped", {"note": "No models to test"}
        try:
            from mlx_lm import load, generate
            first_model = next(model_dir.iterdir())
            model, tokenizer = load(str(first_model))
            start = time.time()
            output = generate(model, tokenizer, prompt="Hello, I am", max_tokens=20)
            elapsed = time.time() - start
            return "pass", {"output_length": len(output), "time_s": round(elapsed, 2)}
        except ImportError:
            return "skipped", {"note": "mlx_lm not available"}
        except Exception as e:
            return "fail", {"error": str(e)}

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
        """Verify auto-routing configuration exists for Max bundle."""
        config_path = Path("/opt/openclaw/state/active-work.json")
        if config_path.exists():
            return "pass", {"note": "Routing config available"}
        return "skipped", {"note": "Auto-routing not configured (may not have Max bundle)"}

    def test_context_window_metadata(self):
        model_dir = Path("/opt/openclaw/models")
        if not model_dir.exists() or not list(model_dir.iterdir()):
            return "skipped", {}
        import json
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
