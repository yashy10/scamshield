"""ScamShield site: landing page, sign-up, Google sign-in and the dashboard.

A guardian signs up and gets an invite link; the protected person opens it, reads what ScamShield
does and never does, and connects Gmail on Google's own consent screen. Either of them can then sign
in with Google to see the dashboard. A people page shows who is protected and has the demo's
"Scan now" button.

The Next.js frontend (frontend/) is the main UI: it uses the JSON API in api.py and sends the browser
here for the sign-in and Gmail-consent redirects, which report problems as /signin?error=<code> and
/connect/problem?error=<code>. These Jinja pages remain as a standalone fallback and the admin page.

Run: cd web && uv run python app.py   (http://localhost:8080)
Vercel: the repo-root app.py wraps this app; see README "Hosting the sign-up site on Vercel".
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

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

from .api import api_routes
from .auth import CALLBACK_PATH, SIGNIN_MESSAGES, Account, GoogleSignIn, SignInError, load_google_client
from .aws import OidcTokenMiddleware, configure_aws
from .dashboard import COLORS, PERIODS, ago, day, inbox_view, period_phrase, visible_to, warned_to, when
from .forms import EMAIL_RE, TOKEN_RE, create_invite, validate_signup
from .scans import ScanRunner

log = logging.getLogger("scamshield.web")
HERE = Path(__file__).resolve().parent
SESSION_COOKIE = "scamshield_session"

# Gmail-connection problems, by the code in /connect/problem?error=<code>.
CONNECT_PROBLEMS = {
    "restart": ("Start again from your invite link",
                ("This connection didn’t start in this browser, or it expired. Open your invite link and choose "
                 "Connect my Gmail again.")),
    "bad_invite": ("That invite link doesn’t work", "Ask the person who sent it for a new invite link."),
    "not_connected": ("Gmail isn’t connected yet",
                      ("Google sign-in was cancelled, or it didn’t finish in this browser. Open your invite link "
                       "to try again.")),
    "failed": ("Gmail isn’t connected yet", "Google didn’t finish the connection. Open your invite link to try again."),
    "unavailable": ("Gmail can’t be connected right now",
                    "Something on our side isn’t ready. Try again in a few minutes."),
}


def _default_base_url() -> str:
    if url := os.environ.get("SCAMSHIELD_WEB_BASE_URL"):
        return url
    if host := os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"):  # set by Vercel, e.g. scamshield.vercel.app
        return f"https://{host}"
    return "http://localhost:8080"


class SiteConfig:
    def __init__(self, settings: Settings | None = None, store: Store | None = None, base_url: str | None = None,
                 consent_kwargs: dict | None = None, gmail_factory=GmailClient, scans: ScanRunner | None = None,
                 admin_password: str | None = None, on_vercel: bool | None = None,
                 sign_in: GoogleSignIn | None = None, dev_sign_in: bool | None = None) -> None:
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
        if sign_in is None and (client := load_google_client(self.settings.secrets_dir)):
            sign_in = GoogleSignIn(*client, redirect_uri=f"{self.base_url}{CALLBACK_PATH}")
        self.sign_in = sign_in
        # Local preview only: sign in as any address without Google. Never on Vercel or a public URL.
        wanted = os.environ.get("SCAMSHIELD_DEV_SIGNIN") == "1" if dev_sign_in is None else dev_sign_in
        local = self.base_url.startswith(("http://localhost", "http://127.0.0.1"))
        self.dev_sign_in = wanted and local and not self.on_vercel

    def consent(self):
        return make_consent(self.settings, self.base_url, **self.consent_kwargs)


def create_app(config: SiteConfig | None = None) -> Starlette:
    cfg = config or SiteConfig()
    templates = Jinja2Templates(directory=str(HERE / "templates"))

    templates.env.globals.update(colors=COLORS, ago=ago, day=day, when=when, warned_to=warned_to,
                                 period_phrase=period_phrase)

    def account_of(request: Request) -> Account | None:
        return Account.from_session(request.session.get("account"))

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> Response:
        ctx = {"sender": cfg.sender, "account": account_of(request), **ctx}
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)

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
        return cfg.store.get_invite(token) if TOKEN_RE.fullmatch(token or "") else None

    def problem(code: str, token: str | None = None) -> Response:
        query = {"error": code, **({"token": token} if token else {})}
        return RedirectResponse(f"/connect/problem?{urlencode(query)}", status_code=303)

    # ------------------------------------------------------------------ pages

    async def home(request: Request) -> Response:
        # Local consent returns to the site root, like Google's desktop-app loopback flow.
        if "code" in request.query_params or "error" in request.query_params:
            return await _finish_consent(request, dict(request.query_params))
        return render(request, "home.html", today=date.today())

    async def signup(request: Request) -> Response:
        if request.method == "GET":
            return render(request, "signup.html", form={}, errors={})
        form = await request.form()
        data, errors = validate_signup(*(str(form.get(k, "")) for k in ("guardian_name", "guardian_email",
                                                                        "protected_name")),
                                       agreed=form.get("agreed") == "yes")
        if errors:
            return render(request, "signup.html", status_code=400, form=data, errors=errors)
        invite = create_invite(cfg.store, data)
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
        if not invite:
            return problem("bad_invite")
        if invite.connected_at:
            return RedirectResponse(f"/protected/{invite.token}", status_code=303)
        try:
            start = cfg.consent().start(invite.user_id)
        except (ConsentError, CredentialError) as exc:
            log.warning("connect could not start user=%s: %s", invite.user_id, exc)
            return problem("unavailable", invite.token)
        request.session["consent"] = {"token": invite.token, "user_id": invite.user_id, **start.state}
        if start.authorization_url is None:  # Identity already holds a token for this user
            return await _finish_consent(request, {})
        return RedirectResponse(start.authorization_url, status_code=303)

    async def identity_callback(request: Request) -> Response:
        return await _finish_consent(request, dict(request.query_params))

    async def _finish_consent(request: Request, params: dict) -> Response:
        saved = request.session.pop("consent", None)
        if not saved:
            return problem("restart")
        invite = invite_or_none(saved["token"])
        if not invite:
            return problem("bad_invite")
        try:
            token = cfg.consent().finish(saved["user_id"], saved, params)
            gmail_address = cfg.gmail_factory(token).profile_email()
        except ConsentError as exc:
            log.info("connect not finished user=%s: %s", saved["user_id"], exc)
            return problem("not_connected", invite.token)
        except (CredentialError, GmailError) as exc:
            log.warning("connect failed user=%s: %s", saved["user_id"], exc)
            return problem("failed", invite.token)
        complete_signup(cfg.store, invite, gmail_address)
        request.session["account"] = Account(gmail_address.lower(), invite.protected_name).to_session()
        log.info("connected user=%s", invite.user_id)
        return RedirectResponse(f"/protected/{invite.token}", status_code=303)

    async def connect_problem(request: Request) -> Response:
        code = request.query_params.get("error", "")
        token = request.query_params.get("token", "")
        title, body = CONNECT_PROBLEMS.get(code, ("Gmail isn’t connected yet", "Open your invite link to try again."))
        link = f"/join/{token}" if TOKEN_RE.fullmatch(token) else None
        return render(request, "message.html", title=title, body=body, link=link, link_text="Open the invite again")

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

    # ------------------------------------------------------------------ sign-in and dashboard

    async def signin(request: Request) -> Response:
        if account_of(request):
            return RedirectResponse("/dashboard", status_code=303)
        return render(request, "signin.html", google=cfg.sign_in is not None, dev=cfg.dev_sign_in,
                      error=SIGNIN_MESSAGES.get(request.query_params.get("error", "")))

    def signin_problem(code: str) -> Response:
        return RedirectResponse(f"/signin?{urlencode({'error': code})}", status_code=303)

    async def signin_google(request: Request) -> Response:
        if not cfg.sign_in:
            return signin_problem("not_configured")
        start = cfg.sign_in.start()
        request.session["signin"] = start.state
        return RedirectResponse(start.url, status_code=303)

    async def signin_callback(request: Request) -> Response:
        saved = request.session.pop("signin", None)
        if not cfg.sign_in:
            return signin_problem("not_configured")
        try:
            account = cfg.sign_in.finish(saved, dict(request.query_params))
        except SignInError as exc:
            log.info("sign-in refused: %s", exc.code)
            return signin_problem(exc.code)
        request.session["account"] = account.to_session()
        log.info("signed in")
        return RedirectResponse("/dashboard", status_code=303)

    async def signin_dev(request: Request) -> Response:
        if not cfg.dev_sign_in:
            return message(request, "Page not found", "There’s nothing here.", 404)
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return signin_problem("bad_email")
        request.session["account"] = Account(email, "").to_session()
        return RedirectResponse("/dashboard", status_code=303)

    async def signout(request: Request) -> Response:
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    async def dashboard(request: Request) -> Response:
        account = account_of(request)
        if not account:
            return RedirectResponse("/signin", status_code=303)
        visible = visible_to(cfg.store, account.email)
        if not visible.people:
            return render(request, "dashboard_empty.html", waiting=visible.waiting, base_url=cfg.base_url)
        wanted = request.query_params.get("person")
        person = next((p for p in visible.people if p.profile.user_id == wanted), visible.people[0])
        view = inbox_view(cfg.store, person, request.query_params.get("period", ""))
        return render(request, "dashboard.html", view=view, people=visible.people, waiting=visible.waiting,
                      periods=PERIODS, base_url=cfg.base_url)

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
            Route("/connect/problem", connect_problem),
            Route("/protected/{token}", protected),
            Route("/people", people),
            Route("/people/{user_id}/scan", scan, methods=["POST"]),
            Route("/signin", signin),
            Route("/signin/google", signin_google, methods=["POST"]),
            Route(CALLBACK_PATH, signin_callback),
            Route("/signin/dev", signin_dev, methods=["POST"]),
            Route("/signout", signout, methods=["POST"]),
            Route("/dashboard", dashboard),
            *api_routes(cfg),
            Mount("/static", StaticFiles(directory=str(HERE / "static")), name="static"),
        ],
        middleware=[
            Middleware(OidcTokenMiddleware),
            # A name of our own: cookies on localhost are shared across ports, and a generic "session" from
            # another local app would shadow ours.
            Middleware(SessionMiddleware, secret_key=secret, session_cookie=SESSION_COOKIE, same_site="lax",
                       max_age=8 * 3600, https_only=cfg.base_url.startswith("https://")),
        ],
    )
