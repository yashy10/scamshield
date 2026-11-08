"""ScamShield sign-up site.

A guardian signs up and gets an invite link; the protected person opens it, reads what ScamShield
does and never does, and connects Gmail on Google's own consent screen. A people page shows who is
protected and has the demo's "Scan now" button.

Run: cd web && uv run python app.py   (http://localhost:8080)
Vercel: the repo-root app.py wraps this app; see README "Hosting the sign-up site on Vercel".
"""

from __future__ import annotations

import base64
import logging
import os
import re
import secrets
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from scamshield.config import Settings, get_settings
from scamshield.credentials import CredentialError
from scamshield.gmail import GmailClient, GmailError
from scamshield.onboarding import ConsentError, complete_signup, make_consent
from scamshield.store import Invite, Store, make_store

from .aws import OidcTokenMiddleware, configure_aws
from .scans import ScanRunner

log = logging.getLogger("scamshield.web")
HERE = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _default_base_url() -> str:
    if url := os.environ.get("SCAMSHIELD_WEB_BASE_URL"):
        return url
    if host := os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"):  # set by Vercel, e.g. scamshield.vercel.app
        return f"https://{host}"
    return "http://localhost:8080"


class SiteConfig:
    def __init__(self, settings: Settings | None = None, store: Store | None = None, base_url: str | None = None,
                 consent_kwargs: dict | None = None, gmail_factory=GmailClient, scans: ScanRunner | None = None,
                 admin_password: str | None = None, on_vercel: bool | None = None) -> None:
        self.settings = settings or get_settings()
        self.on_vercel = os.environ.get("VERCEL") == "1" if on_vercel is None else on_vercel
        if store is None:
            self.aws_mode = configure_aws(self.settings.aws_region)
            log.info("AWS credentials: %s", self.aws_mode)
        self.store = store or make_store(self.settings)
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        self.consent_kwargs = consent_kwargs or {}
        self.gmail_factory = gmail_factory
        # Vercel freezes a function once it responds, so Scan now there starts the deployed agent and returns.
        self.scans = scans or ScanRunner(os.environ.get("SCAMSHIELD_AGENT_ARN"), self.settings.aws_region,
                                         detached=self.on_vercel)
        self.sender = self.settings.ses_from_address
        self.admin_password = admin_password if admin_password is not None else os.environ.get("SCAMSHIELD_ADMIN_PASSWORD")

    def consent(self):
        return make_consent(self.settings, self.base_url, **self.consent_kwargs)


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
    return f"{slug or 'user'}-{secrets.token_hex(2)}"


