"""HTML report generation using Jinja2."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .checker import CertStatus

_env = Environment(
    loader=PackageLoader("cf_cert_monitor", "templates"),
    autoescape=select_autoescape(("html",)),
)


def render(
    statuses: list[CertStatus],
    *,
    title: str,
    threshold_days: int,
    generated_at: datetime | None = None,
) -> str:
    generated = (generated_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")
    zone_count = len({s.zone_name for s in statuses})
    expired_count = sum(1 for s in statuses if s.expired)
    expiring_count = sum(1 for s in statuses if s.expiring_soon and not s.expired)
    healthy_count = len(statuses) - expired_count - expiring_count

    template = _env.get_template("report.html")
    return template.render(
        title=title,
        generated_at=generated,
        threshold_days=threshold_days,
        statuses=sorted(statuses, key=lambda s: s.days_left),
        zone_count=zone_count,
        expired_count=expired_count,
        expiring_count=expiring_count,
        healthy_count=healthy_count,
    )


def write_report(html: str, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
