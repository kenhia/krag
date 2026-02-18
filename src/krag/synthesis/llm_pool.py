"""Multi-LLM lifecycle manager with routing and hot-swap.

Manages one or two LLMs (text and code). Routes queries to the appropriate
LLM based on retrieved chunk composition. Handles hot-swap when only one
LLM fits in VRAM.
"""

from __future__ import annotations

import gc
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from krag.synthesis.llm_client import LLMClient

if TYPE_CHECKING:
    from krag.models.query_result import QueryResult

logger = logging.getLogger(__name__)

# File extensions considered "code" for routing decisions.
CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".java",
        ".cpp",
        ".c",
        ".rs",
        ".go",
        ".ts",
        ".jsx",
        ".tsx",
        ".rb",
        ".cs",
        ".kt",
        ".swift",
        ".scala",
        ".zig",
        ".lua",
        ".sh",
        ".bash",
        ".zsh",
        ".pl",
        ".php",
        ".r",
        ".m",
        ".h",
        ".hpp",
    }
)

# KV-cache memory estimate: ~2 KB per context position (empirical for 7-14B models).
# For n_ctx=8192 → ~16 MB per model, ~32 MB for two models.
_KV_CACHE_BYTES_PER_CTX = 2 * 1024  # 2 KB


@dataclass
class LLMSlot:
    """Tracks the state of a single LLM slot."""

    name: str
    model_path: Path | None = None
    file_size_bytes: int = 0
    instance: LLMClient | None = None
    is_loaded: bool = False
    load_time_ms: float = 0.0
    # Extra kwargs forwarded to LLMClient.
    llm_kwargs: dict[str, Any] = field(default_factory=dict)


def _get_free_vram() -> int | None:
    """Return free VRAM in bytes, or *None* if no CUDA GPU is available."""
    try:
        import torch

        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info()
            return int(free)
    except Exception:  # noqa: BLE001
        pass
    return None


