"""Domain registration date via RDAP (the successor to WHOIS). Public, no API key."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import httpx2
from pydantic import BaseModel, Field

IANA_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
_HEADERS = {"Accept": "application/rdap+json, application/json", "User-Agent": "ScamShield/0.1"}


class DomainAge(BaseModel):
    domain: str
    registered_date: str | None = Field(None, description="Registration date, YYYY-MM-DD, if known.")
    age_days: int | None = Field(None, description="Days since registration, if known.")
    lookup_status: str = Field(
        "ok",
        description="ok | not_found | no_rdap_server | error. Anything other than ok means age is unknown, "
        "which is NOT evidence either way.",
    )


class RdapClient:
    def __init__(self, http: httpx2.Client | None = None) -> None:
        self._http = http or httpx2.Client(timeout=10, follow_redirects=True, headers=_HEADERS)
        self._servers: dict[str, str] | None = None
        self._cache: dict[str, DomainAge] = {}
        self._lock = threading.Lock()

    def _rdap_servers(self) -> dict[str, str]:
        with self._lock:
            if self._servers is None:
                data = self._http.get(IANA_BOOTSTRAP).raise_for_status().json()
                servers: dict[str, str] = {}
                for tlds, urls in data.get("services", []):
                    https = [u for u in urls if u.startswith("https://")] or urls
                    for tld in tlds:
                        servers[tld.lower()] = https[0].rstrip("/") + "/"
                self._servers = servers
            return self._servers

    def lookup(self, domain: str, now: datetime | None = None) -> DomainAge:
        if domain in self._cache:
            return self._cache[domain]
        result = self._lookup(domain, now or datetime.now(UTC))
        if result.lookup_status in ("ok", "not_found"):
            self._cache[domain] = result
        return result

    def _lookup(self, domain: str, now: datetime) -> DomainAge:
        tld = domain.rsplit(".", 1)[-1]
        try:
            base = self._rdap_servers().get(tld)
        except httpx2.HTTPError:
            return DomainAge(domain=domain, lookup_status="error")
        if not base:
            return DomainAge(domain=domain, lookup_status="no_rdap_server")
        try:
            resp = self._http.get(f"{base}domain/{domain}")
        except httpx2.HTTPError:
            return DomainAge(domain=domain, lookup_status="error")
        if resp.status_code == 404:
            return DomainAge(domain=domain, lookup_status="not_found")
        if resp.status_code != 200:
            return DomainAge(domain=domain, lookup_status="error")

        registered = registration_date(resp.json())
        if registered is None:
            return DomainAge(domain=domain, lookup_status="error")
        return DomainAge(
            domain=domain,
            registered_date=registered.date().isoformat(),
            age_days=max(0, (now - registered).days),
            lookup_status="ok",
        )


def registration_date(rdap: dict) -> datetime | None:
    for event in rdap.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            value = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None