def create_app(config: SiteConfig | None = None) -> Starlette:
    cfg = config or SiteConfig()
    templates = Jinja2Templates(directory=str(HERE / "templates"))

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> Response:
        return templates.TemplateResponse(request, name, {"sender": cfg.sender, **ctx}, status_code=status_code)

    def message(request: Request, title: str, body: str, status_code: int = 400) -> Response:
        return render(request, "message.html", status_code=status_code, title=title, body=body)

    def admin_denied(request: Request) -> Response | None:
        """The people page lists everyone's Gmail address: password-protect it when one is set,
        and hide it entirely on a hosted deployment without one."""
        if not cfg.admin_password:
            return message(request, "Page not found", "There's nothing here.", 404) if cfg.on_vercel else None
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                _, _, given = base64.b64decode(header[6:]).decode().partition(":")
            except ValueError:
                given = ""
            if secrets.compare_digest(given.encode(), cfg.admin_password.encode()):
                return None
        return Response("Sign in to see who ScamShield protects.", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="ScamShield people"'})

    def invite_or_none(token: str) -> Invite | None:
        return cfg.store.get_invite(token) if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", token or "") else None

    # ------------------------------------------------------------------ pages

    async def home(request: Request) -> Response:
        # Local consent returns to the site root, like Google's desktop-app loopback flow.
        if "code" in request.query_params or "error" in request.query_params:
            return await _finish_consent(request, dict(request.query_params))
        return render(request, "home.html")

    async def signup(request: Request) -> Response:
        if request.method == "GET":
            return render(request, "signup.html", form={}, errors={})
        form = await request.form()
        data = {k: str(form.get(k, "")).strip() for k in ("guardian_name", "guardian_email", "protected_name")}
        errors = {}
        if not 1 <= len(data["guardian_name"]) <= 60:
            errors["guardian_name"] = "Enter your name."
        if not EMAIL_RE.fullmatch(data["guardian_email"]):
            errors["guardian_email"] = "Enter an email address like name@example.com."
        if not 1 <= len(data["protected_name"]) <= 40:
            errors["protected_name"] = "Enter their first name."
        if form.get("agreed") != "yes":
            errors["agreed"] = "Check this box once they’ve agreed. ScamShield only protects people who want it."
        if errors:
            return render(request, "signup.html", status_code=400, form=data, errors=errors)
        invite = Invite(
            token=secrets.token_urlsafe(18),
            user_id=_slug(data["protected_name"]),
            protected_name=data["protected_name"],
            guardian_name=data["guardian_name"],
            guardian_email=data["guardian_email"].lower(),
        )
        cfg.store.put_invite(invite)
        log.info("invite created user=%s", invite.user_id)
        return RedirectResponse(f"/invite/{invite.token}", status_code=303)

    async def invite_page(request: Request) -> Response:
        invite = invite_or_none(request.path_params["token"])
        if not invite:
            return message(request, "That invite link doesn’t work", "Check the link, or set up a new invite.", 404)
        return render(request, "invite.html", invite=invite, link=f"{cfg.base_url}/join/{invite.token}")

    async def join(request: Request) -> Response:
        invite = invite_or_none(request.path_params["token"])
        if not invite:
            return message(request, "That invite link doesn’t work",
                           "Ask the person who sent it to send you a new one.", 404)
        if invite.connected_at:
            return RedirectResponse(f"/protected/{invite.token}", status_code=303)
        return render(request, "join.html", invite=invite)

    async def connect(request: Request) -> Response:
        invite = invite_or_none(request.path_params["token"])
        if not invite or invite.connected_at:
            return RedirectResponse(f"/join/{request.path_params['token']}", status_code=303)
        try:
            start = cfg.consent().start(invite.user_id)
        except (ConsentError, CredentialError) as exc:
            return message(request, "Gmail can’t be connected right now", str(exc), 503)
        request.session["consent"] = {"token": invite.token, "user_id": invite.user_id, **start.state}
        if start.authorization_url is None:  # Identity already holds a token for this user
            return await _finish_consent(request, {})
        return RedirectResponse(start.authorization_url, status_code=303)

    async def identity_callback(request: Request) -> Response:
        return await _finish_consent(request, dict(request.query_params))

    async def _finish_consent(request: Request, params: dict) -> Response:
        saved = request.session.pop("consent", None)
        if not saved:
            return message(request, "Start again from your invite link",
                           "This sign-in didn’t start in this browser, or it expired. Open your invite link and "
                           "choose Connect my Gmail again.")
        invite = invite_or_none(saved["token"])
        if not invite:
            return message(request, "That invite link doesn’t work", "Ask for a new invite link.", 404)
        try:
            token = cfg.consent().finish(saved["user_id"], saved, params)
            gmail_address = cfg.gmail_factory(token).profile_email()
        except ConsentError as exc:
            return message(request, "Gmail isn’t connected yet", f"{exc} Open your invite link to try again.")
        except (CredentialError, GmailError) as exc:
            log.warning("connect failed user=%s: %s", saved["user_id"], exc)
            return message(request, "Gmail isn’t connected yet",
                           "Google didn’t finish the connection. Open your invite link to try again.", 502)
        complete_signup(cfg.store, invite, gmail_address)
        log.info("connected user=%s", invite.user_id)
        return RedirectResponse(f"/protected/{invite.token}", status_code=303)

    async def protected(request: Request) -> Response:
        invite = invite_or_none(request.path_params["token"])
        if not invite or not invite.connected_at:
            return RedirectResponse(f"/join/{request.path_params['token']}", status_code=303)
        return render(request, "done.html", invite=invite)

    async def people(request: Request) -> Response:
        if denied := admin_denied(request):
            return denied
        invites = cfg.store.list_invites()
        scanning = any(s.status == "running" for s in cfg.scans.states.values())
        return render(request, "people.html", invites=invites, scans=cfg.scans.states, base_url=cfg.base_url,
                      refresh=scanning)

    async def scan(request: Request) -> Response:
        if denied := admin_denied(request):
            return denied
        user_id = request.path_params["user_id"]
        if cfg.store.get_user(user_id):
            cfg.scans.start(user_id)
        return RedirectResponse("/people", status_code=303)

    secret = os.environ.get("SCAMSHIELD_WEB_SECRET")
    if not secret:
        if cfg.on_vercel:  # several instances must share one signing key, or sign-ins break between them
            raise RuntimeError("Set SCAMSHIELD_WEB_SECRET on Vercel.")
        secret = secrets.token_hex(32)
    return Starlette(
        routes=[
            Route("/", home),
            Route("/signup", signup, methods=["GET", "POST"]),
            Route("/invite/{token}", invite_page),
            Route("/join/{token}", join),
            Route("/join/{token}/connect", connect, methods=["POST"]),
            Route("/connect/callback", identity_callback),
            Route("/protected/{token}", protected),
            Route("/people", people),
            Route("/people/{user_id}/scan", scan, methods=["POST"]),
            Mount("/static", StaticFiles(directory=str(HERE / "static")), name="static"),
        ],
        middleware=[
            Middleware(OidcTokenMiddleware),
            Middleware(SessionMiddleware, secret_key=secret, same_site="lax", max_age=3600,
                       https_only=cfg.base_url.startswith("https://")),
        ],
    )
