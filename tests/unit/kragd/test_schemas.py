"""Unit tests for kragd API request/response schema validation.

T006: Tests written before implementation (TDD Red phase).
"""

import pytest
from pydantic import ValidationError


class TestQueryRequest:
    """Test QueryRequest schema validation."""

    def test_valid_query_request(self) -> None:
        """Minimal valid query request."""
        from kragd.schemas import QueryRequest

        req = QueryRequest(query="How does krag work?")
        assert req.query == "How does krag work?"
        assert req.top_k is None
        assert req.preset is None
        assert req.llm is None
        assert req.include_debug is False

    def test_query_required(self) -> None:
        """Query field is required."""
        from kragd.schemas import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest()

    def test_query_cannot_be_empty(self) -> None:
        """Query must be non-empty."""
        from kragd.schemas import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_query_max_length(self) -> None:
        """Query must be <= 10000 chars."""
        from kragd.schemas import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 10001)

    def test_top_k_range(self) -> None:
        """top_k must be 1-100 when set."""
        from kragd.schemas import QueryRequest

        assert QueryRequest(query="test", top_k=1).top_k == 1
        assert QueryRequest(query="test", top_k=100).top_k == 100
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=0)
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=101)

    def test_llm_enum_values(self) -> None:
        """llm accepts only 'text' or 'code'."""
        from kragd.schemas import QueryRequest

        assert QueryRequest(query="test", llm="text").llm == "text"
        assert QueryRequest(query="test", llm="code").llm == "code"
        with pytest.raises(ValidationError):
            QueryRequest(query="test", llm="invalid")

    def test_include_debug_default_false(self) -> None:
        """include_debug defaults to False."""
        from kragd.schemas import QueryRequest

        assert QueryRequest(query="test").include_debug is False

    def test_full_query_request(self) -> None:
        """All fields set."""
        from kragd.schemas import QueryRequest

        req = QueryRequest(
            query="test", top_k=10, preset="balanced", llm="text", include_debug=True
        )
        assert req.top_k == 10
        assert req.preset == "balanced"
        assert req.llm == "text"
        assert req.include_debug is True


class TestRetrieveRequest:
    """Test RetrieveRequest schema validation."""

    def test_valid_retrieve_request(self) -> None:
        """Minimal valid retrieve request."""
        from kragd.schemas import RetrieveRequest

        req = RetrieveRequest(query="plugin architecture")
        assert req.query == "plugin architecture"
        assert req.top_k is None

    def test_query_required(self) -> None:
        """Query is required."""
        from kragd.schemas import RetrieveRequest

        with pytest.raises(ValidationError):
            RetrieveRequest()


class TestIndexRequest:
    """Test IndexRequest schema validation."""

    def test_default_mode(self) -> None:
        """Default mode is incremental."""
        from kragd.schemas import IndexRequest

        req = IndexRequest()
        assert req.mode == "incremental"
        assert req.dry_run is False

    def test_valid_modes(self) -> None:
        """Mode accepts full or incremental."""
        from kragd.schemas import IndexRequest

        assert IndexRequest(mode="full").mode == "full"
        assert IndexRequest(mode="incremental").mode == "incremental"

    def test_invalid_mode(self) -> None:
        """Invalid mode rejected."""
        from kragd.schemas import IndexRequest

        with pytest.raises(ValidationError):
            IndexRequest(mode="partial")

    def test_dry_run_flag(self) -> None:
        """dry_run flag works."""
        from kragd.schemas import IndexRequest

        assert IndexRequest(dry_run=True).dry_run is True


class TestSourceChunk:
    """Test SourceChunk response schema."""

    def test_valid_source_chunk(self) -> None:
        """All required fields present."""
        from kragd.schemas import SourceChunk

        chunk = SourceChunk(
            chunk_id="abc-123",
            file_path="/home/user/test.py",
            score=0.85,
            rank=1,
            chunk_content="def hello(): ...",
            file_type="python",
        )
        assert chunk.chunk_id == "abc-123"
        assert chunk.score == 0.85
        assert chunk.language is None
        assert chunk.start_line is None

    def test_optional_code_fields(self) -> None:
        """Optional code fields are accepted."""
        from kragd.schemas import SourceChunk

        chunk = SourceChunk(
            chunk_id="abc",
            file_path="/test.py",
            score=0.5,
            rank=1,
            chunk_content="...",
            file_type="python",
            language="python",
            function_name="hello",
            class_name="MyClass",
            start_line=10,
            end_line=20,
        )
        assert chunk.language == "python"
        assert chunk.function_name == "hello"
        assert chunk.class_name == "MyClass"
        assert chunk.start_line == 10
        assert chunk.end_line == 20


