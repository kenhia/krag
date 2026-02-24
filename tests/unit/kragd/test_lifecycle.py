"""Unit tests for LLMLifecycleManager.

T033: Primary never unloads, secondary idle timeout, in-flight defer,
no-primary both-unload, timer cancel/restart.

T009: pause()/resume()/_paused guard for indexing timer race fix.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from kragd.lifecycle import LLMLifecycleManager

# ── helpers ─────────────────────────────────────


def _make_pool(
    text_loaded: bool = True,
    code_loaded: bool = False,
    has_code: bool = True,
) -> MagicMock:
    """Build a mock LLMPool with controllable slot states."""
    pool = MagicMock()

    text_slot = MagicMock()
    text_slot.name = "text"
    text_slot.is_loaded = text_loaded
    text_slot.model_path = "/models/text.gguf"

    code_slot = MagicMock()
    code_slot.name = "code"
    code_slot.is_loaded = code_loaded
    code_slot.model_path = "/models/code.gguf" if has_code else None

    pool._text_slot = text_slot
    pool._code_slot = code_slot

    def get_active_llm():
        t = pool._text_slot.is_loaded
        c = pool._code_slot.is_loaded
        if t and c:
            return "both"
        if t:
            return "text"
        if c:
            return "code"
        return None

    pool.get_active_llm = get_active_llm
    pool.swap_to = MagicMock(return_value=0.5)
    pool.close = MagicMock()
    return pool


# ── construction ────────────────────────────────


class TestLLMLifecycleManagerInit:
    """Test construction and defaults."""

    def test_init_stores_pool(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        assert mgr._pool is pool

    def test_init_stores_timeout(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=120, primary_llm="text")
        assert mgr._idle_timeout == 120

    def test_init_stores_primary(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="code")
        assert mgr._primary_llm == "code"

    def test_init_none_primary(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm=None)
        assert mgr._primary_llm is None

    def test_init_inflight_zero(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        assert mgr._inflight == 0

    def test_init_no_timer(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        assert mgr._timer_task is None


# ── in-flight tracking ──────────────────────────


class TestInFlightTracking:
    """Test on_request_start/end in-flight counter."""

    def test_request_start_increments(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.on_request_start("text")
        assert mgr._inflight == 1

    def test_request_end_decrements(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.on_request_start("text")
        mgr.on_request_end("text")
        assert mgr._inflight == 0

    def test_multiple_inflight(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.on_request_start("text")
        mgr.on_request_start("code")
        assert mgr._inflight == 2
        mgr.on_request_end("text")
        assert mgr._inflight == 1

    def test_thread_safety_of_counter(self) -> None:
        """Concurrent increments/decrements don't lose counts."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")

        errors = []

        def worker():
            try:
                for _ in range(100):
                    mgr.on_request_start("text")
                for _ in range(100):
                    mgr.on_request_end("text")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert mgr._inflight == 0


# ── primary never unloads ───────────────────────


class TestPrimaryNeverUnloads:
    """Primary LLM should never be subject to idle timeout."""

    def test_primary_slot_no_timer_scheduled(self) -> None:
        """End of request on primary slot should NOT schedule unload."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=5, primary_llm="text")
        mgr.on_request_start("text")
        mgr.on_request_end("text")
        # No timer should be scheduled for primary slot
        assert mgr._timer_task is None

    def test_primary_code_no_timer(self) -> None:
        """When code is primary, no timer for code requests."""
        pool = _make_pool(code_loaded=True)
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=5, primary_llm="code")
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is None


# ── secondary idle timeout ──────────────────────


class TestSecondaryIdleTimeout:
    """Secondary LLM should unload after idle timeout."""

    @pytest.mark.asyncio
    async def test_secondary_timer_scheduled(self) -> None:
        """Request end on secondary should schedule timer."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None
        # Clean up
        mgr._cancel_timer()

    @pytest.mark.asyncio
    async def test_secondary_unloads_after_timeout(self) -> None:
        """After timeout, secondary should be unloaded via swap_to(primary)."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()
        mgr.on_request_start("code")
        mgr.on_request_end("code")

        # Wait for timer to fire
        await asyncio.sleep(0.3)

        pool.swap_to.assert_called_with("text")

    @pytest.mark.asyncio
    async def test_timer_cancelled_on_new_request(self) -> None:
        """New request should cancel pending timer."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        # First request ends, timer scheduled
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        first_timer = mgr._timer_task
        assert first_timer is not None

        # New request starts, timer should be cancelled
        mgr.on_request_start("code")
        # Task is either cancelled or in cancelling state
        assert first_timer.cancelled() or first_timer.cancelling()
        # And a fresh timer slot (cleared by _cancel_timer)
        assert mgr._timer_task is None
        mgr.on_request_end("code")
        mgr._cancel_timer()


# ── in-flight defer ─────────────────────────────