class LLMPool:
    """Multi-LLM lifecycle manager with routing and hot-swap.

    Manages one or two LLMs (text and code). Routes queries to the
    appropriate LLM based on retrieved chunk composition. Handles
    hot-swap when only one LLM fits in VRAM.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        text_model_path: Path,
        code_model_path: Path | None = None,
        load_multi_llm: bool = False,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,
        **llm_kwargs: Any,
    ) -> None:
        """Initialize LLM pool.

        Args:
            text_model_path: Path to the general-purpose LLM GGUF file.
            code_model_path: Path to the code LLM GGUF file, or ``None``.
            load_multi_llm: If ``True``, attempt to load both LLMs.
            n_ctx: Context window size for all LLMs.
            n_gpu_layers: GPU layers (``-1`` = all layers on GPU).
            **llm_kwargs: Additional kwargs forwarded to ``LLMClient``.

        Raises:
            FileNotFoundError: If *text_model_path* does not exist.
            RuntimeError: If the text LLM fails to load.
        """
        if not Path(text_model_path).exists():
            raise FileNotFoundError(f"Text model not found: {text_model_path}")

        self._lock = threading.Lock()
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._llm_kwargs = llm_kwargs
        self._load_multi_llm = load_multi_llm

        # ---- slots -------------------------------------------------------
        self._text_slot = LLMSlot(
            name="text",
            model_path=Path(text_model_path),
            file_size_bytes=Path(text_model_path).stat().st_size,
        )
        self._code_slot = LLMSlot(
            name="code",
            model_path=Path(code_model_path) if code_model_path else None,
            file_size_bytes=(Path(code_model_path).stat().st_size if code_model_path else 0),
        )

        # ---- determine mode ----------------------------------------------
        self._mode = self._resolve_mode()

        # ---- load model(s) -----------------------------------------------
        self._load_slot(self._text_slot)

        if self._mode == "simultaneous":
            self._load_slot(self._code_slot)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route_and_generate(
        self,
        messages: list[dict[str, str]],
        retrieved_chunks: list[QueryResult],
        llm_override: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Route to appropriate LLM and generate response.

        Returns:
            ``(response_text, llm_name_used)`` where *llm_name_used* is
            ``"text"`` or ``"code"``.
        """
        with self._lock:
            route = self._determine_route_unlocked(retrieved_chunks, llm_override)
            slot = self._slot_for(route)

            # ---- ensure the target LLM is loaded -------------------------
            if not slot.is_loaded:
                self._swap_to_unlocked(route)
                slot = self._slot_for(route)

            assert slot.instance is not None  # noqa: S101
            response = slot.instance.generate(messages, **kwargs)
            return response, route

    def determine_route(
        self,
        chunks: list[QueryResult],
        override: str | None = None,
    ) -> str:
        """Determine which LLM should handle this query.

        Does *not* perform any swap — just returns the recommendation.

        Returns:
            ``"text"`` or ``"code"``.
        """
        return self._determine_route_unlocked(chunks, override)

    def swap_to(self, name: str) -> float:
        """Hot-swap to the named LLM.

        Args:
            name: ``"text"`` or ``"code"``.

        Returns:
            Swap duration in seconds.

        Raises:
            ValueError: If *name* is invalid or code model not configured.
        """
        self._validate_swap_target(name)
        with self._lock:
            return self._swap_to_unlocked(name)

    def get_active_llm(self) -> str | None:
        """Return name of currently loaded LLM(s).

        Returns:
            ``"text"``, ``"code"``, ``"both"``, or ``None``.
        """
        text_loaded = self._text_slot.is_loaded
        code_loaded = self._code_slot.is_loaded
        if text_loaded and code_loaded:
            return "both"
        if text_loaded:
            return "text"
        if code_loaded:
            return "code"
        return None

    def get_status(self) -> dict[str, Any]:
        """Return detailed status of all LLM slots."""
        free_vram = _get_free_vram()
        return {
            "mode": self._mode,
            "text": self._slot_status(self._text_slot),
            "code": self._slot_status(self._code_slot),
            "load_multi_llm": self._load_multi_llm,
            "vram_free_gb": (round(free_vram / (1024**3), 2) if free_vram is not None else None),
        }

    def close(self) -> None:
        """Release all loaded LLMs and free VRAM.

        Safe to call multiple times.
        """
        for slot in (self._text_slot, self._code_slot):
            if slot.instance is not None:
                try:
                    slot.instance.close()
                except Exception:  # noqa: BLE001
                    logger.warning("Error closing %s LLM", slot.name, exc_info=True)
                finally:
                    slot.instance = None
                    slot.is_loaded = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_mode(self) -> str:
        """Decide operational mode: simultaneous, hot-swap, or single."""
        if self._code_slot.model_path is None:
            return "single"

        if not self._load_multi_llm:
            return "hot-swap"

        # load_multi_llm requested — check VRAM
        if self._can_fit_both_llms():
            return "simultaneous"

        logger.warning(
            "Insufficient VRAM to load both LLMs simultaneously. Falling back to hot-swap mode."
        )
        return "hot-swap"

    def _can_fit_both_llms(self) -> bool:
        """Check if both LLMs can fit in VRAM simultaneously.

        Formula::

            free_vram × 0.80  >=  text_size + code_size + 2 × kv_cache

        where ``kv_cache = n_ctx × 2 MB``.
        """
        free = _get_free_vram()
        if free is None:
            logger.warning("No GPU detected – cannot load both LLMs simultaneously.")
            return False

        kv_cache = self._n_ctx * _KV_CACHE_BYTES_PER_CTX  # bytes per model
        required = self._text_slot.file_size_bytes + self._code_slot.file_size_bytes + 2 * kv_cache
        available = free * 0.80
        fits = available >= required
        logger.info(
            "VRAM check: available=%.1f GB, required=%.1f GB → %s",
            available / (1024**3),
            required / (1024**3),
            "fits" if fits else "does not fit",
        )
        return fits

    def _load_slot(self, slot: LLMSlot) -> None:
        """Load a model into the given slot."""
        if slot.model_path is None:
            return
        t0 = time.monotonic()
        client = LLMClient(
            model=slot.model_path,
            n_ctx=self._n_ctx,
            n_gpu_layers=self._n_gpu_layers,
            **self._llm_kwargs,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000
        slot.instance = client
        slot.is_loaded = True
        slot.load_time_ms = elapsed_ms
        logger.info(
            "%s LLM loaded in %.1f ms (%s)",
            slot.name.capitalize(),
            elapsed_ms,
            slot.model_path.name,
        )

    def _unload_slot(self, slot: LLMSlot) -> None:
        """Unload a model from the given slot."""
        if slot.instance is not None:
            slot.instance.close()
            slot.instance = None
            slot.is_loaded = False
            gc.collect()
            logger.info("%s LLM unloaded", slot.name.capitalize())

    def _swap_to_unlocked(self, name: str) -> float:
        """Swap to *name* without acquiring ``_lock`` (caller holds it)."""
        target_slot = self._slot_for(name)
        if target_slot.is_loaded:
            return 0.0

        # Unload the other slot first (if loaded) to free VRAM.
        other_slot = self._code_slot if name == "text" else self._text_slot
        if other_slot.is_loaded and self._mode != "simultaneous":
            logger.info("Swapping LLM: %s → %s …", other_slot.name, name)
            self._unload_slot(other_slot)

        t0 = time.monotonic()
        self._load_slot(target_slot)
        duration = time.monotonic() - t0
        logger.info("%s LLM loaded in %.1f s", name.capitalize(), duration)
        return duration

    def _determine_route_unlocked(
        self,
        chunks: list[QueryResult],
        override: str | None = None,
    ) -> str:
        """Routing logic without lock."""
        if override is not None:
            if override not in ("text", "code"):
                raise ValueError(f"Invalid llm_override: {override!r}")
            # If code override but no code model → fallback to text.
            if override == "code" and self._code_slot.model_path is None:
                logger.warning(
                    "Code LLM override requested but no code model configured. Using text LLM."
                )
                return "text"
            return override

        # No override — auto-route.
        composition = _analyze_chunk_composition(chunks)

        if composition == "code" and self._code_slot.model_path is not None:
            return "code"

        if composition == "code" and self._code_slot.model_path is None:
            logger.info(
                "Code-heavy query detected but no code LLM configured. "
                "Consider setting [llm] code_model in your config."
            )

        return "text"

    def _slot_for(self, name: str) -> LLMSlot:
        if name == "text":
            return self._text_slot
        if name == "code":
            return self._code_slot
        raise ValueError(f"Unknown LLM slot: {name!r}")

    def _validate_swap_target(self, name: str) -> None:
        """Pre-validate a swap target before acquiring the lock."""
        if name not in ("text", "code"):
            raise ValueError(f"Invalid LLM name: {name!r}. Must be 'text' or 'code'.")
        if name == "code" and self._code_slot.model_path is None:
            raise ValueError("Cannot swap to code LLM: code model path not configured.")

    @staticmethod
    def _slot_status(slot: LLMSlot) -> dict[str, Any]:
        return {
            "loaded": slot.is_loaded,
            "path": str(slot.model_path) if slot.model_path else None,
            "file_size_gb": round(slot.file_size_bytes / (1024**3), 2),
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _analyze_chunk_composition(chunks: list[QueryResult]) -> str:
    """Determine if chunks are predominantly code or text.

    Checks ``file_type`` against known code extensions.

    Returns:
        ``"code"`` if >40 % of chunks are code files, ``"text"`` otherwise.
    """
    if not chunks:
        return "text"
    code_count = sum(1 for c in chunks if c.file_type in CODE_EXTENSIONS)
    if code_count > len(chunks) * 0.4:
        return "code"
    return "text"
