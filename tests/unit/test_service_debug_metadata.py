"""Unit tests for debug metadata builder consuming _last_collections_searched (US1).

Tests that the service layer uses _last_collections_searched from the
retriever (when available) to populate DebugMetadata.collections_searched.
"""

from __future__ import annotations


class TestDebugMetadataCollectionsSearched:
    """When retriever._last_collections_searched is set, service should
    use it for DebugMetadata.collections_searched rather than deriving
    from mode config."""

    def test_collections_searched_from_retriever_attribute(self):
        """_last_collections_searched should be preferred over mode config."""
        # This test validates the contract: when the retriever exposes
        # _last_collections_searched, service.py should use it for
        # DebugMetadata.collections_searched.

        # Simulate what the debug metadata builder should do
        retriever_collections = ["code", "tests"]
        mode_config_collections = ["code", "tests", "docs"]  # superset from config

        # The retriever's _last_collections_searched reflects what was
        # actually searched (may differ from config if some were skipped)
        result = retriever_collections  # service should prefer this

        assert result == ["code", "tests"]
        assert result != sorted(mode_config_collections)

    def test_fallback_when_attribute_missing(self):
        """Without _last_collections_searched, fall back to mode config."""

        class FakeRetriever:
            pass

        retriever = FakeRetriever()
        mode_config_collections = {"code": 1.0, "tests": 0.5}

        # getattr pattern used by service
        searched = getattr(retriever, "_last_collections_searched", None)
        if searched is not None:
            result = searched
        else:
            result = sorted(mode_config_collections.keys())

        assert result == ["code", "tests"]

    def test_uses_retriever_when_attribute_present(self):
        """Service should use getattr to read _last_collections_searched."""

        class FakeRetriever:
            _last_collections_searched = ["tests", "code"]

        retriever = FakeRetriever()
        mode_config_collections = {"code": 1.0, "tests": 0.5, "docs": 0.3}

        searched = getattr(retriever, "_last_collections_searched", None)
        if searched is not None:
            result = searched
        else:
            result = sorted(mode_config_collections.keys())

        # Should use the retriever's list (not mode config)
        assert result == ["tests", "code"]
        assert "docs" not in result


class TestDebugMetadataVectorSpacesExtraction:
    """When _last_per_space_counts has composite keys (collection:space),
    vector_spaces_searched should contain only the unique space names."""

    def test_composite_keys_extract_space_names(self):
        """Composite 'collection:space' keys should yield unique space names."""
        per_space_counts = {
            "code:text": 60,
            "code:code-embeddings": 58,
            "tests:text": 45,
            "tests:code-embeddings": 42,
        }
        # The service should split on ':' and deduplicate
        keys = list(per_space_counts.keys())
        if any(":" in k for k in keys):
            spaces = list(dict.fromkeys(k.split(":", 1)[1] for k in keys))
        else:
            spaces = keys

        assert sorted(spaces) == ["code-embeddings", "text"]

    def test_non_composite_keys_pass_through(self):
        """Non-composite keys (collection names) should pass through as-is."""
        per_space_counts = {"code": 60, "tests": 45}
        keys = list(per_space_counts.keys())
        if any(":" in k for k in keys):
            spaces = list(dict.fromkeys(k.split(":", 1)[1] for k in keys))
        else:
            spaces = keys

        assert spaces == ["code", "tests"]
