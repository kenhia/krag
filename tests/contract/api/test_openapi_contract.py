"""Contract tests for OpenAPI spec completeness (US4).

T020: Verify that:
- All endpoints have tags and meaningful summaries
- All Pydantic schema fields have descriptions
- All POST request bodies have examples
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kragd.schemas import HealthResponse

# ── Fixture ──────────────────────────────────────

# Built-in FastAPI schemas that we don't control
_BUILTIN_SCHEMAS = frozenset({"HTTPValidationError", "ValidationError"})


@pytest.fixture
def openapi_spec() -> dict:
    """Create app and return the OpenAPI JSON schema."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        mock_service = MagicMock()
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()
        mock_service.get_health.return_value = HealthResponse(status="healthy", version="0.0.0")
        MockService.return_value = mock_service

        app = create_app(config)
        return app.openapi()


# ── Tag & Summary Tests ─────────────────────────


class TestEndpointTags:
    """Every endpoint must be tagged and have a descriptive summary."""

    def test_all_endpoints_have_tags(self, openapi_spec: dict) -> None:
        """Every endpoint must have at least one tag."""
        missing = []
        for path, methods in openapi_spec["paths"].items():
            for method, spec in methods.items():
                if method in ("parameters",):
                    continue
                tags = spec.get("tags", [])
                if not tags:
                    missing.append(f"{method.upper()} {path}")
        assert missing == [], f"Endpoints missing tags: {missing}"

    def test_all_endpoints_have_summaries(self, openapi_spec: dict) -> None:
        """Every endpoint must have a non-empty summary."""
        missing = []
        for path, methods in openapi_spec["paths"].items():
            for method, spec in methods.items():
                if method in ("parameters",):
                    continue
                summary = spec.get("summary", "")
                if not summary or not summary.strip():
                    missing.append(f"{method.upper()} {path}")
        assert missing == [], f"Endpoints missing summaries: {missing}"

    def test_summaries_are_descriptive(self, openapi_spec: dict) -> None:
        """Summaries should be more than just the function name (>= 3 words)."""
        too_short = []
        for path, methods in openapi_spec["paths"].items():
            for method, spec in methods.items():
                if method in ("parameters",):
                    continue
                summary = spec.get("summary", "")
                word_count = len(summary.split())
                if word_count < 3:
                    too_short.append(f"{method.upper()} {path}: {summary!r}")
        assert too_short == [], f"Summaries too short (< 3 words): {too_short}"


# ── Schema Field Description Tests ──────────────


class TestSchemaDescriptions:
    """All Pydantic model fields must have descriptions."""

    def test_all_schema_fields_have_descriptions(self, openapi_spec: dict) -> None:
        """Every field in every schema component must have a description."""
        missing = []
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        for name, schema in schemas.items():
            if name in _BUILTIN_SCHEMAS:
                continue
            props = schema.get("properties", {})
            for field, fspec in props.items():
                if "description" not in fspec:
                    missing.append(f"{name}.{field}")
        assert missing == [], f"Fields missing descriptions: {missing}"


# ── Request Body Example Tests ──────────────────


class TestRequestBodyExamples:
    """All POST endpoints with request bodies must have examples."""

    def test_all_post_bodies_have_examples(self, openapi_spec: dict) -> None:
        """Every POST endpoint with a request body must have examples."""
        missing = []
        schemas = openapi_spec.get("components", {}).get("schemas", {})

        for path, methods in openapi_spec["paths"].items():
            for method, spec in methods.items():
                if method != "post":
                    continue
                rb = spec.get("requestBody")
                if not rb:
                    continue

                content = rb.get("content", {})
                for _ct, ct_spec in content.items():
                    # Check examples on the content type directly
                    has_example = "examples" in ct_spec or "example" in ct_spec

                    # Also check json_schema_extra on the referenced schema
                    if not has_example:
                        ref = ct_spec.get("schema", {}).get("$ref", "")
                        schema_name = ref.split("/")[-1] if ref else ""
                        if schema_name and schema_name in schemas:
                            schema_def = schemas[schema_name]
                            has_example = "examples" in schema_def or "example" in schema_def

                    if not has_example:
                        missing.append(f"POST {path}")

        assert missing == [], f"POST endpoints missing request body examples: {missing}"
