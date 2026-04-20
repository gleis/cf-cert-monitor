from __future__ import annotations

import json

import pytest

from cf_cert_monitor.config import Config, ConfigError


def test_from_dict_minimal():
    cfg = Config.from_dict({"api_token": "tok"})
    assert cfg.api_token == "tok"
    assert cfg.expiring_soon_days == 31
    assert cfg.slack_webhook_url is None


def test_from_dict_full():
    cfg = Config.from_dict(
        {
            "api_token": "tok",
            "expiring_soon_days": 7,
            "slack_webhook_url": "https://example.com/hook",
            "report_path": "/tmp/out.html",
            "report_title": "Prod Certs",
        }
    )
    assert cfg.expiring_soon_days == 7
    assert cfg.slack_webhook_url == "https://example.com/hook"
    assert cfg.report_path == "/tmp/out.html"
    assert cfg.report_title == "Prod Certs"


def test_missing_token_raises():
    with pytest.raises(ConfigError, match="api_token"):
        Config.from_dict({})


def test_negative_threshold_raises():
    with pytest.raises(ConfigError, match="non-negative"):
        Config.from_dict({"api_token": "tok", "expiring_soon_days": -1})


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.json")


def test_load_invalid_json(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text("{not json")
    with pytest.raises(ConfigError, match="not valid JSON"):
        Config.load(bad)


def test_env_overrides(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_token": "from-file"}))
    monkeypatch.setenv("CF_API_TOKEN", "from-env")
    monkeypatch.setenv("CF_SLACK_WEBHOOK_URL", "https://env.example/hook")
    cfg = Config.load(path)
    assert cfg.api_token == "from-env"
    assert cfg.slack_webhook_url == "https://env.example/hook"
