"""LLM lifecycle manager with primary/secondary idle timeout.

T034: Wraps LLMPool to provide:
- Primary LLM that never unloads
- Secondary LLM that unloads after idle_timeout seconds
- In-flight request tracking to defer unloads
- Cancellable asyncio timer for idle detection

Per R-04 and R-06: uses asyncio.create_task + threading.Lock for
thread-safe in-flight counter (def route handlers run in thread pool).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from krag.synthesis.llm_pool import LLMPool

logger = logging.getLogger(__name__)


class LLMLifecycleManager:
    """Manages LLM loading/unloading around primary/secondary idle policy.

    The primary LLM (if configured) stays loaded permanently.
    The secondary LLM loads on demand and unloads after ``idle_timeout``
    seconds of inactivity (no in-flight requests using that slot).

    Args:
        pool: The ``LLMPool`` to wrap (not modified).
        idle_timeout: Seconds before non-primary LLM unloads (0 = never).
        primary_llm: Which slot is primary (``"text"``, ``"code"``, or ``None``).
    """

    def __init__(
        self,
        pool: LLMPool,
        idle_timeout: int,
        primary_llm: str | None,
    ) -> None:
        self._pool = pool
        self._idle_timeout = idle_timeout
        self._primary_llm = primary_llm
        self._timer_task: asyncio.Task[None] | None = None
        self._inflight = 0
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._paused = False

    # ── public API (called from thread-pool workers) ────

    def on_request_start(self, slot: str) -> None:
        """Track request start. Cancels any pending idle timer.

        Called from thread pool worker (sync ``def`` route handlers).
        """
        self._cancel_timer()
        with self._lock:
            self._inflight += 1

    def on_request_end(self, slot: str) -> None:
        """Track request end. May schedule idle unload for secondary slot.

        Called from thread pool worker (sync ``def`` route handlers).
        Skips timer scheduling when ``_paused`` (during indexing).
        """
        with self._lock:
            self._inflight -= 1
            inflight = self._inflight

        if self._paused:
            return

        if inflight == 0 and self._idle_timeout > 0:
            if self._primary_llm is not None:
                # Only schedule unload for non-primary slot
                if slot != self._primary_llm:
                    self._schedule_unload(slot)
            else:
                # No primary configured → all slots subject to timeout
                self._schedule_unload(slot)

    def ensure_loaded(self, slot: str) -> None:
        """Ensure the given slot is loaded, swapping if necessary.

        Called before routing to guarantee the target LLM is available.
        """
        pool_slot = self._pool._text_slot if slot == "text" else self._pool._code_slot
        if pool_slot.is_loaded:
            return
        logger.info("On-demand loading %s LLM", slot)
        self._pool.swap_to(slot)

    def pause(self) -> None:
        """Pause the idle timer (for indexing).

        Cancels any pending timer task and sets ``_paused`` so that
        ``on_request_end`` will not schedule new timers. Safe to call
        from any thread — timer cancellation uses
        ``loop.call_soon_threadsafe`` when crossing threads.
        """
        self._paused = True
        self._cancel_timer()
        logger.info("Lifecycle timer paused")

    def resume(self) -> None:
        """Resume the idle timer after indexing completes.

        Clears ``_paused`` so that subsequent ``on_request_end`` calls
        will schedule timers normally.
        """
        self._paused = False
        logger.info("Lifecycle timer resumed")

    def get_status(self) -> dict[str, Any]:
        """Return lifecycle manager status for inclusion in service status."""
        return {
            "primary_llm": self._primary_llm,
            "idle_timeout_s": self._idle_timeout,
            "timer_active": self._timer_task is not None and not self._timer_task.done(),
            "timer_paused": self._paused,
            "inflight_requests": self._inflight,
        }

    # ── timer management ────────────────────────

    def _cancel_timer(self) -> None:
        """Cancel any pending idle-timeout timer."""
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None

    def _schedule_unload(self, slot: str) -> None:
        """Schedule an idle-timeout unload for the given slot."""
        self._cancel_timer()
        loop = self._loop or self._get_event_loop()
        if loop is None:
            return
        self._timer_task = loop.create_task(self._unload_after_timeout(slot))

    async def _unload_after_timeout(self, slot: str) -> None:
        """Wait for idle_timeout, then unload if still idle."""
        # Defense-in-depth: bail out if paused (belt-and-suspenders guard)
        if self._paused:
            logger.debug("Unload timer fired but lifecycle is paused — skipping")
            return

        await asyncio.sleep(self._idle_timeout)

        # Re-check _paused after sleep (may have been paused during wait)
        if self._paused:
            logger.debug("Unload timer woke but lifecycle is now paused — skipping")
            return

        with self._lock:
            if self._inflight > 0:
                logger.info(
                    "Idle timeout reached for %s but %d request(s) in-flight — deferring unload",
                    slot,
                    self._inflight,
                )
                return

        if self._primary_llm is not None:
            # Swap to primary (unloads secondary)
            logger.info(
                "Idle timeout: unloading %s LLM, swapping to primary (%s)",
                slot,
                self._primary_llm,
            )
            await asyncio.to_thread(self._pool.swap_to, self._primary_llm)
        else:
            # No primary → close all
            logger.info("Idle timeout: no primary configured, closing all LLMs")
            await asyncio.to_thread(self._pool.close)

    def _get_event_loop(self) -> asyncio.AbstractEventLoop | None:
        """Try to get the running event loop."""
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            return loop
        except RuntimeError:
            return None
