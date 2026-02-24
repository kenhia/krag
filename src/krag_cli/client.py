"""HTTP client wrapper for communication with kragd.

Translates httpx exceptions into meaningful Python exceptions so CLI code
doesn't need to know about HTTP details (FR-026).
"""

from __future__ import annotations

from typing import Any

import httpx


class KragClient:
    """Synchronous HTTP client for kragd.

    Wraps httpx.Client and translates connection/HTTP errors into standard
    Python exceptions (ConnectionError, RuntimeError, ValueError).

    Args:
        host: kragd host address.
        port: kragd port.
        timeout: Request timeout in seconds (default 60).
    """

    def __init__(self, host: str, port: int, timeout: float = 60.0) -> None:
        self._base_url = f"http://{host}:{port}"
        self._timeout = timeout
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    # ── public API ──────────────────────────────

    def query(self, query_text: str, **kwargs: Any) -> dict:
        """POST /query — full RAG query with LLM synthesis.

        Raises:
            ConnectionError: kragd is unreachable.
            RuntimeError: Service not ready (503).
            ValueError: Invalid request (422).
        """
        payload = {"query": query_text, **kwargs}
        return self._post("/query", payload)

    def retrieve(self, query_text: str, **kwargs: Any) -> list[dict]:
        """POST /retrieve — retrieval only, no LLM.

        Returns:
            List of source chunk dicts.
        """
        payload = {"query": query_text, **kwargs}
        resp = self._post("/retrieve", payload)
        return resp.get("sources", [])

    def index(self, **kwargs: Any) -> dict:
        """POST /index — trigger indexing.

        Returns:
            IndexResponse dict.
        """
        return self._post("/index", kwargs if kwargs else {})

    def index_status(self) -> dict:
        """GET /index/status — last indexing job info."""
        return self._get("/index/status")

    def status(self) -> dict:
        """GET /status — full service status.

        Raises:
            ConnectionError: kragd is unreachable.
        """
        return self._get("/status")

    def health(self) -> bool:
        """GET /health — simple up/down check.

        Returns:
            True if healthy, False if unreachable.
        """
        try:
            self._get("/health")
            return True
        except (ConnectionError, Exception):
            return False

    def shutdown(self) -> None:
        """POST /shutdown — graceful shutdown.

        Raises:
            ConnectionError: kragd is unreachable.
        """
        self._post("/shutdown", {})

    def post(self, path: str, json: dict | None = None) -> dict:
        """Send an arbitrary POST request.

        Useful for debug endpoints and other ad-hoc API calls.

        Args:
            path: URL path (e.g. "/debug/query").
            json: JSON payload dict.

        Returns:
            Response JSON as dict.
        """
        return self._post(path, json or {})

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    # ── private helpers ─────────────────────────

    def _post(self, path: str, payload: dict) -> dict:
        """Send POST request and handle errors."""
        try:
            resp = self._client.post(path, json=payload)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Cannot connect to kragd at {self._base_url} — is the service running?"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(
                f"Request to kragd timed out after {self._timeout}s — "
                f"the operation may still be running on the server. "
                f"Check with 'krag index-status' or see logs for details."
            ) from exc

        self._check_response(resp)
        return resp.json()

    def _get(self, path: str) -> dict:
        """Send GET request and handle errors."""
        try:
            resp = self._client.get(path)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Cannot connect to kragd at {self._base_url} — is the service running?"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(
                f"Request to kragd timed out after {self._timeout}s — see logs for details."
            ) from exc

        self._check_response(resp)
        return resp.json()

    def _check_response(self, resp: httpx.Response) -> None:
        """Translate HTTP error codes to Python exceptions."""
        if resp.status_code == 409:
            detail = resp.json().get("detail", "Conflict")
            raise RuntimeError(detail)
        if resp.status_code == 503:
            raise RuntimeError("Service not ready — kragd is still initializing")
        if resp.status_code == 422:
            detail = resp.json().get("detail", "Unknown validation error")
            raise ValueError(f"Request validation failed: {detail}")
        if resp.status_code >= 500:
            try:
                detail = resp.json().get("detail", "Internal server error")
            except Exception:
                detail = resp.text or "Internal server error"
            raise RuntimeError(f"Server error: {detail}")
        resp.raise_for_status()