class TestDebugMetadata:
    """Test DebugMetadata schema."""

    def test_valid_debug_metadata(self) -> None:
        """All required debug fields present."""
        from kragd.schemas import DebugMetadata

        meta = DebugMetadata(
            llm_used="text",
            llm_model="qwen2.5-7b-instruct-q4_k_m.gguf",
            route="text",
            auto_routed=True,
            route_reason="67% non-code chunks",
            preset="balanced",
            retrieval_time_ms=142.3,
            generation_time_ms=3200.5,
            embedding_models_used=["all-MiniLM-L6-v2"],
            vector_spaces_searched=["text"],
            total_candidates_before_dedup=15,
            total_candidates_after_dedup=8,
            similarity_threshold=0.2,
            per_space_result_counts={"text": 12, "code": 3},
        )
        assert meta.llm_used == "text"
        assert meta.retrieval_time_ms == 142.3
        assert len(meta.embedding_models_used) == 1

    def test_at_least_10_fields(self) -> None:
        """DebugMetadata has at least 10 fields (SC-003)."""
        from kragd.schemas import DebugMetadata

        fields = DebugMetadata.model_fields
        assert len(fields) >= 10, f"Expected >=10 fields, got {len(fields)}: {list(fields.keys())}"

    def test_timing_fields_non_negative(self) -> None:
        """Timing fields must be non-negative."""
        from kragd.schemas import DebugMetadata

        with pytest.raises(ValidationError):
            DebugMetadata(
                llm_used="text",
                llm_model="m.gguf",
                route="text",
                auto_routed=True,
                preset="balanced",
                retrieval_time_ms=-1.0,
                generation_time_ms=100.0,
                embedding_models_used=[],
                vector_spaces_searched=[],
                total_candidates_before_dedup=0,
                total_candidates_after_dedup=0,
                similarity_threshold=0.2,
                per_space_result_counts={},
            )


class TestQdrantSearchRequest:
    """Test QdrantSearchRequest schema."""

    def test_defaults(self) -> None:
        """QdrantSearchRequest default values."""
        from kragd.schemas import QdrantSearchRequest

        req = QdrantSearchRequest(query="test")
        assert req.top_k == 10
        assert req.vector_space is None
        assert req.score_threshold is None
        assert req.with_payload is True
        assert req.filters is None

    def test_top_k_range(self) -> None:
        """top_k must be 1-1000."""
        from kragd.schemas import QdrantSearchRequest

        assert QdrantSearchRequest(query="test", top_k=1000).top_k == 1000
        with pytest.raises(ValidationError):
            QdrantSearchRequest(query="test", top_k=0)
        with pytest.raises(ValidationError):
            QdrantSearchRequest(query="test", top_k=1001)

    def test_score_threshold_range(self) -> None:
        """score_threshold must be 0.0-1.0."""
        from kragd.schemas import QdrantSearchRequest

        assert QdrantSearchRequest(query="test", score_threshold=0.5).score_threshold == 0.5
        with pytest.raises(ValidationError):
            QdrantSearchRequest(query="test", score_threshold=1.1)
        with pytest.raises(ValidationError):
            QdrantSearchRequest(query="test", score_threshold=-0.1)


class TestQdrantFilters:
    """Test QdrantFilters schema."""

    def test_all_none_by_default(self) -> None:
        """All filter fields default to None."""
        from kragd.schemas import QdrantFilters

        f = QdrantFilters()
        assert f.file_type is None
        assert f.file_path_contains is None

    def test_set_filters(self) -> None:
        """Filters accept string values."""
        from kragd.schemas import QdrantFilters

        f = QdrantFilters(file_type="python", file_path_contains="plugins")
        assert f.file_type == "python"
        assert f.file_path_contains == "plugins"


class TestResponseSchemas:
    """Test response model shapes."""

    def test_query_response(self) -> None:
        """QueryResponse with optional debug."""
        from kragd.schemas import QueryResponse, SourceChunk

        resp = QueryResponse(
            answer="The answer is...",
            sources=[
                SourceChunk(
                    chunk_id="1",
                    file_path="/test.py",
                    score=0.9,
                    rank=1,
                    chunk_content="...",
                    file_type="python",
                )
            ],
            debug=None,
        )
        assert resp.answer == "The answer is..."
        assert len(resp.sources) == 1
        assert resp.debug is None

    def test_health_response(self) -> None:
        """HealthResponse schema."""
        from kragd.schemas import HealthResponse

        h = HealthResponse(status="healthy", version="0.1.0")
        assert h.status == "healthy"

    def test_health_response_status_enum(self) -> None:
        """HealthResponse status must be 'healthy' or 'degraded'."""
        from kragd.schemas import HealthResponse

        with pytest.raises(ValidationError):
            HealthResponse(status="broken", version="0.1.0")

    def test_service_status(self) -> None:
        """ServiceStatus required fields."""
        from kragd.schemas import LLMSlotStatus, ServiceStatus, VectorStoreStatus

        status = ServiceStatus(
            version="0.1.0",
            uptime_seconds=3600.0,
            llm={
                "text": LLMSlotStatus(
                    loaded=True,
                    model="qwen.gguf",
                    primary=True,
                    idle_timeout_s=None,
                )
            },
            embedding_models=["all-MiniLM-L6-v2"],
            vector_store=VectorStoreStatus(
                collection="krag_embeddings",
                total_vectors=6838,
                named_spaces=["text"],
            ),
            vram=None,
        )
        assert status.uptime_seconds == 3600.0
        assert status.llm["text"].loaded is True

    def test_index_response(self) -> None:
        """IndexResponse required fields."""
        from kragd.schemas import IndexResponse

        resp = IndexResponse(
            job_id="idx-001",
            status="completed",
            mode="incremental",
            files_scanned=100,
            files_processed=10,
            files_skipped=90,
            files_errored=0,
            chunks_created=50,
            vectors_stored=50,
            duration_seconds=12.5,
            dry_run=False,
            errors=[],
        )
        assert resp.files_processed == 10
        assert resp.duration_seconds == 12.5
