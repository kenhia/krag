"""Unit tests for evaluation TOML loader.

Tests load_eval_file() — valid parsing, missing fields, all check types.
Should FAIL until loader.py is implemented.
"""

import textwrap
from pathlib import Path


class TestLoadEvalFile:
    """Tests for load_eval_file()."""

    def test_load_valid_toml(self, tmp_path: Path) -> None:
        """Test loading a valid evaluation TOML file."""
        from krag.evaluation.loader import EvalQuery, load_eval_file

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "What is RAG?"

            [[queries.checks]]
            type = "substring"
            value = "retrieval"
        """)
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        queries = load_eval_file(file)
        assert len(queries) == 1
        assert isinstance(queries[0], EvalQuery)
        assert queries[0].query == "What is RAG?"
        assert len(queries[0].checks) == 1
        assert queries[0].checks[0].type == "substring"
        assert queries[0].checks[0].value == "retrieval"

    def test_load_multiple_queries(self, tmp_path: Path) -> None:
        """Test loading multiple queries from a single file."""
        from krag.evaluation.loader import load_eval_file

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "Q1"

            [[queries.checks]]
            type = "substring"
            value = "v1"

            [[queries]]
            query = "Q2"

            [[queries.checks]]
            type = "no_hallucination"
        """)
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        queries = load_eval_file(file)
        assert len(queries) == 2

    def test_load_all_check_types(self, tmp_path: Path) -> None:
        """Test that all check types are parsed correctly."""
        from krag.evaluation.loader import load_eval_file

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "Test query"

            [[queries.checks]]
            type = "substring"
            value = "expected"

            [[queries.checks]]
            type = "source_cited"
            value = "path/to/file.md"

            [[queries.checks]]
            type = "no_hallucination"
        """)
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        queries = load_eval_file(file)
        checks = queries[0].checks
        assert len(checks) == 3
        assert checks[0].type == "substring"
        assert checks[1].type == "source_cited"
        assert checks[2].type == "no_hallucination"
        assert checks[2].value is None

    def test_load_missing_query_field_raises(self, tmp_path: Path) -> None:
        """Test that missing 'query' field raises EvalLoadError."""
        import pytest

        from krag.evaluation.loader import EvalLoadError, load_eval_file

        toml_content = textwrap.dedent("""\
            [[queries]]

            [[queries.checks]]
            type = "substring"
            value = "test"
        """)
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        with pytest.raises(EvalLoadError):
            load_eval_file(file)

    def test_load_missing_check_type_raises(self, tmp_path: Path) -> None:
        """Test that missing check 'type' field raises EvalLoadError."""
        import pytest

        from krag.evaluation.loader import EvalLoadError, load_eval_file

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "test"

            [[queries.checks]]
            value = "no type field"
        """)
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        with pytest.raises(EvalLoadError):
            load_eval_file(file)

    def test_load_no_queries_key_raises(self, tmp_path: Path) -> None:
        """Test that TOML without [[queries]] raises EvalLoadError."""
        import pytest

        from krag.evaluation.loader import EvalLoadError, load_eval_file

        toml_content = "title = 'not an eval file'\n"
        file = tmp_path / "eval.toml"
        file.write_text(toml_content)

        with pytest.raises(EvalLoadError):
            load_eval_file(file)
