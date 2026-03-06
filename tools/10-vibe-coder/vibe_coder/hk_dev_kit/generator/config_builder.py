"""Build environment configuration for selected HK integrations."""

from __future__ import annotations


_INTEGRATION_CONFIG: dict[str, dict] = {
    "fps": {
        "env_vars": {
            "FPS_BANK_API_URL": "Bank FPS API base URL",
            "FPS_API_KEY": "Bank FPS API key / bearer token",
            "FPS_PROXY_TYPE": "Default FPS proxy type (mobile, fps_id, email, br_number)",
            "FPS_PROXY_ID": "Default FPS proxy identifier for receiving payments",
        },
        "defaults": {
            "FPS_PROXY_TYPE": "mobile",
        },
    },
    "octopus": {
        "env_vars": {
            "OCTOPUS_API_URL": "Octopus merchant API base URL",
            "OCTOPUS_API_KEY": "Octopus merchant API key",
            "OCTOPUS_MERCHANT_ID": "Your Octopus merchant ID",
        },
        "defaults": {
            "OCTOPUS_API_URL": "https://api.octopus.com.hk/merchant/v1",
        },
    },
    "govhk_weather": {
        "env_vars": {
            "GOVHK_WEATHER_CACHE_TTL": "Weather API cache TTL in seconds (default 300)",
        },
        "defaults": {
            "GOVHK_WEATHER_CACHE_TTL": "300",
        },
    },
    "govhk_transport": {
        "env_vars": {
            "GOVHK_TRANSPORT_CACHE_TTL": "Transport API cache TTL in seconds (default 120)",
        },
        "defaults": {
            "GOVHK_TRANSPORT_CACHE_TTL": "120",
        },
    },
    "govhk_geodata": {
        "env_vars": {
            "GOVHK_GEO_CACHE_TTL": "Geo data cache TTL in seconds (default 600)",
        },
        "defaults": {
            "GOVHK_GEO_CACHE_TTL": "600",
        },
    },
}


class ConfigBuilder:
    """Build the configuration dictionary for a set of HK integrations."""

    def build(self, integrations: list[str]) -> dict:
        """Return a merged config dict with ``env_vars`` and ``defaults``."""
        env_vars: dict[str, str] = {}
        defaults: dict[str, str] = {}

        for integration in integrations:
            cfg = _INTEGRATION_CONFIG.get(integration, {})
            env_vars.update(cfg.get("env_vars", {}))
            defaults.update(cfg.get("defaults", {}))

        return {
            "env_vars": env_vars,
            "defaults": defaults,
            "integrations": integrations,
        }

    @staticmethod
    def available_integrations() -> list[str]:
        """Return the list of supported integration names."""
        return list(_INTEGRATION_CONFIG.keys())
