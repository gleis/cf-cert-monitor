from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cf_cert_monitor.checker import (
    CertStatus,
    days_until_expiry,
    evaluate,
    expiring,
    parse_expiry,
)
from cf_cert_monitor.client import Certificate, Zone, ZoneCerts


def test_parse_expiry_plain_format():
    assert parse_expiry("2026-01-02T03:04:05Z") == datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )


def test_parse_expiry_microseconds():
    assert parse_expiry("2026-01-02T03:04:05.123456Z") == datetime(
        2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc
    )


def test_parse_expiry_unknown_format_raises():
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_expiry("not a date")


def test_days_until_expiry_future():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert days_until_expiry("2026-01-11T00:00:00Z", now=now) == 10


def test_days_until_expiry_past_is_negative():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert days_until_expiry("2025-12-25T00:00:00Z", now=now) == -7


def _cert(days_from: int, now: datetime) -> Certificate:
    from datetime import timedelta

    exp = now + timedelta(days=days_from)
    return Certificate(
        hosts=["www.example.com"],
        issuer="Example CA",
        expires_on=exp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def test_evaluate_classifies_correctly():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    zone = Zone(id="z1", name="example.com")
    zc = ZoneCerts(
        zone=zone,
        certs=[_cert(-1, now), _cert(5, now), _cert(90, now)],
    )
    out = evaluate([zc], threshold_days=30, now=now)
    assert [s.expired for s in out] == [True, False, False]
    assert [s.expiring_soon for s in out] == [True, True, False]


def test_expiring_filter():
    statuses = [
        CertStatus(zone_name="a", cert=_cert(0, datetime.now(timezone.utc)), days_left=1, expiring_soon=True, expired=False),
        CertStatus(zone_name="b", cert=_cert(0, datetime.now(timezone.utc)), days_left=100, expiring_soon=False, expired=False),
    ]
    out = expiring(statuses)
    assert len(out) == 1
    assert out[0].zone_name == "a"
