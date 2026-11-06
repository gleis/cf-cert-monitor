"""Load and validate configuration from a JSON file."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or invalid."""


@dataclass(frozen=True)
class Config:
    api_token: str
    expiring_soon_days: int = 31
    slack_webhook_url: str | None = None
    report_path: str = "reports/cfcert_report.html"
    report_title: str = "Cloudflare Certificate Report"
    webhook_url: str | None = None
    zone_policies: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        if "api_token" not in data or not data["api_token"]:
            raise ConfigError("'api_token' is required")

        days = data.get("expiring_soon_days", 31)
        if not isinstance(days, int) or days < 0:
            raise ConfigError("'expiring_soon_days' must be a non-negative integer")

        policies = data.get("zone_policies", {})
        if not isinstance(policies, dict):
            raise ConfigError("'zone_policies' must be an object keyed by zone name")
        for name, policy in policies.items():
            if not isinstance(name, str) or not isinstance(policy, dict):
                raise ConfigError("Each zone policy must be an object")
            threshold = policy.get("expiring_soon_days", days)
            if type(threshold) is not int or threshold < 0:
                raise ConfigError("Zone thresholds must be non-negative integers")
            for route in ("slack_webhook_url", "webhook_url"):
                if route in policy and policy[route] is not None and not isinstance(policy[route], str):
                    raise ConfigError(f"Zone {route} must be a URL string or null")

        return cls(
            api_token=str(data["api_token"]),
            expiring_soon_days=days,
            slack_webhook_url=data.get("slack_webhook_url") or None,
            report_path=data.get("report_path", "reports/cfcert_report.html"),
            report_title=data.get("report_title", "Cloudflare Certificate Report"),
            webhook_url=data.get("webhook_url") or None,
            zone_policies=policies,
        )

    @classmethod
    def load(cls, path: str | Path) -> Config:
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Config file is not valid JSON: {exc}") from exc

        # Environment overrides (handy for CI / containers)
        if token := os.environ.get("CF_API_TOKEN"):
            data["api_token"] = token
        if url := os.environ.get("CF_SLACK_WEBHOOK_URL"):
            data["slack_webhook_url"] = url

        return cls.from_dict(data)
