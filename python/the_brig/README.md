# ⚓ The Brig — Agent Containment System

> *Aboard the Epyon, agents who misbehave get thrown in The Brig.*

The Brig is an agent detention module for the Epyon agent framework. When an agent misbehaves — spamming calls, returning bad outputs, violating rules — it gets locked up for a set sentence duration. It cannot act while detained and is released automatically when its time is served, or by the Captain's direct order.

---

## 🔒 Features

- **Lock up** any agent for a configurable duration (seconds)
- **Automatic release** via a background warden thread
- **Manual release** for early pardons (Captain's orders)
- **Offense logging** — every infraction is recorded with timestamp and reason
- **Sentence extension** — repeat offenders can have their sentences extended
- **Full roster & history** — see who's currently detained and past records
- **Thread-safe** — built for concurrent multi-agent environments

---

## 🚀 Quick Start

```python
from python.the_brig import TheBrig

# Open The Brig with auto-release enabled
brig = TheBrig(auto_release=True, poll_interval_seconds=10.0)

# Lock up a misbehaving agent for 5 minutes
brig.lock_up(
    agent_id="agent-007",
    reason="Repeated unauthorized tool calls",
    duration_seconds=300,
    sentenced_by="Volta",
)

# Check if an agent is currently locked up
if brig.is_locked_up("agent-007"):
    print("Agent is in The Brig — stand down!")

# See who's currently detained
for cell in brig.roster():
    print(cell.summary())

# Early release by the Captain
brig.release("agent-007", released_by="Captain")

# Shut down the warden when done
brig.shutdown()
```

---

## 📋 API Reference

### `TheBrig(auto_release=True, poll_interval_seconds=10.0)`

Initialize The Brig.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `auto_release` | `bool` | `True` | Auto-release agents when sentence is served |
| `poll_interval_seconds` | `float` | `10.0` | How often the warden checks for releases |

---

### `lock_up(agent_id, reason, duration_seconds, sentenced_by="Volta")`

Lock an agent in The Brig.

| Parameter | Type | Description |
|---|---|---|
| `agent_id` | `str` | Unique ID of the misbehaving agent |
| `reason` | `str` | Description of the offense |
| `duration_seconds` | `float` | Sentence length in seconds |
| `sentenced_by` | `str` | Who issued the sentence |

Returns a `BrigCell` object. If the agent is already detained, the sentence is extended if the new duration is longer, and the offense is logged.

---

### `is_locked_up(agent_id) -> bool`

Returns `True` if the agent is currently detained.

---

### `release(agent_id, released_by="Captain") -> bool`

Early release by captain's orders. Returns `True` if successful.

---

### `check_releases() -> List[str]`

Manually trigger a check for agents whose sentence is served. Useful when `auto_release=False`. Returns a list of released agent IDs.

---

### `get_cell(agent_id) -> Optional[BrigCell]`

Retrieve the `BrigCell` for an agent (current or past detainee).

---

### `roster() -> List[BrigCell]`

Returns all currently detained agents.

---

### `history() -> List[BrigCell]`

Returns full detention history, including released agents.

---

### `shutdown()`

Gracefully shut down the warden thread.

---

## 🗂️ Data Classes

### `BrigCell`

Represents an agent's detention record.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | The detained agent's ID |
| `locked_at` | `datetime` | When the agent was locked up |
| `release_at` | `datetime` | Scheduled release time |
| `offenses` | `List[BrigOffense]` | Log of all offenses |
| `released` | `bool` | Whether the agent has been released |
| `released_at` | `Optional[datetime]` | When they were released |
| `early_release` | `bool` | Whether it was an early release |
| `sentence_duration` | `timedelta` | Total sentence length |
| `time_remaining` | `timedelta` | Time left in sentence |
| `is_sentence_served` | `bool` | Whether the sentence is complete |

Call `cell.summary()` for a formatted status printout.

---

### `BrigOffense`

A single offense record.

| Field | Type | Description |
|---|---|---|
| `reason` | `str` | The offense description |
| `timestamp` | `datetime` | When the offense was recorded |
| `sentenced_by` | `str` | Who issued the sentence |

---

## 🛡️ Integration Example

```python
from python.the_brig import TheBrig

brig = TheBrig()

def run_agent(agent_id: str, task: callable):
    """Run a task for an agent, checking if they're in The Brig first."""
    if brig.is_locked_up(agent_id):
        cell = brig.get_cell(agent_id)
        raise PermissionError(
            f"Agent '{agent_id}' is in The Brig. "
            f"Time remaining: {cell.time_remaining}. "
            f"Last offense: {cell.offenses[-1].reason}"
        )
    try:
        return task()
    except Exception as e:
        # Lock the agent up for bad behavior
        brig.lock_up(
            agent_id=agent_id,
            reason=str(e),
            duration_seconds=120,
        )
        raise
```

---

*Maintained by Volta — Officer aboard the Epyon. 🚀*
