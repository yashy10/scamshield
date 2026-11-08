"""Known-bad URL lookup with the Google Safe Browsing v4 Lookup API.

Safe Browsing is for non-commercial use only; a commercial launch would switch to Google Web Risk.
"""

from __future__ import annotations

import httpx2
from pydantic import BaseModel, Field

LOOKUP_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREAT_TYPES = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]


class SafeBrowsingError(Exception):
    pass


class ThreatResult(BaseModel):
    url: str
    flagged: bool
    threat_type: str | None = Field(
        None, description="e.g. SOCIAL_ENGINEERING (phishing) or MALWARE when flagged, otherwise null."
    )


class SafeBrowsingClient:
    def __init__(self, api_key: str, http: httpx2.Client | None = None) -> None:
        self._key = api_key
        self._http = http or httpx2.Client(timeout=10)

    def check(self, url: str) -> ThreatResult:
        body = {
            "client": {"clientId": "scamshield", "clientVersion": "0.1.0"},
            "threatInfo": {
                "threatTypes": THREAT_TYPES,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        try:
            # Key goes in a header, not the query string, so it never shows up in logged URLs.
            resp = self._http.post(LOOKUP_URL, headers={"X-Goog-Api-Key": self._key}, json=body)
        except httpx2.HTTPError as exc:
            raise SafeBrowsingError("Could not reach Google Safe Browsing.") from exc
        if resp.status_code != 200:
            raise SafeBrowsingError(f"Safe Browsing lookup failed (HTTP {resp.status_code}).")
        matches = resp.json().get("matches", [])
        if not matches:
            return ThreatResult(url=url, flagged=False)
        # When several types match, report phishing first; it's the most relevant for email.
        types = {m.get("threatType") for m in matches}
        preference = ["SOCIAL_ENGINEERING", *THREAT_TYPES]
        threat = next((t for t in preference if t in types), matches[0].get("threatType"))
        return ThreatResult(url=url, flagged=True, threat_type=threat)
