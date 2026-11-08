"""JSON API for the Next.js frontend (frontend/). It uses the same session cookie as the HTML pages.

Every POST under /api needs the header `X-ScamShield-Client: web`. A cross-site form can't set a custom
header, and a cross-site script can't send one without a CORS preflight this API never answers. Together
with the SameSite=Lax session cookie, that keeps other sites from acting as a signed-in person.

Responses are camelCase and never cached. A family contact (guardian) gets the same view as the person,
except email subjects, matching the warnings they get by email ("you see warnings only").
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, tzinfo
from typing import TYPE_CHECKING
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from scamshield.store import EmailRecord, now_iso

from .auth import Account
from .dashboard import (
    DEFAULT_PERIOD,
    PERIODS,
    Person,
    local_window,
    parse_time,
    series,
    status_of,
    tally,
    verdict_of,
    visible_to,
    warned_to,
    when,
    within,
)
from .forms import TOKEN_RE, create_invite, validate_signup

if TYPE_CHECKING:
    from .app import SiteConfig

log = logging.getLogger("scamshield.web.api")

CLIENT_HEADER = "x-scamshield-client"
EMAIL_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
TZ_RE = re.compile(r"[A-Za-z0-9_+\-/]{1,64}")
SCAN_COOLDOWN = 60.0  # seconds: a started deployed scan isn't started again within this window

SCAN_MESSAGES = {
    "running": "Checking new emails now.",
    "started": "Scan started. Any warnings arrive by email within a few minutes.",
    "done": "Scan finished.",
    "error": "The last check didn’t finish. Try Check now again in a minute.",
}


def reply(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


def fail(code: str, status: int) -> JSONResponse:
    return reply({"error": code}, status)


def zone(name: str | None) -> tzinfo:
    """The viewer's IANA time zone; UTC when it's missing, malformed or unknown here."""
    if name and TZ_RE.fullmatch(name):
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return UTC


def person_json(person: Person) -> dict:
    return {"id": person.profile.user_id, "name": person.name, "email": person.profile.email, "role": person.role}


def marked_json(record: EmailRecord) -> dict | None:
    return {"at": record.marked_safe_at, "by": record.marked_safe_by} if record.marked_safe_at else None


def flagged_json(record: EmailRecord, person: Person) -> dict:
    return {
        "id": record.email_id,
        "verdict": record.verdict,
        "receivedAt": record.received_at,
        "checkedAt": record.checked_at,
        "senderName": record.sender_name,
        "senderDomain": record.sender_domain,
        "subject": record.subject if person.role == "self" else None,
        "reasons": list(record.reasons),
        "labeled": record.labeled,
        "warnedAt": record.warned_at,
        "warnedTo": warned_to(record, person) or None,
        "markedSafe": marked_json(record),
    }


def scan_json(cfg: SiteConfig, user_id: str) -> dict:
    state = cfg.scans.states.get(user_id)
    if state is None:
        return {"status": "idle", "message": None}
    message = SCAN_MESSAGES.get(state.status)
    if state.status == "started" and state.summary:
        message = state.summary
    elif state.status == "done":
        message = (f"Checked {state.labeled} new {'email' if state.labeled == 1 else 'emails'}." if state.labeled
                   else "No new emails were checked this time.")
    return {"status": state.status, "message": message}


def dashboard_json(cfg: SiteConfig, account: Account, wanted: str | None, period: str, tz: tzinfo,
                   now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    period = period if period in PERIODS else DEFAULT_PERIOD
    visible = visible_to(cfg.store, account.email)
    records = {p.profile.user_id: cfg.store.list_emails(p.profile.user_id) for p in visible.people}

    month_start, _ = local_window("30", now, tz)
    people = []
    for p in visible.people:
        mine = records[p.profile.user_id]
        recent = within(mine, month_start)
        people.append({**person_json(p), "status": status_of(bool(mine), recent),
                       "flagged30d": sum(verdict_of(r) != "safe" for r in recent)})

    waiting = [{"token": i.token, "protectedName": i.protected_name, "inviteUrl": f"{cfg.base_url}/join/{i.token}"}
               for i in visible.waiting]

    view = None
    if visible.people:
        person = next((p for p in visible.people if p.profile.user_id == wanted), visible.people[0])
        everything = records[person.profile.user_id]
        start, previous_start = local_window(period, now, tz)
        current = within(everything, start)
        checked_times = [t for r in everything if (t := parse_time(r.checked_at))]
        flagged = sorted((r for r in current if r.verdict in ("scam", "suspicious")), key=when, reverse=True)
        view = {
            "person": {**person_json(person), "guardianName": person.profile.guardian_name,
                       "guardianEmail": person.profile.guardian_email},
            "period": period,
            "periodLabel": PERIODS[period][0],
            "status": status_of(bool(everything), current),
            "counts": {**tally(current),
                       "warningsSent": sum(1 for r in current if r.warned_at),
                       "markedSafe": sum(1 for r in current if r.marked_safe_at)},
            "previous": tally(within(everything, previous_start, start)) if start else None,
            "lastCheckedAt": max(checked_times).isoformat() if checked_times else None,
            "series": series(everything, period, now, tz),
            "flagged": [flagged_json(r, person) for r in flagged],
            "scan": scan_json(cfg, person.profile.user_id),
        }
    return {"account": account.to_session(), "people": people, "waiting": waiting, "view": view}


def api_routes(cfg: SiteConfig) -> list[Route]:
    def account_of(request: Request) -> Account | None:
        return Account.from_session(request.session.get("account"))

    def visible_person(account: Account, user_id: str) -> Person | None:
        return next((p for p in visible_to(cfg.store, account.email).people if p.profile.user_id == user_id), None)

    def guarded(handler: Callable[[Request], Awaitable[Response]]) -> Callable[[Request], Awaitable[Response]]:
        async def check(request: Request) -> Response:
            if request.method == "POST" and request.headers.get(CLIENT_HEADER) != "web":
                return fail("missing_client_header", 403)
            return await handler(request)
        return check

    async def body_of(request: Request) -> dict | None:
        try:
            data = await request.json()
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    async def session(request: Request) -> Response:
        account = account_of(request)
        return reply({"account": account.to_session() if account else None,
                      "googleSignIn": cfg.sign_in is not None, "devSignIn": cfg.dev_sign_in})

    async def dashboard(request: Request) -> Response:
        account = account_of(request)
        if not account:
            return fail("signed_out", 401)
        q = request.query_params
        return reply(dashboard_json(cfg, account, q.get("person"), q.get("period", DEFAULT_PERIOD), zone(q.get("tz"))))

    async def scan(request: Request) -> Response:
        account = account_of(request)
        if not account:
            return fail("signed_out", 401)
        user_id = request.path_params["user_id"]
        if not visible_person(account, user_id):
            return fail("not_found", 404)
        if request.method == "GET":
            return reply(scan_json(cfg, user_id))
        state = cfg.scans.states.get(user_id)
        recently_started = state and state.status == "started" and time.time() - state.at < SCAN_COOLDOWN
        if state and (state.status == "running" or recently_started):
            return reply({"status": state.status})
        cfg.scans.start(user_id)
        state = cfg.scans.states.get(user_id)
        if state and state.status == "error":
            log.warning("scan did not start user=%s: %s", user_id, state.error)
            return reply({"error": "Scan now isn’t available right now. ScamShield still checks on its regular "
                                   "schedule."}, 503)
        log.info("scan requested user=%s", user_id)
        return reply({"status": state.status if state and state.status in ("running", "started") else "started"}, 202)

    async def mark_safe(request: Request) -> Response:
        account = account_of(request)
        if not account:
            return fail("signed_out", 401)
        body = await body_of(request)
        if body is None or not isinstance(body.get("safe"), bool):
            return fail("bad_request", 400)
        user_id, email_id = request.path_params["user_id"], request.path_params["email_id"]
        if not visible_person(account, user_id) or not EMAIL_ID_RE.fullmatch(email_id):
            return fail("not_found", 404)
        record = cfg.store.get_email(user_id, email_id)
        if not record:
            return fail("not_found", 404)
        record.marked_safe_at, record.marked_safe_by = (now_iso(), account.email) if body["safe"] else (None, None)
        cfg.store.update_email(user_id, email_id, {"marked_safe_at": record.marked_safe_at, "marked_safe_by": record.marked_safe_by})
        log.info("marked safe=%s user=%s email=%s", body["safe"], user_id, email_id)
        return reply({"markedSafe": marked_json(record)})

    async def signup(request: Request) -> Response:
        body = await body_of(request)
        if body is None:
            return fail("bad_request", 400)
        def text(key: str) -> str:
            return body[key] if isinstance(body.get(key), str) else ""

        data, errors = validate_signup(text("guardianName"), text("guardianEmail"), text("protectedName"),
                                       body.get("agreed") is True)
        if errors:
            camel = {"guardian_name": "guardianName", "guardian_email": "guardianEmail",
                     "protected_name": "protectedName", "agreed": "agreed"}
            return reply({"errors": {camel[k]: v for k, v in errors.items()}}, 400)
        invite = create_invite(cfg.store, data)
        log.info("invite created user=%s", invite.user_id)
        return reply({"token": invite.token, "inviteUrl": f"{cfg.base_url}/join/{quote(invite.token)}"}, 201)

    async def invite(request: Request) -> Response:
        token = request.path_params["token"]
        found = cfg.store.get_invite(token) if TOKEN_RE.fullmatch(token) else None
        if not found:
            return fail("not_found", 404)
        return reply({"protectedName": found.protected_name, "guardianName": found.guardian_name,
                      "connected": bool(found.connected_at), "inviteUrl": f"{cfg.base_url}/join/{found.token}"})

    async def not_found(request: Request) -> Response:
        return fail("not_found", 404)

    return [
        Route("/api/session", session),
        Route("/api/dashboard", dashboard),
        Route("/api/people/{user_id}/scan", guarded(scan), methods=["GET", "POST"]),
        Route("/api/people/{user_id}/emails/{email_id}/safe", guarded(mark_safe), methods=["POST"]),
        Route("/api/signup", guarded(signup), methods=["POST"]),
        Route("/api/invites/{token}", invite),
        Route("/api/{rest:path}", not_found, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    ]
