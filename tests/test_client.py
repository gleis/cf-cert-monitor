from __future__ import annotations

import pytest
import responses

from cf_cert_monitor.client import CLOUDFLARE_API, CloudflareClient, CloudflareError


def _zones_page(page: int, total_pages: int, zones: list[dict]) -> dict:
    return {
        "success": True,
        "result": zones,
        "result_info": {"page": page, "total_pages": total_pages},
    }


@responses.activate
def test_list_zones_paginates():
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones",
        json=_zones_page(1, 2, [{"id": "z1", "name": "one.com"}]),
        match=[responses.matchers.query_param_matcher({"page": "1", "per_page": "50"})],
    )
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones",
        json=_zones_page(2, 2, [{"id": "z2", "name": "two.com"}]),
        match=[responses.matchers.query_param_matcher({"page": "2", "per_page": "50"})],
    )

    client = CloudflareClient("token")
    zones = client.list_zones()
    assert [z.id for z in zones] == ["z1", "z2"]
    assert [z.name for z in zones] == ["one.com", "two.com"]


@responses.activate
def test_list_custom_hostname_certs_extracts_fields():
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones/z1/custom_hostnames",
        json={
            "success": True,
            "result": [
                {
                    "ssl": {
                        "hosts": ["a.example.com", "b.example.com"],
                        "certificates": [
                            {"issuer": "Let's Encrypt", "expires_on": "2026-09-01T00:00:00Z"}
                        ],
                    }
                },
                {"ssl": {"hosts": ["c.example.com"], "certificates": []}},
            ],
            "result_info": {"page": 1, "total_pages": 1},
        },
    )

    client = CloudflareClient("token")
    from cf_cert_monitor.client import Zone

    certs = client.list_custom_hostname_certs(Zone(id="z1", name="example.com"))
    assert len(certs) == 1
    assert certs[0].hosts == ["a.example.com", "b.example.com"]
    assert certs[0].issuer == "Let's Encrypt"
    assert certs[0].expires_on == "2026-09-01T00:00:00Z"


@responses.activate
def test_non_200_raises_cloudflare_error():
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones",
        json={"success": False, "errors": [{"message": "bad token"}]},
        status=403,
    )
    client = CloudflareClient("token")
    with pytest.raises(CloudflareError, match="403"):
        client.list_zones()


@responses.activate
def test_collect_skips_zones_without_certs():
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones",
        json=_zones_page(
            1, 1, [{"id": "z1", "name": "has.com"}, {"id": "z2", "name": "empty.com"}]
        ),
    )
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones/z1/custom_hostnames",
        json={
            "success": True,
            "result": [
                {
                    "ssl": {
                        "hosts": ["x.has.com"],
                        "certificates": [
                            {"issuer": "CA", "expires_on": "2026-09-01T00:00:00Z"}
                        ],
                    }
                }
            ],
            "result_info": {"page": 1, "total_pages": 1},
        },
    )
    responses.add(
        responses.GET,
        f"{CLOUDFLARE_API}/zones/z2/custom_hostnames",
        json={"success": True, "result": [], "result_info": {"page": 1, "total_pages": 1}},
    )

    client = CloudflareClient("token")
    out = client.collect()
    assert len(out) == 1
    assert out[0].zone.name == "has.com"
