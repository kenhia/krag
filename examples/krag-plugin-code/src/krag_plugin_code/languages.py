"""Language grammar discovery and mapping for tree-sitter.

Dynamically discovers installed tree-sitter grammars and maps
file extensions to languages.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging

from tree_sitter import Language

logger = logging.getLogger(__name__)

# Mapping of language names to their common file extensions.
# tree-sitter grammar packages are named `tree-sitter-<language>`.
LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py", ".pyi"],
    "rust": [".rs"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".mts", ".cts"],
    "java": [".java"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
    "go": [".go"],
    "ruby": [".rb"],
    "php": [".php"],
    "c_sharp": [".cs"],
    "kotlin": [".kt", ".kts"],
    "swift": [".swift"],
    "lua": [".lua"],
    "bash": [".sh", ".bash"],
    "haskell": [".hs"],
    "scala": [".scala"],
    "r": [".r", ".R"],
    "julia": [".jl"],
    "zig": [".zig"],
    "elixir": [".ex", ".exs"],
    "toml": [".toml"],
    "yaml": [".yaml", ".yml"],
    "json": [".json"],
    "html": [".html", ".htm"],
    "css": [".css"],
}

# Tree-sitter query patterns for extracting semantic units per language.
# These patterns match top-level and class-level function/class definitions.
LANGUAGE_QUERIES: dict[str, str] = {
    "python": """
        (decorated_definition) @decorated
        (function_definition
            name: (identifier) @func_name) @function
        (class_definition
            name: (identifier) @class_name) @class
        (import_statement) @import
        (import_from_statement) @import
    """,
    "rust": """
        (function_item
            name: (identifier) @func_name) @function
        (struct_item
            name: (type_identifier) @struct_name) @struct
        (impl_item) @impl
        (enum_item
            name: (type_identifier) @enum_name) @enum
        (trait_item
            name: (type_identifier) @trait_name) @trait
        (use_declaration) @import
    """,
}

# Cache for discovered grammars
_grammar_cache: dict[str, Language] | None = None
_extension_map_cache: dict[str, str] | None = None


def discover_grammars() -> dict[str, Language]:
    """Discover installed tree-sitter grammars dynamically.

    Scans installed packages for tree-sitter-* grammar packages and
    loads their Language objects.

    Returns:
        Dict mapping language name to Language object.
        E.g., {"python": Language(...), "rust": Language(...)}.
    """
    global _grammar_cache
    if _grammar_cache is not None:
        return _grammar_cache

    langs: dict[str, Language] = {}

    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name", "")
        if not name:
            continue
        if name.startswith("tree-sitter-") and name != "tree-sitter":
            lang_name = name.replace("tree-sitter-", "").replace("-", "_")
            try:
                mod = importlib.import_module(f"tree_sitter_{lang_name}")
                language_func = getattr(mod, "language", None)
                if language_func is not None:
                    langs[lang_name] = Language(language_func())
                    logger.debug("Discovered tree-sitter grammar: %s", lang_name)
            except (ImportError, AttributeError, OSError) as e:
                logger.debug("Failed to load grammar for %s: %s", lang_name, e)

    _grammar_cache = langs
    logger.info("Discovered %d tree-sitter grammars: %s", len(langs), list(langs.keys()))
    return langs


def get_supported_extensions() -> list[str]:
    """Get all file extensions supported by installed grammars.

    Returns:
        List of file extensions (e.g., [".py", ".rs"]).
    """
    grammars = discover_grammars()
    extensions: list[str] = []
    for lang_name in grammars:
        if lang_name in LANGUAGE_EXTENSIONS:
            extensions.extend(LANGUAGE_EXTENSIONS[lang_name])
    return sorted(set(extensions))


def get_language_for_extension(ext: str) -> str | None:
    """Get the language name for a file extension.

    Args:
        ext: File extension (e.g., ".py").

    Returns:
        Language name (e.g., "python"), or None if not supported.
    """
    global _extension_map_cache
    if _extension_map_cache is None:
        _extension_map_cache = {}
        grammars = discover_grammars()
        for lang_name in grammars:
            if lang_name in LANGUAGE_EXTENSIONS:
                for lang_ext in LANGUAGE_EXTENSIONS[lang_name]:
                    _extension_map_cache[lang_ext] = lang_name
    return _extension_map_cache.get(ext)


def get_grammar_for_language(language: str) -> Language | None:
    """Get the tree-sitter Language object for a language name.

    Args:
        language: Language name (e.g., "python").

    Returns:
        Language object, or None if grammar not installed.
    """
    grammars = discover_grammars()
    return grammars.get(language)


def get_query_pattern(language: str) -> str | None:
    """Get the tree-sitter query pattern for a language.

    Args:
        language: Language name (e.g., "python").

    Returns:
        Query pattern string, or None if no pattern defined.
    """
    return LANGUAGE_QUERIES.get(language)


def clear_cache() -> None:
    """Clear grammar caches. Useful for testing."""
    global _grammar_cache, _extension_map_cache
    _grammar_cache = None
    _extension_map_cache = None
