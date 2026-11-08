from __future__ import annotations

from pathlib import Path

import pytest

from scamshield import server
from scamshield.testing import gmail_message, make_fake_env  # noqa: F401  (re-exported for tests)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def env(tmp_path: Path):
    """Wire the server to fakes plus a real LocalStore in a temp dir."""
    fake = make_fake_env(tmp_path)
    server.set_services(fake.services)
    yield fake
    server.set_services(None)
