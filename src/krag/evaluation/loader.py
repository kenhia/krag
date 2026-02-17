"""TOML evaluation file loader.

Loads evaluation queries with checks from TOML files.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class EvalLoadError(Exception):
    """Error raised when evaluation file cannot be loaded or is invalid."""


@dataclass
class EvalCheck:
    """Single expected check for a query."""

    type: str  # "substring" | "source_cited" | "no_hallucination"
    value: str | None = None  # expected substring or source path; None for no_hallucination


@dataclass
class EvalQuery:
    """A single test case from the TOML file."""

    query: str
    checks: list[EvalCheck] = field(default_factory=list)


def load_eval_file(path: Path) -> list[EvalQuery]:
    """Load evaluation queries from a TOML file.

    TOML format::

        [[queries]]
        query = "What is X?"

        [[queries.checks]]
        type = "substring"
        value = "expected text"

    Args:
        path: Path to the TOML evaluation file.

    Returns:
        List of EvalQuery objects.

    Raises:
        EvalLoadError: On invalid TOML, missing required fields, or I/O errors.
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise EvalLoadError(f"Failed to load eval file: {e}") from e

    if "queries" not in data:
        raise EvalLoadError(f"Eval file {path} missing 'queries' key")

    queries: list[EvalQuery] = []
    for idx, entry in enumerate(data["queries"]):
        if "query" not in entry:
            raise EvalLoadError(f"Query entry {idx} missing 'query' field")

        checks: list[EvalCheck] = []
        for cidx, check_data in enumerate(entry.get("checks", [])):
            if "type" not in check_data:
                raise EvalLoadError(f"Check {cidx} in query {idx} missing 'type' field")
            checks.append(
                EvalCheck(
                    type=check_data["type"],
                    value=check_data.get("value"),
                )
            )

        queries.append(EvalQuery(query=entry["query"], checks=checks))

    return queries
