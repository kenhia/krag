"""Contract tests for GET /health, GET /status, POST /shutdown endpoints.

T027: Validate request/response schemas match OpenAPI spec.
T003: Verify relocated schemas are importable from kragd.schemas.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kragd.schemas import (
    HealthResponse,
    LLMSlotStatus,
    ServiceStatus,
    VectorStoreStatus,
    VRAMStatus,
)

# ── Fixture ──────────────────────────────────────


@pytest.fixture
def test_client() -> TestClient:
    """Create TestClient with mocked KragService for system endpoints."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        mock_service = MagicMock()
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()

        mock_service.get_health.return_value = HealthResponse(
            status="healthy",
            version="1.0.0",
        )

        mock_service.get_status.return_value = ServiceStatus(
            version="1.0.0",
            uptime_seconds=3600.0,
            llm={
                "text": LLMSlotStatus(
                    loaded=True,
                    model="qwen2.5-7b-instruct-q4_k_m.gguf",
                    primary=True,
                    idle_timeout_s=None,
                ),
                "code": LLMSlotStatus(
                    loaded=False,
                    model="qwen2.5-coder-7b-q4_k_m.gguf",
                    primary=False,
                    idle_timeout_s=300,
                ),
            },
            embedding_models=["all-MiniLM-L6-v2"],
            vector_store=VectorStoreStatus(
                collection="krag_embeddings",
                total_vectors=6838,
                named_spaces=["text"],
            ),
            vram=VRAMStatus(
                total_mb=8192,
                used_mb=5400,
                free_mb=2792,
            ),
        )

        MockService.return_value = mock_service
        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── GET /health contract ─────────────────────────


