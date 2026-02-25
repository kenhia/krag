"""TDD tests for [embedding_code] config parsing and wiring (US4).

These tests cover:
 - Configuration model accepts ``embedding_code_model`` field
 - ``_load_toml()`` parses ``[embedding_code]`` section
 - Construction sites pass ``additional_models`` when field is set
 - Backward compat: omitted section → field is ``None``
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# T044-1: Configuration model field
# ---------------------------------------------------------------------------


class TestConfigurationEmbeddingCodeField:
    """embedding_code_model field on Configuration."""

    def test_default_is_none(self):
        """When not set, embedding_code_model defaults to None."""
        from krag.models.configuration import Configuration

        cfg = Configuration(directory_paths=[Path("/tmp")])
        assert cfg.embedding_code_model is None

    def test_accepts_model_string(self):
        """embedding_code_model can be set to a model name string."""
        from krag.models.configuration import Configuration

        cfg = Configuration(
            directory_paths=[Path("/tmp")],
            embedding_code_model="jinaai/jina-embeddings-v2-base-code",
        )
        assert cfg.embedding_code_model == "jinaai/jina-embeddings-v2-base-code"


# ---------------------------------------------------------------------------
# T044-2: TOML parsing of [embedding_code] section
# ---------------------------------------------------------------------------


class TestEmbeddingCodeTomlParsing:
    """_load_toml() parses [embedding_code] section."""

    def test_embedding_code_section_parsed(self, tmp_path: Path):
        """[embedding_code] model key maps to embedding_code_model."""
        from krag.config.settings import ConfigManager

        config_file = tmp_path / "krag.toml"
        config_file.write_text(
            """\
[directories]
paths = ["/tmp"]

[embedding_code]
model = "jinaai/jina-embeddings-v2-base-code"
"""
        )
        config = ConfigManager._load_toml(config_file)
        assert config.embedding_code_model == "jinaai/jina-embeddings-v2-base-code"

    def test_missing_embedding_code_section_defaults_none(self, tmp_path: Path):
        """Omitting [embedding_code] leaves field as None."""
        from krag.config.settings import ConfigManager

        config_file = tmp_path / "krag.toml"
        config_file.write_text(
            """\
[directories]
paths = ["/tmp"]
"""
        )
        config = ConfigManager._load_toml(config_file)
        assert config.embedding_code_model is None


# ---------------------------------------------------------------------------
# T044-3: Wiring into EmbeddingOrchestrator construction sites
# ---------------------------------------------------------------------------


class TestEmbeddingCodeWiring:
    """Construction sites pass additional_models when embedding_code_model set."""

    @patch("krag.embeddings.generator.EmbeddingGenerator")
    @patch("krag.embeddings.orchestrator.EmbeddingOrchestrator")
    def test_service_passes_additional_models(self, mock_orch_cls, mock_gen_cls):
        """KragService._init_embeddings passes code model to orchestrator."""
        from krag.models.configuration import Configuration

        mock_gen = MagicMock()
        mock_gen.dimension = 768
        mock_gen_cls.return_value = mock_gen

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        cfg = Configuration(
            directory_paths=[Path("/tmp")],
            embedding_code_model="code-model",
        )

        from kragd.service import KragService

        svc = object.__new__(KragService)
        svc.config = cfg
        svc.embedding_generator = None
        svc.embedding_orchestrator = None

        svc._init_embeddings()

        mock_orch_cls.assert_called_once()
        call_kwargs = mock_orch_cls.call_args
        assert call_kwargs.kwargs.get("additional_models") == {"code": "code-model"}

    @patch("krag.embeddings.generator.EmbeddingGenerator")
    @patch("krag.embeddings.orchestrator.EmbeddingOrchestrator")
    def test_service_no_additional_models_when_none(self, mock_orch_cls, mock_gen_cls):
        """KragService._init_embeddings omits additional_models when None."""
        from krag.models.configuration import Configuration

        mock_gen = MagicMock()
        mock_gen.dimension = 768
        mock_gen_cls.return_value = mock_gen

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        cfg = Configuration(
            directory_paths=[Path("/tmp")],
        )

        from kragd.service import KragService

        svc = object.__new__(KragService)
        svc.config = cfg
        svc.embedding_generator = None
        svc.embedding_orchestrator = None

        svc._init_embeddings()

        mock_orch_cls.assert_called_once()
        call_kwargs = mock_orch_cls.call_args
        am = call_kwargs.kwargs.get("additional_models")
        assert am is None

    @patch("krag.embeddings.orchestrator.EmbeddingGenerator")
    @patch("krag.orchestration.indexer.ChangeDetector")
    def test_indexer_passes_additional_models(self, mock_cd_cls, mock_gen_cls):
        """IndexingOrchestrator passes code model to orchestrator."""
        from krag.models.configuration import Configuration

        mock_gen = MagicMock()
        mock_gen.dimension = 768
        mock_gen_cls.return_value = mock_gen

        cfg = Configuration(
            directory_paths=[Path("/tmp")],
            embedding_code_model="code-model",
        )

        from krag.orchestration.indexer import IndexingOrchestrator

        indexer = IndexingOrchestrator(config=cfg)

        # The orchestrator should have been constructed with additional_models
        # Since we patched EmbeddingGenerator, we can inspect the orchestrator
        assert "code" in indexer.embedding_orchestrator._model_names

    @patch("krag.embeddings.generator.EmbeddingGenerator")
    @patch("krag.embeddings.orchestrator.EmbeddingOrchestrator")
    def test_pipeline_passes_additional_models(self, mock_orch_cls, mock_gen_cls, tmp_path):
        """build_query_pipeline passes code model to orchestrator."""
        from krag.models.configuration import Configuration

        cfg = Configuration(
            directory_paths=[Path("/tmp")],
            embedding_code_model="code-model",
            vector_store_path=tmp_path,  # real path so exists-check passes
        )

        mock_gen = MagicMock()
        mock_gen.dimension = 768
        mock_gen_cls.return_value = mock_gen

        mock_orch = MagicMock()
        mock_orch.is_multi_model = False
        mock_orch.get_vector_config.return_value = {}
        mock_orch_cls.return_value = mock_orch

        with (
            patch("krag.cli.pipeline.resolve_config_path", return_value=Path("/fake.toml")),
            patch("krag.config.settings.ConfigManager.load", return_value=cfg),
            patch("krag.storage.qdrant_impl.QdrantVectorStore") as mock_store_cls,
            patch("krag.retrieval.retriever.Retriever") as mock_ret_cls,
            patch("krag.orchestration.query_engine.QueryEngine") as mock_qe_cls,
            patch("krag.synthesis.llm_client.LLMClient"),
            patch("krag.synthesis.llm_pool.LLMPool"),
        ):
            mock_store_cls.return_value = MagicMock()
            mock_ret_cls.return_value = MagicMock()
            mock_qe_cls.return_value = MagicMock()

            from krag.cli.pipeline import build_query_pipeline

            build_query_pipeline(config_path=Path("/fake.toml"))

            mock_orch_cls.assert_called_once()
            call_kwargs = mock_orch_cls.call_args
            assert call_kwargs.kwargs.get("additional_models") == {"code": "code-model"}
