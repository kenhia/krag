"""Contract test: lexicon JSON validates against contracts/lexicon-schema.json — T046.

Validates that:
1. The example lexicon in the schema is valid against the schema
2. Various valid and invalid lexicon files match expected outcomes
3. LexiconStore produces entries conforming to the schema expectations
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "009-retrieval-modes"
    / "contracts"
    / "lexicon-schema.json"
)


@pytest.fixture()
def schema() -> dict:
    """Load the lexicon JSON schema."""
    return json.loads(SCHEMA_PATH.read_text())


class TestLexiconSchemaContract:
    """Contract: lexicon files conform to lexicon-schema.json."""

    def test_schema_exists(self) -> None:
        """The lexicon schema contract file exists."""
        assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json(self) -> None:
        """The schema file is valid JSON."""
        data = json.loads(SCHEMA_PATH.read_text())
        assert isinstance(data, dict)

    def test_schema_type_is_object(self, schema: dict) -> None:
        """Schema requires the root type to be 'object'."""
        assert schema["type"] == "object"

    def test_schema_additional_properties(self, schema: dict) -> None:
        """Schema allows additional properties of type string with minLength=1."""
        ap = schema["additionalProperties"]
        assert ap["type"] == "string"
        assert ap["minLength"] == 1

    def test_example_validates(self, schema: dict) -> None:
        """The example in the schema itself is a valid lexicon."""
        examples = schema.get("examples", [])
        assert len(examples) >= 1, "Schema should include at least one example"

        example = examples[0]
        assert isinstance(example, dict)
        for key, value in example.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(value, str), f"Value for {key!r} is not a string"
            assert len(value) >= 1, f"Value for {key!r} is empty"

    def test_valid_lexicon_accepted(self, tmp_path: Path) -> None:
        """A well-formed lexicon file loads without validation errors."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "valid.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon",
                    "RRF": "Reciprocal Rank Fusion",
                }
            )
        )

        store = LexiconStore()
        count = store.load(lexicon_file)
        assert count == 2

    def test_empty_lexicon_accepted(self, tmp_path: Path) -> None:
        """An empty object is valid per minProperties=0."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "empty.json"
        lexicon_file.write_text("{}")

        store = LexiconStore()
        count = store.load(lexicon_file)
        assert count == 0

    def test_non_string_value_rejected(self, tmp_path: Path) -> None:
        """Values must be strings — integer value is rejected."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "bad.json"
        lexicon_file.write_text(json.dumps({"term": 123}))

        store = LexiconStore()
        with pytest.raises(LexiconValidationError):
            store.load(lexicon_file)

    def test_empty_string_value_rejected(self, tmp_path: Path) -> None:
        """Values with minLength=1 — empty string is rejected."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "empty_val.json"
        lexicon_file.write_text(json.dumps({"term": ""}))

        store = LexiconStore()
        with pytest.raises(LexiconValidationError):
            store.load(lexicon_file)

    def test_array_root_rejected(self, tmp_path: Path) -> None:
        """Root must be an object — array is rejected."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "array.json"
        lexicon_file.write_text('["a", "b"]')

        store = LexiconStore()
        with pytest.raises(LexiconValidationError):
            store.load(lexicon_file)

    def test_loaded_entries_match_schema_contract(self, tmp_path: Path) -> None:
        """LexiconStore.entries are all dict[str, str] conforming to the schema."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "full.json"
        example = {
            "kragd": "The krag service daemon",
            "krag-direct": "In-process CLI entry point",
            "RRF": "Reciprocal Rank Fusion",
        }
        lexicon_file.write_text(json.dumps(example))

        store = LexiconStore()
        store.load(lexicon_file)

        for term, definition in store.entries.items():
            assert isinstance(term, str)
            assert isinstance(definition, str)
            assert len(definition) >= 1
