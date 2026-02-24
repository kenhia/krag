"""Routing rule definitions for file-to-collection mapping.

Defines the 8-level precedence hierarchy that routes files to the
appropriate Qdrant collection based on path patterns and file extensions.

Precedence (first match wins):
1. Plugin override → plugin-declared collection
2. Test directory pattern → ``tests``
3. Test filename pattern → ``tests``
4. Well-known doc filename → ``docs``
5. Docs extension → ``docs``
6. Code extension → ``code``
7. Config/data extension → ``text``
8. Fallback → ``text``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# ── collection constants ──────────────────────────

COLLECTION_CODE: Final[str] = "code"
COLLECTION_TESTS: Final[str] = "tests"
COLLECTION_DOCS: Final[str] = "docs"
COLLECTION_TEXT: Final[str] = "text"

ALL_COLLECTIONS: Final[frozenset[str]] = frozenset(
    {COLLECTION_CODE, COLLECTION_TESTS, COLLECTION_DOCS, COLLECTION_TEXT}
)

COLLECTION_PREFIX: Final[str] = "krag_"


def qdrant_collection_name(collection: str) -> str:
    """Return the namespaced Qdrant collection name.

    >>> qdrant_collection_name("code")
    'krag_code'
    """
    return f"{COLLECTION_PREFIX}{collection}"


# ── routing patterns ──────────────────────────────

# Level 2: Test directory patterns (any path component)
# Note: spec/ and specs/ are NOT test dirs — they route to docs via extension.
TEST_DIR_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(^|/)tests?/",
        r"(^|/)__tests__/",
        r"(^|/)test_utils?/",
    )
)

# Level 3: Test filename patterns
TEST_FILE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"test_[^/]+\.py$",
        r"[^/]+_test\.py$",
        r"[^/]+_test\.go$",
        r"[^/]+\.test\.(js|ts|tsx|jsx)$",
        r"[^/]+\.spec\.(js|ts|tsx|jsx)$",
        r"conftest\.py$",
        r"pytest\.ini$",
        r"setup\.cfg$",  # often contains [tool:pytest]
    )
)

# Level 4: Well-known documentation filenames (case-insensitive)
WELL_KNOWN_DOCS: Final[frozenset[str]] = frozenset(
    name.lower()
    for name in (
        "README",
        "README.md",
        "README.rst",
        "README.txt",
        "CHANGELOG",
        "CHANGELOG.md",
        "CHANGES",
        "CHANGES.md",
        "HISTORY",
        "HISTORY.md",
        "CONTRIBUTING",
        "CONTRIBUTING.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "CODE_OF_CONDUCT",
        "CODE_OF_CONDUCT.md",
        "SECURITY",
        "SECURITY.md",
        "AUTHORS",
        "AUTHORS.md",
        "MAINTAINERS",
        "MAINTAINERS.md",
        "TODO",
        "TODO.md",
        "ROADMAP",
        "ROADMAP.md",
    )
)

# Level 5: Documentation extensions
DOCS_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".md", ".rst", ".txt", ".adoc", ".asciidoc", ".tex", ".wiki"}
)

# Level 6: Source code extensions
CODE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".lua",
        ".swift",
        ".kt",
        ".kts",
        ".scala",
        ".r",
        ".R",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".psm1",
        ".psd1",
        ".pl",
        ".pm",
        ".ex",
        ".exs",
        ".erl",
        ".hrl",
        ".hs",
        ".ml",
        ".mli",
        ".clj",
        ".cljs",
        ".elm",
        ".v",
        ".sv",
        ".vhd",
        ".vhdl",
        ".sql",
    }
)

# Level 7: Config/data extensions
CONFIG_DATA_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".xml",
        ".csv",
        ".env",
        ".properties",
        ".editorconfig",
        ".prettierrc",
        ".eslintrc",
        ".babelrc",
    }
)


# ── routing rule dataclass ────────────────────────


@dataclass(frozen=True)
class RoutingRule:
    """A single routing rule mapping a pattern to a collection.

    Attributes:
        level: Precedence level (1 = highest priority).
        name: Human-readable rule name for debugging.
        collection: Target collection name.
    """

    level: int
    name: str
    collection: str


# Pre-built rule instances for each precedence level
RULE_PLUGIN_OVERRIDE = RoutingRule(level=1, name="plugin_override", collection="")
RULE_TEST_DIR = RoutingRule(level=2, name="test_directory", collection=COLLECTION_TESTS)
RULE_TEST_FILE = RoutingRule(level=3, name="test_filename", collection=COLLECTION_TESTS)
RULE_WELL_KNOWN_DOC = RoutingRule(level=4, name="well_known_doc", collection=COLLECTION_DOCS)
RULE_DOCS_EXT = RoutingRule(level=5, name="docs_extension", collection=COLLECTION_DOCS)
RULE_CODE_EXT = RoutingRule(level=6, name="code_extension", collection=COLLECTION_CODE)
RULE_CONFIG_DATA = RoutingRule(level=7, name="config_data", collection=COLLECTION_TEXT)
RULE_FALLBACK = RoutingRule(level=8, name="fallback", collection=COLLECTION_TEXT)
