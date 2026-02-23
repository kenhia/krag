"""Integration test: lifecycle timer pause/resume during indexing.

T010: Verifies the full pause → wait > timeout → resume flow:
- pause() cancels the idle timer
- While paused, timer does NOT fire even after timeout elapses
- resume() re-enables timer scheduling
- After resume, the next on_request_end re-schedules the timer normally
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from kragd.lifecycle import LLMLifecycleManager


def _make_pool() -> MagicMock:
    """Build a mock LLMPool for integration testing."""
    pool = MagicMock()

    text_slot = MagicMock()
    text_slot.name = "text"
    text_slot.is_loaded = True
    text_slot.model_path = "/models/text.gguf"

    code_slot = MagicMock()
    code_slot.name = "code"
    code_slot.is_loaded = True
    code_slot.model_path = "/models/code.gguf"

    pool._text_slot = text_slot
    pool._code_slot = code_slot
    pool.swap_to = MagicMock(return_value=0.5)
    pool.close = MagicMock()
    return pool


class TestPauseResumeIntegration:
    """Integration test for the full pause/resume lifecycle flow."""

    @pytest.mark.asyncio
    async def test_pause_prevents_unload_during_timeout(self) -> None:
        """Pause → wait longer than timeout → verify no unload occurred.

        Simulates the indexing scenario: timer would have fired during
        indexing, but pause() prevents the unload.
        """
        pool = _make_pool()
        # Short timeout so the test runs fast
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        # Simulate: a code request just finished, timer is scheduled
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None

        # Pause (simulates start of indexing)
        mgr.pause()
        assert mgr._paused is True
        assert mgr._timer_task is None  # timer cancelled

        # Wait longer than the timeout — timer should NOT fire
        await asyncio.sleep(0.3)

        # LLM should NOT have been unloaded
        pool.swap_to.assert_not_called()
        pool.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_restores_normal_timer_behavior(self) -> None:
        """After resume, normal timer scheduling works again.

        Simulates: indexing finished, LLM reloaded, resume() called,
        then a query request comes in and the idle timer fires normally.
        """
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        # Pause then resume
        mgr.pause()
        mgr.resume()
        assert mgr._paused is False

        # Now a code request → on_request_end should schedule timer
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None

        # Wait for timeout to fire
        await asyncio.sleep(0.3)

        # Timer should have fired and swapped to primary
        pool.swap_to.assert_called_with("text")

    @pytest.mark.asyncio
    async def test_full_indexing_lifecycle(self) -> None:
        """Full simulation: request → pause → wait → resume → request → timeout.

        This mirrors the real service flow:
        1. A code query finishes (timer scheduled)
        2. Indexing starts: pause()
        3. Indexing takes longer than timeout
        4. Indexing finishes: resume()
        5. Another code query finishes (timer scheduled)
        6. Timer fires normally
        """
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=0.1, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        # Step 1: Code query finishes
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None

        # Step 2: Indexing starts
        mgr.pause()
        assert mgr._paused is True

        # Step 3: Indexing takes time
        await asyncio.sleep(0.2)
        pool.swap_to.assert_not_called()

        # Step 4: Indexing finishes
        mgr.resume()
        assert mgr._paused is False

        # Step 5: Another code query
        mgr.on_request_start("code")
        mgr.on_request_end("code")
        assert mgr._timer_task is not None

        # Step 6: Wait for timer
        await asyncio.sleep(0.3)
        pool.swap_to.assert_called_with("text")

    @pytest.mark.asyncio
    async def test_on_request_end_skips_scheduling_when_paused(self) -> None:
        """If paused, on_request_end should not schedule a timer."""
        pool = _make_pool()
        mgr = LLMLifecycleManager(pool=pool, idle_timeout=5, primary_llm="text")
        mgr._loop = asyncio.get_event_loop()

        mgr.pause()

        mgr.on_request_start("code")
        mgr.on_request_end("code")

        # No timer should be scheduled while paused
        assert mgr._timer_task is None

        mgr.resume()
