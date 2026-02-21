"""Unit tests for KragClient (connection errors, timeout, error translation).

T008: Tests written before implementation (TDD Red phase).
"""

import pytest


class TestKragClientInit:
    """Test KragClient initialization."""

    def test_default_base_url(self) -> None:
        """KragClient constructs default base URL from host/port."""
        from krag_cli.client import KragClient

        client = KragClient(host="0.0.0.0", port=8742)
        assert client._base_url == "http://0.0.0.0:8742"
        client.close()

    def test_custom_host_port(self) -> None:
        """KragClient accepts custom host and port."""
        from krag_cli.client import KragClient

        client = KragClient(host="192.168.1.100", port=9000)
        assert client._base_url == "http://192.168.1.100:9000"
        client.close()

    def test_custom_timeout(self) -> None:
        """KragClient accepts custom timeout."""
        from krag_cli.client import KragClient

        client = KragClient(host="localhost", port=8742, timeout=120.0)
        assert client._timeout == 120.0
        client.close()

    def test_default_timeout(self) -> None:
        """KragClient has a sensible default timeout."""
        from krag_cli.client import KragClient

        client = KragClient(host="localhost", port=8742)
        assert client._timeout > 0
        client.close()


class TestKragClientConnectionErrors:
    """Test KragClient error handling when kragd is unreachable."""

    def test_query_connection_error(self, httpx_mock) -> None:
        """query() raises ConnectionError when kragd is unreachable."""
        import httpx

        from krag_cli.client import KragClient

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        client = KragClient(host="localhost", port=8742)
        with pytest.raises(ConnectionError, match="kragd"):
            client.query("test")
        client.close()

    def test_health_connection_error(self, httpx_mock) -> None:
        """health() returns False when kragd is unreachable."""
        import httpx

        from krag_cli.client import KragClient

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        client = KragClient(host="localhost", port=8742)
        result = client.health()
        assert result is False
        client.close()

    def test_status_connection_error(self, httpx_mock) -> None:
        """status() raises ConnectionError when kragd is unreachable."""
        import httpx

        from krag_cli.client import KragClient

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        client = KragClient(host="localhost", port=8742)
        with pytest.raises(ConnectionError, match="kragd"):
            client.status()
        client.close()

    def test_shutdown_connection_error(self, httpx_mock) -> None:
        """shutdown() raises ConnectionError when kragd is unreachable."""
        import httpx

        from krag_cli.client import KragClient

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        client = KragClient(host="localhost", port=8742)
        with pytest.raises(ConnectionError, match="kragd"):
            client.shutdown()
        client.close()


class TestKragClientErrorTranslation:
    """Test HTTP error translation to meaningful exceptions."""

    def test_503_raises_service_not_ready(self, httpx_mock) -> None:
        """503 response raises RuntimeError about service not ready."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(
            status_code=503,
            json={"detail": "Service not ready"},
        )
        client = KragClient(host="localhost", port=8742)
        with pytest.raises(RuntimeError, match="not ready"):
            client.query("test")
        client.close()

    def test_422_raises_validation_error(self, httpx_mock) -> None:
        """422 response raises ValueError about invalid request."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(
            status_code=422,
            json={"detail": [{"msg": "field required", "type": "missing"}]},
        )
        client = KragClient(host="localhost", port=8742)
        with pytest.raises(ValueError, match="validation"):
            client.query("test")
        client.close()


class TestKragClientSuccessfulRequests:
    """Test successful HTTP round-trips via mock."""

    def test_query_success(self, httpx_mock) -> None:
        """query() returns parsed response dict on success."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(
            json={
                "answer": "The answer is 42",
                "sources": [],
                "debug": None,
            }
        )
        client = KragClient(host="localhost", port=8742)
        result = client.query("What is the answer?")
        assert result["answer"] == "The answer is 42"
        client.close()

    def test_health_success(self, httpx_mock) -> None:
        """health() returns True when service is healthy."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(json={"status": "healthy", "version": "0.1.0"})
        client = KragClient(host="localhost", port=8742)
        assert client.health() is True
        client.close()

    def test_status_success(self, httpx_mock) -> None:
        """status() returns parsed status dict."""
        from krag_cli.client import KragClient

        status_data = {
            "version": "0.1.0",
            "uptime_seconds": 100.0,
            "llm": {},
            "embedding_models": [],
            "vector_store": {"collection": "test", "total_vectors": 0, "named_spaces": []},
            "vram": None,
        }
        httpx_mock.add_response(json=status_data)
        client = KragClient(host="localhost", port=8742)
        result = client.status()
        assert result["version"] == "0.1.0"
        client.close()

    def test_shutdown_success(self, httpx_mock) -> None:
        """shutdown() completes without error on 200."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(json={"message": "Shutdown initiated"})
        client = KragClient(host="localhost", port=8742)
        client.shutdown()  # Should not raise
        client.close()

    def test_retrieve_success(self, httpx_mock) -> None:
        """retrieve() returns list of source dicts."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(
            json={
                "sources": [
                    {
                        "chunk_id": "1",
                        "file_path": "/test.py",
                        "score": 0.5,
                        "rank": 1,
                        "chunk_content": "...",
                        "file_type": "python",
                    }
                ]
            }
        )
        client = KragClient(host="localhost", port=8742)
        result = client.retrieve("test query")
        assert len(result) == 1
        client.close()

    def test_index_success(self, httpx_mock) -> None:
        """index() returns parsed response dict."""
        from krag_cli.client import KragClient

        httpx_mock.add_response(
            json={
                "job_id": "idx-001",
                "status": "completed",
                "mode": "incremental",
                "files_scanned": 100,
                "files_processed": 10,
                "files_skipped": 90,
                "files_errored": 0,
                "chunks_created": 50,
                "vectors_stored": 50,
                "duration_seconds": 12.5,
                "dry_run": False,
                "errors": [],
            }
        )
        client = KragClient(host="localhost", port=8742)
        result = client.index()
        assert result["status"] == "completed"
        client.close()