class TestInFlightDefer:
    """Unload should be deferred if requests are in-flight."""

    @pytest.mark.asyncio
    async def test_no_unload_while_inflight(self) -> None:
        """Timer fires but request is in-flight → skip unload."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        mgr.on_request_start("code")
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        # One still in-flight

        await asyncio.sleep(0.3)
        pool.swap_to.assert_not_called()

        mgr.on_request_end("code")
        mgr._cancel_timer()


# ── no primary: both unload ─────────────────────


class TestNoPrimaryBothUnload:
    """When no primary is configured, both slots unload after timeout."""

    @pytest.mark.asyncio
    async def test_no_primary_text_unloads(self) -> None:
        """With no primary, text requests should schedule unload."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm=None)
        mgr._loop = asyncio.get_event_loop()

        mgr.on_request_start("text")
        mgr.on_request_end("text")

        await asyncio.sleep(0.3)
        # With no primary configured, should call close()
        pool.close.assert_called()

    @pytest.mark.asyncio
    async def test_no_primary_code_unloads(self) -> None:
        """With no primary, code requests should schedule unload."""
        pool = _make_pool(code_loaded=True)
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm=None)
        mgr._loop = asyncio.get_event_loop()

        mgr.on_request_start("code")
        mgr.on_request_end("code")

        await asyncio.sleep(0.3)
        pool.close.assert_called()


# ── ensure_loaded ───────────────────────────────


class TestEnsureLoaded:
    """Test ensure_loaded method for on-demand loading."""

    def test_ensure_loaded_already_loaded(self) -> None:
        """If slot is already loaded, no swap."""
        pool = _make_pool(text_loaded=True)
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.ensure_loaded("text")
        pool.swap_to.assert_not_called()

    def test_ensure_loaded_triggers_swap(self) -> None:
        """If slot not loaded, swap_to is called."""
        pool = _make_pool(text_loaded=True, code_loaded=False)
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.ensure_loaded("code")
        pool.swap_to.assert_called_with("code")


# ── cancel_timer ────────────────────────────────


class TestCancelTimer:
    """Test timer cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_existing_timer(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=10, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None

        mgr._cancel_timer()
        assert mgr._timer_task is None

    def test_cancel_when_none(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr._cancel_timer()  # Should not raise
        assert mgr._timer_task is None


# ── get_status ──────────────────────────────────


class TestLifecycleStatus:
    """Test status reporting from lifecycle manager."""

    def test_status_includes_primary(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        status = mgr.get_status()
        assert status["primary_llm"] == "text"

    def test_status_includes_timeout(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=120, primary_llm="text")
        status = mgr.get_status()
        assert status["idle_timeout_s"] == 120

    def test_status_timer_active(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        status = mgr.get_status()
        assert status["timer_active"] is False

    def test_status_inflight(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.on_request_start("text")
        status = mgr.get_status()
        assert status["inflight_requests"] == 1
        mgr.on_request_end("text")


# ── T009: pause / resume / _paused guard ────────


class TestPause:
    """Test pause() cancels timer and sets _paused flag."""

    def test_pause_sets_flag(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()
        assert mgr._paused is True

    def test_pause_idempotent(self) -> None:
        """Calling pause() twice should not raise."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()
        mgr.pause()
        assert mgr._paused is True

    @pytest.mark.asyncio
    async def test_pause_cancels_active_timer(self) -> None:
        """pause() should cancel any pending idle timer."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        # Schedule a timer
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None
        old_task = mgr._timer_task

        mgr.pause()
        assert mgr._timer_task is None
        assert old_task.cancelled() or old_task.cancelling()

    def test_pause_without_timer(self) -> None:
        """pause() when no timer is active should not raise."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()  # no timer active
        assert mgr._paused is True
        assert mgr._timer_task is None


class TestResume:
    """Test resume() clears _paused flag and optionally re-schedules timer."""

    def test_resume_clears_flag(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()
        assert mgr._paused is True
        mgr.resume()
        assert mgr._paused is False

    def test_resume_without_pause(self) -> None:
        """resume() when not paused should not raise."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.resume()
        assert mgr._paused is False

    def test_resume_idempotent(self) -> None:
        """Calling resume() twice should not raise."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()
        mgr.resume()
        mgr.resume()
        assert mgr._paused is False


class TestPausedGuardInUnload:
    """_unload_after_timeout should bail out when _paused is True (defense-in-depth)."""

    @pytest.mark.asyncio
    async def test_unload_skipped_when_paused(self) -> None:
        """If _paused is True, _unload_after_timeout should return immediately."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.05, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()
        mgr._paused = True

        # Run unload directly — should bail out
        await mgr._unload_after_timeout("code")
        pool.swap_to.assert_not_called()
        pool.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_proceeds_when_not_paused(self) -> None:
        """If _paused is False, _unload_after_timeout should proceed normally."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.05, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        await mgr._unload_after_timeout("code")
        pool.swap_to.assert_called_with("text")


class TestOnRequestEndPausedGuard:
    """on_request_end should skip timer scheduling when _paused is True."""

    def test_no_timer_when_paused(self) -> None:
        """on_request_end should NOT schedule timer when paused."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=5, primary_llm="text")
        mgr.pause()

        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is None

    @pytest.mark.asyncio
    async def test_timer_resumes_after_unpause(self) -> None:
        """After resume(), on_request_end should schedule timer again."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=5, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        mgr.pause()
        mgr.resume()

        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None
        mgr._cancel_timer()


class TestPausedInStatus:
    """get_status() should include timer_paused field."""

    def test_status_timer_paused_false(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        status = mgr.get_status()
        assert status["timer_paused"] is False

    def test_status_timer_paused_true(self) -> None:
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=300, primary_llm="text")
        mgr.pause()
        status = mgr.get_status()
        assert status["timer_paused"] is True
