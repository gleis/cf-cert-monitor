from datetime import datetime, timezone

import pytest
import responses

from cf_cert_monitor.checker import evaluate
from cf_cert_monitor.client import Certificate, Zone, ZoneCerts
from cf_cert_monitor.config import Config, ConfigError
from cf_cert_monitor.notify import notify_webhook


def test_zone_threshold_and_global_fallback():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cert = Certificate(hosts=["www.example.com"], issuer="Test", expires_on="2026-01-21T00:00:00Z")
    groups = [ZoneCerts(zone=Zone(id="a", name="a.test"), certs=[cert]), ZoneCerts(zone=Zone(id="b", name="b.test"), certs=[cert])]
    statuses = evaluate(groups, 31, now=now, zone_thresholds={"a.test": 14})
    assert not statuses[0].expiring_soon
    assert statuses[1].expiring_soon


@pytest.mark.parametrize("policies", [[], {"x": []}, {"x": {"expiring_soon_days": -1}}, {"x": {"webhook_url": []}}])
def test_invalid_policies_fail_configuration(policies):
    with pytest.raises(ConfigError):
        Config.from_dict({"api_token": "test", "zone_policies": policies})


@responses.activate
def test_generic_webhook_payload_and_non_200_success():
    cert = Certificate(hosts=["www.example.com"], issuer="Test", expires_on="2026-01-03T00:00:00Z")
    statuses = evaluate([ZoneCerts(zone=Zone(id="a", name="a.test"), certs=[cert])], 31, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    responses.post("https://example.net/alerts", status=202)
    assert notify_webhook("https://example.net/alerts", statuses) == 1
    import json
    assert json.loads(responses.calls[0].request.body)["event"] == "certificate.expiring"
    assert notify_webhook(None, statuses) == 0
