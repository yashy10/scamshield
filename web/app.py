"""Run the ScamShield sign-up site on http://localhost:8080 (localhost only)."""

import logging
import os

import uvicorn

from scamshield_web.app import create_app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    uvicorn.run(create_app(), host=os.environ.get("SCAMSHIELD_WEB_HOST", "127.0.0.1"),
                port=int(os.environ.get("SCAMSHIELD_WEB_PORT", "8080")))
