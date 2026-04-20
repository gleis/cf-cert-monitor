from __future__ import annotations

import responses

from cf_cert_monitor.checker import CertStatus
from cf_cert_monitor.client import Certificate
from cf_cert_monitor.notify import build_slack_payload, notify_slack


def _status(days: int, *, expired: bool = False) -> CertStatus:
    return CertStatus(
        zone_name="example.com",
        cert=Certificate(
            hosts=["www.example.com"],
            issuer="Example CA",
            expires_on="2026-09-01T00:00:00Z",
        ),
        days_left=days,
        expiring_soon=True,
        expired=expired,
    )


def test_build_slack_payload_shape():
    payload = build_slack_payload(_status(5))
    assert payload["blocks"][0]["type"] == "header"
    assert "expiring in 5 days" in payload["blocks"][0]["text"]["text"]
    fields = {f["text"] for f in payload["blocks"][1]["fields"]}
    assert any("example.com" in f for f in fields)
    assert any("www.example.com" in f for f in fields)


def test_build_slack_payload_expired_wording():
    payload = build_slack_payload(_status(-3, expired=True))
    assert "expired" in payload["blocks"][0]["text"]["text"].lower()


def test_notify_slack_no_webhook_returns_zero():
    assert notify_slack(None, [_status(5)]) == 0


def test_notify_slack_empty_list_returns_zero():
    assert notify_slack("https://hooks.slack.com/services/x/y/z", []) == 0


@responses.activate
def test_notify_slack_posts_each_status():
    url = "https://hooks.slack.com/services/x/y/z"
    responses.add(responses.POST, url, status=200)
    responses.add(responses.POST, url, status=200)
    sent = notify_slack(url, [_status(5), _status(10)])
    assert sent == 2
    assert len(responses.calls) == 2


@responses.activate
def test_notify_slack_counts_only_successes():
    url = "https://hooks.slack.com/services/x/y/z"
    responses.add(responses.POST, url, status=500)
    responses.add(responses.POST, url, status=200)
    sent = notify_slack(url, [_status(5), _status(10)])
    assert sent == 1
