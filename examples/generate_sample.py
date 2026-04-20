"""Generate a sample HTML report from fake data for screenshots / demos."""
from datetime import datetime, timedelta, timezone

from cf_cert_monitor.checker import CertStatus
from cf_cert_monitor.client import Certificate
from cf_cert_monitor.report import render, write_report

now = datetime(2026, 4, 18, tzinfo=timezone.utc)


def cert(hosts, days, issuer="Let's Encrypt"):
    exp = (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Certificate(hosts=hosts, issuer=issuer, expires_on=exp)


fake = [
    CertStatus("apple.com", cert(["apple.com"], 9, "Google Trust Services"), 9, True, False),
    CertStatus("google.com", cert(["google.com"], 3), 3, True, False),
    CertStatus("oldsite.example", cert(["old.example.com"], -5), -5, True, True),
]

html = render(fake, title="Cloudflare Certificate Report (sample)", threshold_days=31, generated_at=now)
write_report(html, "sample_report.html")
print("wrote sample_report.html")
