"""Obsidian content chunker with mixed-content routing.

Splits Obsidian notes into prose segments (→ ``docs`` collection) and
fenced code blocks (→ ``code`` collection for tagged blocks, ``docs`` for
untagged per FR-012).  Each resulting :class:`TextChunk` carries routing
metadata that the krag indexer uses for per-chunk collection assignment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from krag.models.text_chunk import TextChunk

# ---------------------------------------------------------------------------
# T048 — ContentSegment dataclass
# ---------------------------------------------------------------------------

# Regex for opening a fenced code block: 3+ backticks with optional lang tag.
_FENCE_OPEN = re.compile(r"^(`{3,})(\w*)\s*$")


@dataclass(frozen=True, slots=True)
class ContentSegment:
    """A contiguous section of note content — prose or fenced code.

    Attributes:
        text: Raw text content of the segment (non-empty after strip).
        segment_type: ``"prose"`` or ``"code"``.
        language: Language identifier from the fence line, or ``None``.
        start_line: 0-based line number where the segment begins in the
            original note.
    """

    text: str
    segment_type: Literal["prose", "code"]
    language: str | None = None
    start_line: int = 0


# ---------------------------------------------------------------------------
# T049 — _split_content()
# ---------------------------------------------------------------------------


def _split_content(text: str) -> list[ContentSegment]:
    """Parse *text* into a sequence of :class:`ContentSegment` objects.

    Fenced code blocks (3+ backticks) are recognised using a simple state
    machine.  A closing fence must have **at least** as many backticks as
    the opening fence (matching / exceeding count) — this supports nested
    fences (e.g. quad-backtick blocks containing triple backticks).

    Args:
        text: Raw note body (frontmatter already stripped).

    Returns:
        Ordered list of segments.  Empty/whitespace-only segments are
        discarded.
    """
    lines = text.split("\n")
    segments: list[ContentSegment] = []

    prose_lines: list[str] = []
    prose_start = 0

    code_lines: list[str] = []
    code_start = 0
    code_lang: str | None = None
    fence_len = 0  # 0 → not inside a fence

    def _flush_prose() -> None:
        body = "\n".join(prose_lines).strip()
        if body:
            segments.append(
                ContentSegment(
                    text=body,
                    segment_type="prose",
                    language=None,
                    start_line=prose_start,
                )
            )
        prose_lines.clear()

    def _flush_code() -> None:
        body = "\n".join(code_lines).strip()
        if body:
            segments.append(
                ContentSegment(
                    text=body,
                    segment_type="code",
                    language=code_lang,
                    start_line=code_start,
                )
            )
        code_lines.clear()

    for idx, line in enumerate(lines):
        if fence_len == 0:
            # Not inside a code block — look for an opening fence
            m = _FENCE_OPEN.match(line)
            if m:
                _flush_prose()
                fence_len = len(m.group(1))
                lang = m.group(2) or None
                code_lang = lang
                code_start = idx
                code_lines = []
            else:
                if not prose_lines:
                    prose_start = idx
                prose_lines.append(line)
        else:
            # Inside a code block — look for a matching closing fence
            stripped = line.strip()
            # Closing fence: only backticks, count >= opening fence
            if stripped and all(ch == "`" for ch in stripped) and len(stripped) >= fence_len:
                _flush_code()
                fence_len = 0
                code_lang = None
            else:
                code_lines.append(line)

    # Flush anything remaining
    if fence_len:
        # Unclosed fence — treat accumulated code lines as prose fallback
        prose_lines.extend(code_lines)
        code_lines.clear()
        fence_len = 0
    _flush_prose()

    return segments


# ---------------------------------------------------------------------------
# T050 / T051 — ObsidianChunker
# ---------------------------------------------------------------------------


class ObsidianChunker:
    """Custom chunker that splits Obsidian notes into prose and code segments.

    Each segment becomes one :class:`TextChunk`.  Per-chunk routing metadata
    (``target_collection``, ``content_type``, ``language``, ``vault_name``) is
    available via :meth:`get_chunk_metadata`.

    The chunker exposes a ``chunk()`` method so that
    :class:`ChunkingStrategyResolver` recognises it as a valid chunker and
    returns it directly (no adapter wrapping).

    Args:
        vault_name: Human-readable vault name for metadata.
        virtual_path: Virtual ``obsidian://`` path for the file.
    """

    def __init__(self, vault_name: str, virtual_path: str) -> None:
        self.vault_name = vault_name
        self.virtual_path = virtual_path
        # Map chunk_id → segment metadata for get_chunk_metadata()
        self._chunk_meta: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # chunk() — produces TextChunk objects from note text
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        file_path: Path | None = None,
        file_type: str | None = None,
    ) -> list[TextChunk]:
        """Split *text* into content-typed :class:`TextChunk` objects.

        Args:
            text: Note body (frontmatter already stripped).
            file_path: Source file path (used in chunk metadata).
            file_type: Ignored (always ``"markdown"``).

        Returns:
            Ordered list of chunks with sequential ``chunk_index`` values.
        """
        self._chunk_meta.clear()
        segments = _split_content(text)

        chunks: list[TextChunk] = []
        char_offset = 0

        for idx, seg in enumerate(segments):
            content = seg.text
            chunk_id = str(uuid4())

            chunk = TextChunk(
                chunk_id=chunk_id,
                file_path=file_path or Path("unknown"),
                chunk_index=idx,
                content=content,
                start_char=char_offset,
                end_char=char_offset + len(content),
                token_count=max(1, len(content.split())),
            )

            # Routing rules from data-model.md
            if seg.segment_type == "code" and seg.language is not None:
                target = "code"
            else:
                # prose, or untagged code (FR-012)
                target = "docs"

            self._chunk_meta[chunk_id] = {
                "target_collection": target,
                "content_type": seg.segment_type,
                "language": seg.language,
                "vault_name": self.vault_name,
            }

            chunks.append(chunk)
            char_offset += len(content)

        return chunks

    # ------------------------------------------------------------------
    # get_chunk_metadata() — per-chunk routing and attribution
    # ------------------------------------------------------------------

    def get_chunk_metadata(self, chunk: TextChunk) -> dict[str, Any]:
        """Return routing and attribution metadata for *chunk*.

        This method is called by the indexer for each chunk.  The returned
        dict is merged into the vector payload.  ``target_collection`` is
        consumed (popped) by the indexer's routing logic and is **not**
        persisted.

        Returns:
            Dict with ``target_collection``, ``content_type``,
            ``vault_name``, and optionally ``language``.
        """
        meta = self._chunk_meta.get(chunk.chunk_id, {})
        # Omit language key entirely when None
        result: dict[str, Any] = {
            "target_collection": meta.get("target_collection", "docs"),
            "content_type": meta.get("content_type", "prose"),
            "vault_name": meta.get("vault_name", self.vault_name),
        }
        lang = meta.get("language")
        if lang is not None:
            result["language"] = lang
        return result
