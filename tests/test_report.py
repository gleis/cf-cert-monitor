from __future__ import annotations

from datetime import datetime, timezone

from cf_cert_monitor.checker import CertStatus
from cf_cert_monitor.client import Certificate
from cf_cert_monitor.report import render, write_report


def _status(zone: str, days: int, expired: bool = False) -> CertStatus:
    return CertStatus(
        zone_name=zone,
        cert=Certificate(
            hosts=[f"www.{zone}"],
            issuer="Test CA",
            expires_on="2026-09-01T00:00:00Z",
        ),
        days_left=days,
        expiring_soon=(days <= 30),
        expired=expired,
    )


def test_render_contains_summary_and_rows():
    statuses = [
        _status("good.com", 200),
        _status("soon.com", 10),
        _status("dead.com", -1, expired=True),
    ]
    html = render(
        statuses,
        title="My Certs",
        threshold_days=30,
        generated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )
    assert "My Certs" in html
    assert "2026-04-18" in html
    for zone in ("good.com", "soon.com", "dead.com"):
        assert zone in html
    # Summary tiles should show correct counts
    assert ">1<" in html  # expired
    assert "3" in html    # total


def test_render_escapes_html():
    statuses = [
        CertStatus(
            zone_name="<script>alert(1)</script>",
            cert=Certificate(
                hosts=["<script>"],
                issuer="Test CA",
                expires_on="2026-09-01T00:00:00Z",
            ),
            days_left=10,
            expiring_soon=True,
            expired=False,
        )
    ]
    html = render(statuses, title="T", threshold_days=30)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_report_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "out.html"
    path = write_report("<html>hi</html>", target)
    assert path.exists()
    assert path.read_text() == "<html>hi</html>"
