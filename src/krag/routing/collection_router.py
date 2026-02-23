"""CollectionRouter — routes files to content-type collections.

Implements 8-level precedence routing (first match wins):
1. Plugin override → plugin-declared collection
2. Test directory pattern → tests
3. Test filename pattern → tests
4. Well-known doc filename → docs
5. Docs extension → docs
6. Code extension → code
7. Config/data extension → text
8. Fallback → text

The router is stateless — it uses pre-compiled patterns from
``routing.rules`` and an optional plugin overrides dict.
"""

from __future__ import annotations

import logging
from pathlib import Path

from krag.routing.rules import (
    CODE_EXTENSIONS,
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_TESTS,
    COLLECTION_TEXT,
    CONFIG_DATA_EXTENSIONS,
    DOCS_EXTENSIONS,
    TEST_DIR_PATTERNS,
    TEST_FILE_PATTERNS,
    WELL_KNOWN_DOCS,
)

logger = logging.getLogger(__name__)


class CollectionRouter:
    """Routes files to the appropriate Qdrant collection.

    Uses an 8-level precedence hierarchy.  The first matching rule wins.
    Plugin overrides (level 1) are provided at construction time; all
    other rules come from the compiled constants in ``routing.rules``.

    Attributes:
        plugin_overrides: Mapping of plugin name → preferred collection.
    """

    __slots__ = ("plugin_overrides",)

    def __init__(
        self,
        plugin_overrides: dict[str, str] | None = None,
    ) -> None:
        self.plugin_overrides: dict[str, str] = plugin_overrides or {}

    # ── public API ────────────────────────────────

    def route(
        self,
        file_path: Path,
        file_ext: str,
        plugin_name: str | None,
    ) -> str:
        """Determine the target collection for *file_path*.

        Args:
            file_path: Absolute or relative path to the file.
            file_ext: File extension including leading dot (e.g. ``".py"``).
                      May be empty for extensionless files.
            plugin_name: Plugin that handled extraction, or ``None``.

        Returns:
            One of ``code``, ``tests``, ``docs``, or ``text``.
        """
        # Normalise to POSIX for pattern matching
        posix = file_path.as_posix()
        ext_lower = file_ext.lower()
        filename = file_path.name

        # Level 1: Plugin override
        if plugin_name and plugin_name in self.plugin_overrides:
            collection = self.plugin_overrides[plugin_name]
            logger.debug("Route %s → %s (plugin override: %s)", posix, collection, plugin_name)
            return collection

        # Level 2: Test directory
        for pattern in TEST_DIR_PATTERNS:
            if pattern.search(posix):
                logger.debug("Route %s → tests (test directory)", posix)
                return COLLECTION_TESTS

        # Level 3: Test filename
        for pattern in TEST_FILE_PATTERNS:
            if pattern.search(posix):
                logger.debug("Route %s → tests (test filename)", posix)
                return COLLECTION_TESTS

        # Level 4: Well-known documentation filename
        if filename.lower() in WELL_KNOWN_DOCS:
            logger.debug("Route %s → docs (well-known doc)", posix)
            return COLLECTION_DOCS

        # Level 5: Documentation extension
        if ext_lower in DOCS_EXTENSIONS:
            logger.debug("Route %s → docs (docs extension)", posix)
            return COLLECTION_DOCS

        # Level 6: Code extension
        if ext_lower in CODE_EXTENSIONS:
            logger.debug("Route %s → code (code extension)", posix)
            return COLLECTION_CODE

        # Level 7: Config/data extension
        if ext_lower in CONFIG_DATA_EXTENSIONS:
            logger.debug("Route %s → text (config/data extension)", posix)
            return COLLECTION_TEXT

        # Level 8: Fallback
        logger.debug("Route %s → text (fallback)", posix)
        return COLLECTION_TEXT
