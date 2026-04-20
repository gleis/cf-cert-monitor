"""Slack webhook notifier."""
from __future__ import annotations

import logging

import requests

from .checker import CertStatus

log = logging.getLogger(__name__)


def build_slack_payload(status: CertStatus) -> dict:
    """Build the Slack Block Kit payload for one expiring certificate."""
    header = (
        "SSL certificate expired"
        if status.expired
        else f"SSL certificate expiring in {status.days_left} days"
    )
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Zone:*\n{status.zone_name}"},
                    {"type": "mrkdwn", "text": f"*Days left:*\n{status.days_left}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Hostnames:*\n{', '.join(status.cert.hosts) or '(none)'}",
                    },
                    {"type": "mrkdwn", "text": f"*Expires:*\n{status.cert.expires_on}"},
                    {"type": "mrkdwn", "text": f"*Issuer:*\n{status.cert.issuer}"},
                ],
            },
        ]
    }


def notify_slack(
    webhook_url: str | None,
    statuses: list[CertStatus],
    *,
    session: requests.Session | None = None,
    timeout: int = 10,
) -> int:
    """POST one Slack message per expiring cert. Returns the count successfully sent."""
    if not webhook_url:
        log.info("No slack_webhook_url configured — skipping notifications.")
        return 0
    if not statuses:
        return 0

    http = session or requests.Session()
    sent = 0
    for status in statuses:
        try:
            resp = http.post(webhook_url, json=build_slack_payload(status), timeout=timeout)
            if resp.status_code != 200:
                log.warning(
                    "Slack responded %s for %s: %s",
                    resp.status_code,
                    status.zone_name,
                    resp.text[:200],
                )
                continue
            sent += 1
        except requests.RequestException as exc:
            log.warning("Slack POST failed for %s: %s", status.zone_name, exc)
    return sent
