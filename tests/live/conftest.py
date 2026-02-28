"""Shared fixtures for live integration tests against a running kragd.

These tests require a running kragd service and are excluded from the default
test suite. Run explicitly with:

    uv run pytest -m live --no-cov -v

Environment variables (all optional):
    KRAG_TEST_HOST          kragd host          (default: localhost)
    KRAG_TEST_PORT          kragd port          (default: 8742)
    KRAG_TEST_DIR_SMALL     small corpus dir    (default: ~/src/bits-and-pieces)
    KRAG_TEST_DIR_LARGE     large corpus dir    (default: ~/src)
    KRAG_TEST_TIMEOUT       index timeout (sec) (default: 3600)
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from krag_cli.client import KragClient


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def ensure_idle(
    client: KragClient,
    *,
    timeout: float = 3600,
    interval: float = 5.0,
) -> None:
    """Wait until no indexing job is running.

    Call at the start of any test phase that requires the service to be idle
    (not indexing). Silently returns if the service is already idle.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.index_status()
        if isinstance(resp, list):
            resp = resp[-1] if resp else {"status": "none"}
        status = resp.get("status", "none")
        if status != "running":
            return
        time.sleep(interval)
    raise TimeoutError(f"Service still indexing after {timeout}s wait")


@pytest.fixture(scope="session")
def live_host() -> str:
    return _env("KRAG_TEST_HOST", "localhost")


@pytest.fixture(scope="session")
def live_port() -> int:
    return int(_env("KRAG_TEST_PORT", "8742"))


@pytest.fixture(scope="session")
def live_timeout() -> float:
    return float(_env("KRAG_TEST_TIMEOUT", "3600"))


@pytest.fixture(scope="session")
def dir_small() -> Path:
    p = Path(_env("KRAG_TEST_DIR_SMALL", str(Path.home() / "src" / "bits-and-pieces")))
    if not p.is_dir():
        pytest.skip(f"Small corpus dir not found: {p}")
    return p


@pytest.fixture(scope="session")
def dir_large() -> Path:
    p = Path(_env("KRAG_TEST_DIR_LARGE", str(Path.home() / "src")))
    if not p.is_dir():
        pytest.skip(f"Large corpus dir not found: {p}")
    return p


@pytest.fixture(scope="session")
def client(live_host: str, live_port: int, live_timeout: float) -> KragClient:
    """Session-scoped KragClient. Skips all live tests if kragd is unreachable."""
    c = KragClient(host=live_host, port=live_port, timeout=live_timeout)
    if not c.health():
        pytest.skip(
            f"kragd is not running at {live_host}:{live_port} — "
            "start it with `uv run kragd` before running live tests"
        )
    yield c  # type: ignore[misc]
    c.close()


def poll_index_complete(
    client: KragClient,
    *,
    timeout: float = 1800,
    interval: float = 5.0,
) -> dict:
    """Block until the most recent indexing job finishes.

    Returns the final IndexResponse dict.
    Raises TimeoutError if the job doesn't complete within *timeout* seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.index_status()
        # index_status may return a list (cache) or a single dict
        if isinstance(resp, list):
            resp = resp[-1] if resp else {"status": "none"}
        status = resp.get("status", "none")
        if status in ("completed", "failed", "none"):
            return resp
        time.sleep(interval)

    raise TimeoutError(f"Indexing did not complete within {timeout}s")