class TestHealthContract:
    """GET /health schema contract tests."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        """GET /health returns 200."""
        resp = test_client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self, test_client: TestClient) -> None:
        """Response has 'status' field."""
        data = test_client.get("/health").json()
        assert "status" in data
        assert data["status"] in {"healthy", "degraded"}

    def test_health_has_version_field(self, test_client: TestClient) -> None:
        """Response has 'version' string field."""
        data = test_client.get("/health").json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_content_type_json(self, test_client: TestClient) -> None:
        """Response content-type is application/json."""
        resp = test_client.get("/health")
        assert "application/json" in resp.headers["content-type"]


# ── GET /status contract ─────────────────────────


class TestStatusContract:
    """GET /status schema contract tests."""

    def test_status_returns_200(self, test_client: TestClient) -> None:
        """GET /status returns 200."""
        resp = test_client.get("/status")
        assert resp.status_code == 200

    def test_status_has_required_fields(self, test_client: TestClient) -> None:
        """Response has all required top-level fields per OpenAPI."""
        data = test_client.get("/status").json()
        required = {"version", "uptime_seconds", "llm", "embedding_models", "vector_store"}
        assert required.issubset(data.keys()), f"Missing: {required - data.keys()}"

    def test_status_version_is_string(self, test_client: TestClient) -> None:
        """version field is a string."""
        data = test_client.get("/status").json()
        assert isinstance(data["version"], str)

    def test_status_uptime_is_number(self, test_client: TestClient) -> None:
        """uptime_seconds is a non-negative number."""
        data = test_client.get("/status").json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_status_llm_is_dict_of_slots(self, test_client: TestClient) -> None:
        """llm field is a dict mapping slot names to LLMSlotStatus."""
        data = test_client.get("/status").json()
        llm = data["llm"]
        assert isinstance(llm, dict)
        for slot_name, slot in llm.items():
            assert isinstance(slot_name, str)
            assert "loaded" in slot
            assert "primary" in slot

    def test_status_llm_slot_schema(self, test_client: TestClient) -> None:
        """Each LLM slot has required fields per OpenAPI."""
        data = test_client.get("/status").json()
        for slot in data["llm"].values():
            assert isinstance(slot["loaded"], bool)
            assert isinstance(slot["primary"], bool)
            # model and idle_timeout_s are nullable
            assert "model" in slot
            assert "idle_timeout_s" in slot

    def test_status_embedding_models_is_list(self, test_client: TestClient) -> None:
        """embedding_models is an array of strings."""
        data = test_client.get("/status").json()
        assert isinstance(data["embedding_models"], list)
        for model in data["embedding_models"]:
            assert isinstance(model, str)

    def test_status_vector_store_schema(self, test_client: TestClient) -> None:
        """vector_store has required fields per OpenAPI."""
        data = test_client.get("/status").json()
        vs = data["vector_store"]
        assert "collection" in vs
        assert "total_vectors" in vs
        assert "named_spaces" in vs
        assert isinstance(vs["total_vectors"], int)
        assert isinstance(vs["named_spaces"], list)

    def test_status_vram_nullable(self, test_client: TestClient) -> None:
        """vram field is either null or has required fields."""
        data = test_client.get("/status").json()
        vram = data.get("vram")
        if vram is not None:
            assert "total_mb" in vram
            assert "used_mb" in vram
            assert "free_mb" in vram

    def test_status_vram_schema(self, test_client: TestClient) -> None:
        """When vram is present, all fields are integers."""
        data = test_client.get("/status").json()
        vram = data.get("vram")
        if vram is not None:
            assert isinstance(vram["total_mb"], int)
            assert isinstance(vram["used_mb"], int)
            assert isinstance(vram["free_mb"], int)


# ── POST /shutdown contract ──────────────────────


@patch("kragd.routers.system.threading.Thread")
class TestShutdownContract:
    """POST /shutdown schema contract tests."""

    def test_shutdown_returns_200(self, mock_thread: MagicMock, test_client: TestClient) -> None:
        """POST /shutdown returns 200."""
        resp = test_client.post("/shutdown")
        assert resp.status_code == 200

    def test_shutdown_has_message(self, mock_thread: MagicMock, test_client: TestClient) -> None:
        """Response contains 'message' string field."""
        data = test_client.post("/shutdown").json()
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_shutdown_content_type_json(
        self, mock_thread: MagicMock, test_client: TestClient
    ) -> None:
        """Response content-type is application/json."""
        resp = test_client.post("/shutdown")
        assert "application/json" in resp.headers["content-type"]


# ── Schema consolidation (T003) ──────────────────


class TestSchemaConsolidation:
    """Verify relocated schemas are importable from kragd.schemas."""

    def test_lexicon_refresh_response_importable(self) -> None:
        """LexiconRefreshResponse must be importable from kragd.schemas."""
        from kragd.schemas import LexiconRefreshResponse

        assert LexiconRefreshResponse is not None
        # Verify it has the expected fields
        fields = LexiconRefreshResponse.model_fields
        assert "entries" in fields, "Missing 'entries' field"
        assert "status" in fields, "Missing 'status' field"

    def test_mode_list_response_importable(self) -> None:
        """ModeListResponse must be importable from kragd.schemas."""
        from kragd.schemas import ModeListResponse

        assert ModeListResponse is not None
        fields = ModeListResponse.model_fields
        assert "modes" in fields, "Missing 'modes' field"

    def test_mode_detail_response_importable(self) -> None:
        """ModeDetailResponse must be importable from kragd.schemas."""
        from kragd.schemas import ModeDetailResponse

        assert ModeDetailResponse is not None
        fields = ModeDetailResponse.model_fields
        expected = {
            "name",
            "description",
            "collections",
            "llm_slot",
            "preset",
            "top_k",
            "similarity_threshold",
            "critic_enabled",
            "critic_threshold",
        }
        assert expected.issubset(fields.keys()), f"Missing fields: {expected - fields.keys()}"

    def test_lexicon_router_uses_schemas_import(self) -> None:
        """Lexicon router must import LexiconRefreshResponse from schemas, not define inline."""
        import inspect

        from kragd.routers import lexicon as lexicon_module

        source = inspect.getsource(lexicon_module)
        # Must NOT define class inline
        assert "class LexiconRefreshResponse" not in source, (
            "LexiconRefreshResponse still defined inline in lexicon router"
        )
        # Must import from schemas
        assert "from kragd.schemas import" in source and "LexiconRefreshResponse" in source, (
            "LexiconRefreshResponse not imported from kragd.schemas"
        )

    def test_modes_router_uses_schemas_import(self) -> None:
        """Modes router must import ModeDetailResponse and ModeListResponse from schemas."""
        import inspect

        from kragd.routers import modes as modes_module

        source = inspect.getsource(modes_module)
        assert "class ModeDetailResponse" not in source, (
            "ModeDetailResponse still defined inline in modes router"
        )
        assert "class ModeListResponse" not in source, (
            "ModeListResponse still defined inline in modes router"
        )
        assert "ModeDetailResponse" in source, "ModeDetailResponse not used in modes router"
        assert "ModeListResponse" in source, "ModeListResponse not used in modes router"
