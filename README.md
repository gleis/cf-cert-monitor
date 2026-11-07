# cf-cert-monitor

Audit every Cloudflare custom-hostname SSL certificate on your account, alert Slack when anything is close to expiring, and publish an HTML dashboard you can pin to your ops channel or stick behind a basic-auth URL.

Built because "did that cert renew?" is a question nobody should have to answer manually at 11pm.

## What it does

- Walks every zone on your Cloudflare account, paginated.
- For each zone, pulls every custom-hostname SSL certificate.
- Flags anything inside a configurable threshold (default: 31 days).
- Posts a Slack Block Kit message per expiring cert to a webhook.
- Renders a sortable Bootstrap + DataTables HTML report with summary tiles for healthy / expiring / expired.
- Returns a non-zero exit code when `--fail-on-expiring` is set, so it slots into CI or a cron with a wrapper.

## Quickstart

```bash
git clone https://github.com/gleis/cf-cert-monitor
cd cf-cert-monitor
python -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock
pip install --no-deps -e .

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/cf-cert-monitor"
mkdir -p "$config_dir"
cp config.example.json "$config_dir/config.json"
chmod 600 "$config_dir/config.json"
# Edit this local file to add your Cloudflare API token and optional webhook.

./scripts/check-local.sh
```

Want to see what the HTML report looks like before connecting a real account? Run the demo:

```bash
python examples/generate_sample.py
open examples/sample_report.html
```

## Configuration

`config.json`:

| Key                  | Required | Default                           | Notes                                         |
| -------------------- | -------- | --------------------------------- | --------------------------------------------- |
| `api_token`          | yes      | —                                 | Cloudflare API token with Zone:Read + SSL:Read |
| `expiring_soon_days` | no       | `31`                              | Days-ahead threshold for alerts                |
| `slack_webhook_url`  | no       | —                                 | Incoming webhook; omit to disable Slack        |
| `report_path`        | no       | `reports/cfcert_report.html`      | Where to write the HTML report                 |
| `report_title`       | no       | `Cloudflare Certificate Report`   | Shown at the top of the report                 |

Environment overrides (useful in CI / containers):

- `CF_API_TOKEN` overrides `api_token`
- `CF_SLACK_WEBHOOK_URL` overrides `slack_webhook_url`

## CLI

```
cf-cert-monitor [-c CONFIG] [--report PATH] [--threshold DAYS]
                [--no-slack] [--no-report] [--fail-on-expiring] [-v]
```

Exit codes:

- `0` — everything healthy (or at least no failures flagged)
- `1` — config error
- `2` — Cloudflare API error
- `3` — `--fail-on-expiring` was set and at least one cert is within the threshold

## Running on a schedule

Run checks on your own computer or private server. Keep the token in a local configuration file outside the checkout, for example `~/.config/cf-cert-monitor/config.json`, and restrict its permissions with `chmod 600`. Create the repository's `.venv` and install the package before scheduling.

The local wrapper uses that configuration and a private working directory under `~/.local/state/cf-cert-monitor`. It preserves the monitor's exit status. Override the paths with `CF_CERT_MONITOR_CONFIG` and `CF_CERT_MONITOR_STATE_DIR` when needed.

Cron example (daily at 7am; replace the checkout path):

```
0 7 * * * /absolute/path/cf-cert-monitor/scripts/check-local.sh
```

GitHub Actions runs tests and dependency checks only. Live account monitoring runs locally; no Cloudflare token or hostname inventory is needed in GitHub. Scheduling requires an awake computer or a private server. The Cloudflare API integration checks Cloudflare for SaaS custom-hostname certificates; it does not inventory ordinary zone edge certificates.

## Project layout

```
src/cf_cert_monitor/
  config.py     # JSON + env config loader with validation
  client.py     # Cloudflare API client (pagination, retries, typed dataclasses)
  checker.py    # Pure expiration math — easy to test
  notify.py     # Slack Block Kit notifier
  report.py     # Jinja2-rendered HTML dashboard
  cli.py        # argparse entry point with documented exit codes
  templates/
    report.html
tests/          # pytest with responses mocking the Cloudflare API
```

The core decisions that are worth calling out:

- **Pagination is real.** Cloudflare caps results per page; the previous version of this script silently lost zones past the first 50. `client._paginate` walks every page.
- **Retries are on by default** for 429 and 5xx with exponential backoff.
- **Expiration math is pure.** `checker.py` takes no config, touches no network, and has an injectable `now` so tests can assert exact day counts across DST and leap-year edges.
- **Templates are escaped.** Swapped hand-rolled HTML concatenation for a Jinja2 template with autoescape on, so a weird zone name can't break the report.

## Development

```bash
pip install -e ".[dev]"
pytest              # run the suite
ruff check .        # lint
```

## License

MIT — see [LICENSE](LICENSE).

## Zone thresholds and routing

Optional `zone_policies` is keyed by exact zone name. Each entry can set `expiring_soon_days`, `slack_webhook_url`, and `webhook_url`. Missing routes inherit global settings; null disables that route for the zone. Global `webhook_url` sends vendor-neutral JSON events (`event`, `zone`, `hosts`, `expires_on`, `days_left`, `issuer`). `--threshold` overrides every zone threshold; `--no-webhook` and `--no-slack` independently disable delivery. Report status colors use each zone's threshold; the header shows the default threshold.

```json
{"api_token":"use CF_API_TOKEN instead","expiring_soon_days":31,"zone_policies":{"example.com":{"expiring_soon_days":14,"slack_webhook_url":null,"webhook_url":"https://example.net/alerts"}}}
```
