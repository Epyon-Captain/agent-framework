"""
Tests for The Brig - Agent Containment System
"""

import time
import pytest
from datetime import timezone
from python.the_brig import TheBrig, BrigCell, BrigOffense


@pytest.fixture
def brig():
    """Create a Brig instance with auto_release disabled for test control."""
    b = TheBrig(auto_release=False)
    yield b
    b.shutdown()


@pytest.fixture
def auto_brig():
    """Create a Brig instance with auto_release enabled."""
    b = TheBrig(auto_release=True, poll_interval_seconds=0.5)
    yield b
    b.shutdown()


class TestLockUp:
    def test_lock_up_basic(self, brig):
        cell = brig.lock_up("agent-001", "Spamming tool calls", duration_seconds=60)
        assert isinstance(cell, BrigCell)
        assert cell.agent_id == "agent-001"
        assert not cell.released
        assert len(cell.offenses) == 1
        assert cell.offenses[0].reason == "Spamming tool calls"

    def test_lock_up_invalid_duration(self, brig):
        with pytest.raises(ValueError):
            brig.lock_up("agent-002", "Bad behavior", duration_seconds=0)

        with pytest.raises(ValueError):
            brig.lock_up("agent-002", "Bad behavior", duration_seconds=-10)

    def test_lock_up_already_detained_extends_sentence(self, brig):
        brig.lock_up("agent-003", "First offense", duration_seconds=30)
        cell = brig.lock_up("agent-003", "Second offense", duration_seconds=120)
        assert len(cell.offenses) == 2
        # Sentence should be extended
        remaining = cell.time_remaining.total_seconds()
        assert remaining > 30  # Extended beyond original

    def test_lock_up_repeat_shorter_sentence_keeps_longer(self, brig):
        brig.lock_up("agent-004", "First offense", duration_seconds=300)
        original_release = brig.get_cell("agent-004").release_at
        brig.lock_up("agent-004", "Second offense", duration_seconds=10)
        # Original longer sentence should remain
        assert brig.get_cell("agent-004").release_at == original_release

    def test_sentenced_by_default_volta(self, brig):
        brig.lock_up("agent-005", "Test offense", duration_seconds=60)
        cell = brig.get_cell("agent-005")
        assert cell.offenses[0].sentenced_by == "Volta"


class TestIsLockedUp:
    def test_locked_up_returns_true(self, brig):
        brig.lock_up("agent-010", "Testing", duration_seconds=60)
        assert brig.is_locked_up("agent-010") is True

    def test_unknown_agent_returns_false(self, brig):
        assert brig.is_locked_up("ghost-agent") is False

    def test_served_sentence_lazy_release(self, brig):
        brig.lock_up("agent-011", "Short sentence", duration_seconds=0.1)
        time.sleep(0.2)
        # is_locked_up should trigger lazy release
        assert brig.is_locked_up("agent-011") is False
        cell = brig.get_cell("agent-011")
        assert cell.released is True


class TestRelease:
    def test_manual_release(self, brig):
        brig.lock_up("agent-020", "Testing release", duration_seconds=300)
        result = brig.release("agent-020", released_by="Captain")
        assert result is True
        assert brig.is_locked_up("agent-020") is False
        cell = brig.get_cell("agent-020")
        assert cell.released is True
        assert cell.early_release is True

    def test_release_non_detained_agent(self, brig):
        result = brig.release("agent-999")
        assert result is False

    def test_release_already_released_agent(self, brig):
        brig.lock_up("agent-021", "Testing", duration_seconds=300)
        brig.release("agent-021")
        result = brig.release("agent-021")  # Second release
        assert result is False


class TestCheckReleases:
    def test_check_releases_frees_served_agents(self, brig):
        brig.lock_up("agent-030", "Short sentence", duration_seconds=0.1)
        brig.lock_up("agent-031", "Long sentence", duration_seconds=300)
        time.sleep(0.2)
        released = brig.check_releases()
        assert "agent-030" in released
        assert "agent-031" not in released
        assert brig.is_locked_up("agent-031") is True


class TestAutoRelease:
    def test_auto_release(self, auto_brig):
        auto_brig.lock_up("agent-040", "Auto release test", duration_seconds=0.2)
        assert auto_brig.is_locked_up("agent-040") is True
        time.sleep(1.5)  # Wait for warden poll
        assert auto_brig.is_locked_up("agent-040") is False


class TestRosterAndHistory:
    def test_roster_shows_active(self, brig):
        brig.lock_up("agent-050", "Test", duration_seconds=300)
        brig.lock_up("agent-051", "Test", duration_seconds=300)
        roster = brig.roster()
        ids = [c.agent_id for c in roster]
        assert "agent-050" in ids
        assert "agent-051" in ids

    def test_roster_excludes_released(self, brig):
        brig.lock_up("agent-052", "Test", duration_seconds=300)
        brig.release("agent-052")
        roster = brig.roster()
        ids = [c.agent_id for c in roster]
        assert "agent-052" not in ids

    def test_history_includes_released(self, brig):
        brig.lock_up("agent-053", "Test", duration_seconds=300)
        brig.release("agent-053")
        history = brig.history()
        ids = [c.agent_id for c in history]
        assert "agent-053" in ids


class TestBrigCell:
    def test_cell_summary(self, brig):
        brig.lock_up("agent-060", "Summary test", duration_seconds=60)
        cell = brig.get_cell("agent-060")
        summary = cell.summary()
        assert "agent-060" in summary
        assert "Detained" in summary
        assert "Summary test" in summary

    def test_sentence_duration(self, brig):
        brig.lock_up("agent-061", "Duration test", duration_seconds=120)
        cell = brig.get_cell("agent-061")
        assert abs(cell.sentence_duration.total_seconds() - 120) < 1

    def test_time_remaining_decreases(self, brig):
        brig.lock_up("agent-062", "Time test", duration_seconds=10)
        cell = brig.get_cell("agent-062")
        r1 = cell.time_remaining.total_seconds()
        time.sleep(0.1)
        r2 = cell.time_remaining.total_seconds()
        assert r2 < r1
