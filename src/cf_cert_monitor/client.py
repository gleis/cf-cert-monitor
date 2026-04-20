"""Thin Cloudflare API client — only the endpoints we need."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT = 15
DEFAULT_PAGE_SIZE = 50


class CloudflareError(Exception):
    """Raised for any non-2xx response or transport error from the Cloudflare API."""


@dataclass
class Zone:
    id: str
    name: str


@dataclass
class Certificate:
    hosts: list[str]
    issuer: str
    expires_on: str  # ISO-8601 string as returned by Cloudflare


@dataclass
class ZoneCerts:
    zone: Zone
    certs: list[Certificate] = field(default_factory=list)


def _make_session(api_token: str) -> requests.Session:
    """Build a requests session with sane retries and auth headers baked in."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
    )
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class CloudflareClient:
    """Fetches zones and custom-hostname certificates from the Cloudflare API."""

    def __init__(
        self,
        api_token: str,
        base_url: str = CLOUDFLARE_API,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or _make_session(api_token)

    # --- internal helpers -------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CloudflareError(f"Request to {url} failed: {exc}") from exc
        if resp.status_code != 200:
            raise CloudflareError(
                f"GET {url} returned {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    def _paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every `result` item across all pages for a Cloudflare list endpoint."""
        page = 1
        while True:
            merged = {"page": page, "per_page": DEFAULT_PAGE_SIZE}
            if params:
                merged.update(params)
            body = self._get(path, params=merged)
            yield from (body.get("result", []) or [])
            info = body.get("result_info") or {}
            total_pages = info.get("total_pages", 1)
            if page >= total_pages:
                return
            page += 1

    # --- public API -------------------------------------------------------

    def list_zones(self) -> list[Zone]:
        return [Zone(id=item["id"], name=item["name"]) for item in self._paginate("/zones")]

    def list_custom_hostname_certs(self, zone: Zone) -> list[Certificate]:
        certs: list[Certificate] = []
        for item in self._paginate(f"/zones/{zone.id}/custom_hostnames"):
            ssl = item.get("ssl") or {}
            hosts = ssl.get("hosts") or []
            for cert in ssl.get("certificates") or []:
                expires_on = cert.get("expires_on")
                if not expires_on:
                    continue
                certs.append(
                    Certificate(
                        hosts=list(hosts),
                        issuer=cert.get("issuer", "unknown"),
                        expires_on=expires_on,
                    )
                )
        return certs

    def collect(self) -> list[ZoneCerts]:
        """Return every zone with any custom-hostname certs attached."""
        results: list[ZoneCerts] = []
        for zone in self.list_zones():
            try:
                certs = self.list_custom_hostname_certs(zone)
            except CloudflareError as exc:
                log.warning("Skipping zone %s: %s", zone.name, exc)
                continue
            if certs:
                results.append(ZoneCerts(zone=zone, certs=certs))
        return results
