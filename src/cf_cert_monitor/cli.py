"""Command-line entry point."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .checker import evaluate, expiring
from .client import CloudflareClient, CloudflareError
from .config import Config, ConfigError
from .notify import notify_slack, notify_webhook
from .report import render, write_report

# Exit codes — documented so operators can build on them.
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_API_ERROR = 2
EXIT_EXPIRING_FOUND = 3

log = logging.getLogger("cf_cert_monitor")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cf-cert-monitor",
        description="Audit Cloudflare custom-hostname SSL certs, alert Slack, emit an HTML report.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to the JSON config file (default: ./config.json)",
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        help="Override report_path from config",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        metavar="DAYS",
        help="Override expiring_soon_days from config",
    )
    parser.add_argument(
        "--no-slack",
        action="store_true",
        help="Skip Slack notifications even if a webhook is configured",
    )
    parser.add_argument("--no-webhook", action="store_true", help="Skip generic webhook notifications")
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing the HTML report",
    )
    parser.add_argument(
        "--fail-on-expiring",
        action="store_true",
        help=f"Exit {EXIT_EXPIRING_FOUND} if any cert is within the threshold (useful in CI)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    try:
        config = Config.load(args.config)
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return EXIT_CONFIG_ERROR

    threshold = args.threshold if args.threshold is not None else config.expiring_soon_days
    report_path = Path(args.report or config.report_path)

    client = CloudflareClient(config.api_token)
    try:
        zone_certs = client.collect()
    except CloudflareError as exc:
        log.error("Cloudflare API error: %s", exc)
        return EXIT_API_ERROR

    log.info(
        "Collected %d certs across %d zones",
        sum(len(zc.certs) for zc in zone_certs),
        len(zone_certs),
    )

    zone_thresholds = {} if args.threshold is not None else {
        name: policy.get("expiring_soon_days", threshold)
        for name, policy in config.zone_policies.items()
    }
    statuses = evaluate(zone_certs, threshold_days=threshold, zone_thresholds=zone_thresholds)
    soon = expiring(statuses)
    log.info("%d cert(s) within the %d-day threshold", len(soon), threshold)

    for zone_name in {status.zone_name for status in soon}:
        group = [status for status in soon if status.zone_name == zone_name]
        policy = config.zone_policies.get(zone_name, {})
        if not args.no_slack:
            notify_slack(policy.get("slack_webhook_url", config.slack_webhook_url), group)
        if not args.no_webhook:
            notify_webhook(policy.get("webhook_url", config.webhook_url), group)

    if not args.no_report:
        html = render(statuses, title=config.report_title, threshold_days=threshold)
        out = write_report(html, report_path)
        log.info("Wrote report to %s", out)

    if args.fail_on_expiring and soon:
        return EXIT_EXPIRING_FOUND
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
