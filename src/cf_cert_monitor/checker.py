"""Expiration math — pure functions, no I/O, easy to test."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .client import Certificate, ZoneCerts

# Cloudflare returns expiration as ISO-8601 with either a plain 'Z' suffix
# or sub-second precision. Support both.
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
)


def parse_expiry(value: str) -> datetime:
    """Parse a Cloudflare expiry timestamp into a timezone-aware UTC datetime."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized certificate expiry format: {value!r}")


def days_until_expiry(expires_on: str, now: datetime | None = None) -> int:
    """Return whole days between `now` (UTC) and `expires_on`. Negative if past."""
    current = now or datetime.now(timezone.utc)
    return (parse_expiry(expires_on) - current).days


@dataclass(frozen=True)
class CertStatus:
    zone_name: str
    cert: Certificate
    days_left: int
    expiring_soon: bool
    expired: bool


def evaluate(
    zone_certs: list[ZoneCerts],
    threshold_days: int,
    now: datetime | None = None,
) -> list[CertStatus]:
    """Attach expiration status to every cert and flag anything at or under threshold."""
    results: list[CertStatus] = []
    for zc in zone_certs:
        for cert in zc.certs:
            days = days_until_expiry(cert.expires_on, now=now)
            results.append(
                CertStatus(
                    zone_name=zc.zone.name,
                    cert=cert,
                    days_left=days,
                    expiring_soon=days <= threshold_days,
                    expired=days < 0,
                )
            )
    return results


def expiring(statuses: list[CertStatus]) -> list[CertStatus]:
    return [s for s in statuses if s.expiring_soon]
