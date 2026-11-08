"""Vercel entrypoint for the ScamShield sign-up site.

The site lives in web/ and uses the scamshield package from mcp_server/. Vercel's FastAPI preset
loads the top-level `app` here; the Starlette site is mounted inside it unchanged.
Locally, run the site with `cd web && uv run python app.py` instead.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "web"), str(ROOT / "mcp_server")]

from fastapi import FastAPI  # noqa: E402

from scamshield_web.app import create_app  # noqa: E402

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/", create_app())
