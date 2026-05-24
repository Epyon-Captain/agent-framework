"""
The Brig - Agent Containment and Lockdown System
=================================================
Aboard the Epyon, this module handles the detention of misbehaving agents.

Usage:
    brig = TheBrig()
    brig.lock_up(agent_id="agent-007", reason="Spamming tool calls", duration_seconds=300)

    if brig.is_locked_up("agent-007"):
        print("Agent is in The Brig!")

    brig.check_releases()   # Frees agents whose sentence is served
    brig.release("agent-007")  # Early release (captain's orders)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("epyon.the_brig")


@dataclass
class BrigOffense:
    """A record of a single offense committed by an agent."""

    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sentenced_by: str = "Volta"  # The officer who issued the sentence

    def __str__(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"[{ts}] Offense by {self.sentenced_by}: {self.reason}"


@dataclass
class BrigCell:
    """Represents a single cell in The Brig, holding one detained agent."""

    agent_id: str
    locked_at: datetime
    release_at: datetime
    offenses: List[BrigOffense] = field(default_factory=list)
    released: bool = False
    released_at: Optional[datetime] = None
    early_release: bool = False

    @property
    def sentence_duration(self) -> timedelta:
        return self.release_at - self.locked_at

    @property
    def time_remaining(self) -> timedelta:
        now = datetime.now(timezone.utc)
        remaining = self.release_at - now
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    @property
    def is_sentence_served(self) -> bool:
        return datetime.now(timezone.utc) >= self.release_at

    def add_offense(self, offense: BrigOffense) -> None:
        self.offenses.append(offense)

    def summary(self) -> str:
        status = "Released" if self.released else "Detained"
        remaining = (
            f"{self.time_remaining}" if not self.released else "N/A"
        )
        offense_list = "\n    ".join(str(o) for o in self.offenses) or "No offenses logged."
        return (
            f"=== THE BRIG: Cell for Agent '{self.agent_id}' ===\n"
            f"  Status        : {status}\n"
            f"  Locked At     : {self.locked_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"  Release At    : {self.release_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"  Time Remaining: {remaining}\n"
            f"  Early Release : {self.early_release}\n"
            f"  Offenses:\n    {offense_list}"
        )


class TheBrig:
    """
    The Brig - Epyon's Agent Detention Facility.

    Agents who misbehave are locked up for a set period of time.
    They cannot act while detained and are released automatically
    when their sentence is served (or by captain's orders).
    """

    def __init__(self, auto_release: bool = True, poll_interval_seconds: float = 10.0):
        """
        Initialize The Brig.

        Args:
            auto_release: If True, a background thread automatically
                          releases agents when their sentence is served.
            poll_interval_seconds: How often (in seconds) to poll for
                                   agents whose sentence is complete.
        """
        self._cells: Dict[str, BrigCell] = {}  # agent_id -> BrigCell
        self._lock = threading.Lock()
        self._auto_release = auto_release
        self._poll_interval = poll_interval_seconds
        self._shutdown = threading.Event()

        if auto_release:
            self._warden_thread = threading.Thread(
                target=self._warden_loop,
                name="TheBrig-Warden",
                daemon=True,
            )
            self._warden_thread.start()
            logger.info("The Brig is open. Warden is on duty.")
        else:
            logger.info("The Brig is open. Manual release mode.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lock_up(
        self,
        agent_id: str,
        reason: str,
        duration_seconds: float,
        sentenced_by: str = "Volta",
    ) -> BrigCell:
        """
        Lock an agent in The Brig for a set duration.

        Args:
            agent_id: Unique identifier of the misbehaving agent.
            reason: Human-readable description of the offense.
            duration_seconds: How long (in seconds) the agent is detained.
            sentenced_by: Who issued the sentence (default: Volta).

        Returns:
            The BrigCell representing the agent's detention.

        Raises:
            ValueError: If duration_seconds is not positive.
        """
        if duration_seconds <= 0:
            raise ValueError("Sentence duration must be a positive number of seconds.")

        now = datetime.now(timezone.utc)
        release_at = now + timedelta(seconds=duration_seconds)
        offense = BrigOffense(reason=reason, timestamp=now, sentenced_by=sentenced_by)

        with self._lock:
            if agent_id in self._cells and not self._cells[agent_id].released:
                # Agent already in The Brig - extend sentence and log new offense
                cell = self._cells[agent_id]
                cell.add_offense(offense)
                # Extend release time if new sentence is longer
                if release_at > cell.release_at:
                    cell.release_at = release_at
                    logger.warning(
                        "Agent '%s' already in The Brig. Sentence extended to %s. Reason: %s",
                        agent_id,
                        cell.release_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        reason,
                    )
                else:
                    logger.warning(
                        "Agent '%s' already in The Brig. New offense logged. Reason: %s",
                        agent_id,
                        reason,
                    )
                return cell

            # New cell
            cell = BrigCell(
                agent_id=agent_id,
                locked_at=now,
                release_at=release_at,
                offenses=[offense],
            )
            self._cells[agent_id] = cell

        logger.warning(
            "🔒 Agent '%s' has been locked in The Brig for %.1f seconds. Reason: %s",
            agent_id,
            duration_seconds,
            reason,
        )
        return cell

    def is_locked_up(self, agent_id: str) -> bool:
        """
        Check whether an agent is currently detained in The Brig.

        Args:
            agent_id: The agent's unique identifier.

        Returns:
            True if the agent is currently locked up, False otherwise.
        """
        with self._lock:
            cell = self._cells.get(agent_id)
            if cell is None or cell.released:
                return False
            if cell.is_sentence_served:
                # Lazy release
                self._do_release(cell, early=False)
                return False
            return True

    def release(self, agent_id: str, released_by: str = "Captain") -> bool:
        """
        Release an agent from The Brig early (captain's orders).

        Args:
            agent_id: The agent's unique identifier.
            released_by: Who authorized the early release.

        Returns:
            True if the agent was released, False if they weren't in The Brig.
        """
        with self._lock:
            cell = self._cells.get(agent_id)
            if cell is None or cell.released:
                logger.info("Agent '%s' is not currently in The Brig.", agent_id)
                return False
            self._do_release(cell, early=True)

        logger.info(
            "⚓ Agent '%s' has been released from The Brig early by %s.",
            agent_id,
            released_by,
        )
        return True

    def check_releases(self) -> List[str]:
        """
        Manually check for and release agents whose sentence is served.
        Useful when auto_release=False.

        Returns:
            List of agent IDs that were released.
        """
        released_agents: List[str] = []
        with self._lock:
            for cell in list(self._cells.values()):
                if not cell.released and cell.is_sentence_served:
                    self._do_release(cell, early=False)
                    released_agents.append(cell.agent_id)

        for agent_id in released_agents:
            logger.info("✅ Agent '%s' has served their sentence and is released.", agent_id)

        return released_agents

    def get_cell(self, agent_id: str) -> Optional[BrigCell]:
        """
        Retrieve the BrigCell for a given agent (current or past).

        Args:
            agent_id: The agent's unique identifier.

        Returns:
            The BrigCell if it exists, None otherwise.
        """
        with self._lock:
            return self._cells.get(agent_id)

    def roster(self) -> List[BrigCell]:
        """
        Return a list of all currently detained agents.

        Returns:
            List of active BrigCells.
        """
        with self._lock:
            return [c for c in self._cells.values() if not c.released]

    def history(self) -> List[BrigCell]:
        """
        Return all BrigCells, including already-released agents.

        Returns:
            Full list of BrigCells.
        """
        with self._lock:
            return list(self._cells.values())

    def shutdown(self) -> None:
        """Shut down The Brig's warden thread gracefully."""
        self._shutdown.set()
        logger.info("The Brig is shutting down.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_release(self, cell: BrigCell, early: bool) -> None:
        """Mark a cell as released. Must be called with self._lock held."""
        cell.released = True
        cell.released_at = datetime.now(timezone.utc)
        cell.early_release = early

    def _warden_loop(self) -> None:
        """Background warden thread that checks for sentence completions."""
        logger.info("Warden reporting for duty aboard the Epyon.")
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=self._poll_interval)
            released = self.check_releases()
            if released:
                logger.info(
                    "Warden released %d agent(s): %s", len(released), released
                )
        logger.info("Warden standing down.")

    def __repr__(self) -> str:
        with self._lock:
            total = len(self._cells)
            active = sum(1 for c in self._cells.values() if not c.released)
        return f"TheBrig(active={active}, total_processed={total})"
