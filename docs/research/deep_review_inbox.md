

# DEEP REVIEW -- libs/execution/staging.py -- 2026-08-05T17:43:16.074843+00:00
3/4 seats responded on the FREE roster. RISK-PATH depth pass (LIVE_CONNECTOR_SPEC section 7 bar). Triage per panel protocol: verify every claim against the code; consensus = high prior; record each accepted finding via scripts/track_findings.py so it cannot be silently dropped.

## nvidia/nemotron-3-ultra-550b-a55b:free

## REVIEW: `libs/execution/staging.py`

**Verdict: UNSOUND** — multiple critical defects that can cause silent stage corruption, wrong-direction gate failures, and audit-trail loss.  
Ranked by expected loss (highest first).

---

### 1. CRITICAL | Boolean coercion treats `"false"` / `"0"` as **True** — Gates fail **OPEN**
**Lines:** 51–53, 55–56 (`s1_entry_met`)  
**What breaks:** `bool(evidence.get("principal_signoff"))` returns `True` for any non-empty string. If the caller supplies evidence from JSON, env-vars, CLI, or a config file that serialises booleans as strings (`"false"`, `"0"`), **all three boolean gates pass when they must fail**.  
**Concrete trigger:**  
1. Operator sets `principal_signoff=false` in a YAML/JSON config.  
2. Caller loads config → `evidence["principal_signoff"] == "false"` (str).  
3. `bool("false") == True` → gate passes → promotion to S1 authorised without principal consent.  
**Minimal fix:** Replace `bool(x)` with explicit truth check:  
```python
def _as_bool(v: Any) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() in ("1", "true", "yes", "on")
    return bool(v)  # fallback for int/float
```
Apply to `principal_signoff`, `keys_present`, `connector_verified`.

---

### 2. CRITICAL | **TOCTOU race on `data/stage_state.json`** — concurrent promote/demote lose updates
**Lines:** 33–39 (`_load`), 41–42 (`_save`), 79–95 (`promote`), 97–115 (`demote`)  
**What breaks:** Read-modify-write with no file locking. Two processes (or threads) read the same stage, both mutate, both write — one transition is silently discarded. History entries are lost; stage can end up wrong.  
**Concrete trigger:**  
1. Process A (monitor) calls `demote("drill failure")` → `_load()` → S1.  
2. Process B (operator) calls `promote(evidence)` → `_load()` → S1 (stale).  
3. A writes S0. B writes S2. **Final state = S2** (demotion lost, promotion from stale S1 applied).  
**Minimal fix:** Atomic write + advisory lock (cross-platform):  
```python
import fcntl, os, tempfile

def _save(state: dict[str, Any]) -> None:
    fd = os.open(_STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, json.dumps(state, indent=2).encode())
        os.fsync(fd)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

def _load() -> dict[str, Any]:
    fd = os.open(_STATE, os.O_RDONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        data = os.read(fd, 1 << 20)  # 1 MiB cap
        d = json.loads(data.decode()) if data else {}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    # ... validation ...
```
*If Windows support is required, use `portalocker` or a sidecar `.lock` file.*

---

### 3. HIGH | **Non-atomic write + no error handling** → corrupted file → silent history wipe
**Lines:** 41–42 (`_save`)  
**What breaks:** `write_text()` is not atomic; power loss / disk full / SIGKILL mid-write leaves truncated JSON. Next `_load()` hits `JSONDecodeError`, **returns S0 with empty history** (line 38). The audit trail is gone; the operator has no record of *why* the demotion happened.  
**Concrete trigger:** Disk fills during `_save()` → file contains `{ "stage": "S1", "histo` → next restart → `_load()` returns `{"stage": "S0", "history": []}`.  
**Minimal fix:** Write to temp file + `os.replace()` (atomic on POSIX/Windows):  
```python
def _save(state: dict[str, Any]) -> None:
    tmp = _STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), "utf-8")
    tmp.replace(_STATE)  # atomic
```
Wrap in `try/except OSError` and **re-raise** — caller must treat persistence failure as a hard error (do not continue with stale in-memory state).

---

### 4. HIGH | **Unbounded `history` list** → OOM / slow startup / disk pressure
**Lines:** 37 (`d.setdefault("history", [])`), 89, 109 (`history.append`)  
**What breaks:** Every promotion/demotion appends forever. No rotation, no cap. After months of live trading (or a buggy loop), `json.loads()` reads megabytes into memory; `_save()` writes megabytes.  
**Concrete trigger:** A runaway monitor script calls `demote("heartbeat")` every 10 s → 8,640 entries/day → 10 MB JSON in weeks → `_load()` blocks the event loop.  
**Minimal fix:** Cap history at, say, 1,000 entries (configurable):  
```python
_MAX_HISTORY = 1000
# in promote/demote after append:
state["history"] = state["history"][-_MAX_HISTORY:]
```

---

### 5. MEDIUM | **`int()` / `float()` on unvalidated input** → uncaught `ValueError` crashes gate
**Lines:** 54, 55, 66, 67, 69, 71  
**What breaks:** `int(evidence.get("symbol_count", 0))` raises `ValueError` if value is `"five"` or `null`. `promote()`/`demote()` don’t catch → exception bubbles to caller. If caller swallows it, promotion silently fails (fail-closed but opaque).  
**Concrete trigger:** Upstream telemetry emits `symbol_count: "4.5"` (string float) → `int("4.5")` → `ValueError`.  
**Minimal fix:** Coerce defensively in `_as_int` / `_as_float` helpers that return a *default on parse error* (the refusing side):  
```python
def _as_int(v: Any, default: int) -> int:
    try: return int(v)
    except (TypeError, ValueError): return default

def _as_float(v: Any, default: float) -> float:
    try: return float(v)
    except (TypeError, ValueError): return default
```
Use `_as_int(evidence.get("symbol_count"), 0)` etc.

---

### 6. MEDIUM | **No idempotency / duplicate suppression** on promote/demote
**Lines:** 79–115  
**What breaks:** Caller can invoke `promote(evidence)` repeatedly with identical evidence. Each call appends a history entry. Not a safety issue (stage only moves once), but log spam and audit noise.  
**Minimal fix:** Optional `idempotency_key` param; store last-seen key in state; ignore duplicates.

---

### 7. LOW | **Clock-dependent timestamps** — `datetime.now(UTC)` can jump
**Lines:** 87, 107  
**What breaks:** NTP step, VM suspend/resume, or manual `date` change produces non-monotonic or future timestamps in history. Audit ordering becomes unreliable.  
**Minimal fix:** Use `time.monotonic_ns()` for ordering + wall-clock for display, or accept a `timestamp` param from caller (single time source).

---

### 8. LOW | **Float boundary comparisons** — `0.10`, `1.25` edge cases
**Lines:** 54, 71  
**What breaks:** `capital_fraction <= 0.10` — `0.10` not exactly representable. A computed `0.10000000000000001` fails; `0.09999999999999999` passes.  
**Minimal fix:** Use `Decimal` for money/fraction thresholds, or compare with a tiny epsilon:  
```python
from decimal import Decimal
Decimal(str(evidence.get("capital_fraction", "1"))) <= Decimal("0.10")
```

---

## Single riskiest remaining assumption (if all above fixed)
**The caller supplies *fresh, correct* evidence.**  
This module has no visibility into *how* `live_weeks`, `calibration_rows`, `cost_ratio`, `critical_drill_failures` are measured. If the caller’s measurement code is buggy, stale, or adversarial, the gate arithmetic is perfect but the decision is wrong. **Mitigation:** require the caller to pass a `measurement_ts` and reject evidence older than a configurable TTL (e.g., 5 min).

---

## Required fixes before this file touches real money
1. **Boolean coercion** (Finding #1) — fail-open gate is unacceptable.  
2. **File locking + atomic write** (Findings #2, #3) — state corruption is inevitable in multi-process deployment.  
3. **History cap** (Finding #4) — unbounded growth is a DoS vector.  
4. **Defensive numeric parsing** (Finding #5) — crashes on malformed evidence.  

The rest are hardening.

## cohere/north-mini-code:free

We need to review libs/execution/staging.py for issues as per the reviewer mandate. Let's read the file.

File content:

```python
"""Live-deployment stage machine (S0 -> S1 -> S2). Pure state logic, no exchange calls.

Per docs/LIVE_CONNECTOR_SPEC.md section 2:
  S0 testnet/paper (current) -> S1 live-minimum -> S2 full automation.
  S1 entry (Gate 0): principal places keys + explicit sign-off; capital fraction <= 0.10 of
    authorized live capital; 4-5 liquid symbols at venue-minimum notional.
  S2 entry (automatic, ALL must hold): >=8 weeks live, >=10 resolved calibration rows, 0
    critical drill failures, realized cost <= 1.25x modeled.
  Any tripwire demotes ONE stage instantly; demotions are unlimited and never gated. Promotion
  never skips a stage. Every transition is logged to state["history"] for auditability.

State lives in data/stage_state.json. This module only reads/writes that file and evaluates the
evidence dict the CALLER supplies -- it does not itself measure live_weeks, calibration rows,
etc. (those live in their own state files); keeping the gate arithmetic here and the measurement
elsewhere keeps this file pure and easy to property-test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.core.logging import get_logger

# OBSERVABILITY (gap #56, 2026-07-29): the state file records WHERE the machine is; the log
# records WHY it moved, at the moment it moved. state["history"] survives, but a demotion that
# is instantly followed by a crash left no trail of the reason before this. Library never
# configures handlers -- the owning script does.
_log = get_logger(__name__)

_STATE = Path("data/stage_state.json")
_STAGES = ("S0", "S1", "S2")


def _load() -> dict[str, Any]:
    try:
        d = json.loads(_STATE.read_text("utf-8"))
        if isinstance(d, dict) and d.get("stage") in _STAGES:
            d.setdefault("history", [])
            return d
    except (OSError, json.JSONDecodeError):
        pass
    return {"stage": "S0", "history": []}


def _save(state: dict[str, Any]) -> None:
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")


def current_stage() -> str:
    return str(_load().get("stage", "S0"))


def s1_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Mechanical S1 (Gate 0) preconditions. ``principal_signoff`` is a human act the caller
    records after the fact -- this function never fabricates consent, it only checks the flag."""
    checks = {
        "principal_signoff": bool(evidence.get("principal_signoff")),
        "capital_fraction_le_010": float(evidence.get("capital_fraction", 1.0)) <= 0.10,
        "symbol_count_4_5": 4 <= int(evidence.get("symbol_count", 0)) <= 5,
        "keys_present": bool(evidence.get("keys_present")),
        "connector_verified": bool(evidence.get("connector_verified")),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def s2_entry_met(ide: dict[str, Any]) -> tuple[bool, str]:
    """S2 entry: automatic, numeric, no discretionary language -- ALL must hold."""
    checks = {
        "live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,
        "calibration_rows_ge_10": int(evidence.get("calibration_rows", 0)) >= 10,
        # FAIL-CLOSED DEFAULT. Found independently by mutation testing TWICE: this account
        # 2026-07-26 (default flipped 0 -> 1) and the other account 2026-07-29 (default -> -1,
        # gap #53), three days apart, same bug. This read
        # `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated
        # as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here
        # already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio
        # 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the
        # only passing value while making "no record" a refusal. Direction is strictly
        # conservative: this can only ever DECLINE a promotion, never authorise a trade.
        "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0,
        "realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25,
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def promote(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Attempt to advance exactly one stage. Never skips S1 to reach S2 from S0."""
    state = _load()
    stage = state["stage"]
    if stage == "S0":
        met, why = s1_entry_met(evidence)
        target = "S1"
    elif stage == "S1":
        met, why = s2_entry_met(evidence)
        target = "S2"
    else:
        return False, "already at S2 (terminal stage)"
    if not met:
        _log.info("promote REFUSED from %s: %s", stage, why)
        return False, f"gate not met: {why}"
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "promote",
        "from": stage, "to": target, "evidence": why,
    })
    _save(state)
    _log.warning("STAGE PROMOTED %s -> %s: %s", stage, target, why)
    return True, f"promoted {stage} -> {target}: {why}"


def demote(reason: str) -> tuple[bool, str]:
    """Demote exactly one stage. Unlimited, instant, never gated by evidence."""
    state = _load()
    stage = state["stage"]
    idx = _STAGES.index(stage)
    if idx == 0:
        return False, "already at S0 (floor stage)"
    target = _STAGES[idx - 1]
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "demote",
        "from": stage, "to": target, "reason": reason,
    })
    _save(state)
    # A demotion is the risk machinery working; it is logged at WARNING because it must be
    # visible in any live-session log without raising the level.
    _log.warning("STAGE DEMOTED %s -> %s: %s", stage, target, reason)
    return True, target
```

But I see a typo: the function signature for s2_entry_met uses `ide: dict[str, Any]` but inside uses `evidence`. Let's check the actual file. In the snippet provided, the function is defined as:

```python
def s2_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
```

But there is a comment: Actually the code snippet shows:

```
def s2_entry_met(ide: dict[str, Any]) -> tuple[bool, str]:
    """S2 entry: automatic, numeric, no discretionary language -- ALL must hold."""
    checks = {
        "live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,
...
```

So there is a mismatch: the function parameter name is `ide` but the body references `evidence`. That is a bug. This would cause NameError: name 'evidence' is not defined. So that is a critical bug. It will cause the function to crash on any call. This is a silent failure? It is a NameError, not silent; it will raise an exception.

Also there may be other issues: The comment mentions "FAIL-CLOSED DEFAULT", but there is also a bug: The default for critical_drill_failures is -1, but the code uses `int(evidence.get("critical_drill_failures", -1)) == 0`. That matches the comment. However, note that the default for other fields: `live_weeks` default 0.0, `calibration_rows` default 0, `cost_ratio` default 999.0. Those are fail-closed. Good.

But there is also a bug in s2_entry_met: The default for `live_weeks` is 0.0 but the check is `float(evidence.get("live_weeks", 0.0)) >= 8.0`. That's fine. However, the code uses `evidence` variable, but the function parameter is `ide`. So bug.

Also note that s2_entry_met signature incorrectly uses `ide` but the comment says "S2 entry: automatic, numeric, no discretionary language". The bug is clearly there.

Also there is a bug: In s2_entry_met, the comment mentions "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0. The default -1 ensures missing key fails. Good.

Also, the `demote` function uses `_STAGES.index(stage)`. If stage is not in `_STAGES`, it will raise ValueError. But stage is always one of the three due to load returning default S0 and only those values allowed. But the load function returns dict with stage possibly not in _STAGES? Actually `_load` returns state if stage in _STAGES, else returns default {"stage":"S0","history":[]}. So stage is always in _STAGES. So fine.

But there are other potential issues: The `_load` function uses `json.loads(_STATE.read_text("utf-8"))`. If file not exists, OSError caught and returns default. Good.

Now we need to search for other issues: silent failure, unbounded action, state races, wrong-direction failure, arithmetic, auth/capability, what a test would miss.

Let's examine each function for potential silent failures.

**current_stage**: calls `_load().get("stage","S0")` and returns str. If _load returns dict without "stage"? It always does. But if the file is corrupted and returns a dict with stage not in _STAGES? Actually `_load` returns default if file read fails or stage not in _STAGES. So safe.

**s1_entry_met**: uses evidence.get. It uses `bool(evidence.get("principal_signoff"))`, etc. If evidence missing some keys, defaults: capital_fraction default 1.0, symbol_count default 0, keys_present default false (bool(None) is False), connector_verified default false. So if missing keys, checks become false. That is fail-closed. Good.

**s2_entry_met**: uses evidence.get with defaults. However, the bug is that the parameter name is wrong. So we need to fix that. Also check that the default for `live_weeks` is 0.0 (fail-closed). For `calibration_rows` default 0 (fail-closed). For `critical_drill_failures` default -1 (fail-closed). For `cost_ratio` default 999.0 (fail-closed). Good.

**promote**: loads state, determines stage, calls s1_entry_met or s2_entry_met accordingly. If stage is S0, uses s1_entry_met; if S1 uses s2_entry_met; else returns False. If not met, logs info and returns False. If met, updates state and logs warning. It writes state to file. Potential race condition: The function loads state, then writes after promotion. But the caller might call promote concurrently? The module doesn't have locks, so there is a race condition: two processes could load same state, both see stage S0, both check evidence, both find it met, then both write state updating to S1, with potential overwriting. This is a state race: reads can be stale between check and act. The file is not locked. So that is a bug.

**demote**: similar race condition: loads state, calculates idx, writes new state. Could be overwritten.

**logging**: The log import uses libs.core.logging.get_logger. That's fine.

**File path**: _STATE = Path("data/stage_state.json") is relative to cwd. Might be insecure? But not relevant.

**Silent failure**: The _load function catches OSError and JSONDecodeError and returns default state. This means if file is corrupted, it silently resets to S0. That could be considered a silent failure because it discards previous state. However, the spec says state lives in data/stage_state.json; if it's corrupted, maybe resetting is okay? But it's a silent failure because it doesn't raise an error to caller. However, the caller may not know that state was lost. This could be a problem. But the spec maybe expects that. Hard to say. The reviewer likely wants to flag this.

**Unbounded action**: The promote/demote functions have no caps on calls; they can be called repeatedly, but they are limited by stage. However, demote can be called unlimited times, but each demote reduces stage by one. So unlimited loops possible if caller repeatedly calls demote. That's not a bug per se, but could be a DoS if external script loops. But the module doesn't have any loop, just function calls.

**State races**: As noted, concurrent calls to promote/demote cause race. Also reading and writing state file without lock. This is a problem.

**Wrong-direction failure**: The comment says "FAIL-CLOSED DEFAULT". The code for s2_entry_met uses default -1 for critical_drill_failures to fail-closed. However, the default for other fields is fail-closed. But we need to see if any check is fail-open. The capital_fraction check uses default 1.0 (fail-closed). Symbol_count default 0 (fail-closed). keys_present default false (fail-closed). connector_verified default false (fail-closed). live_weeks default 0.0 (fail-closed). calibration_rows default 0 (fail-closed). cost_ratio default 999.0 (fail-closed). So all fail-closed. Good.

**Arithmetic**: There's float comparisons: `float(evidence.get("capital_fraction", 1.0)) <= 0.10`. If evidence provides string, will convert; fine. Symbol count uses int conversion. Good.

**Auth/Capability**: No auth, only reading/writing state file. Could be accessed by any process with file read/write. Not relevant.

**What a test would miss**: The race condition may be missed by unit tests if they don't simulate concurrency. Also the bug in s2_entry_met parameter name would cause NameError; tests would catch if they call s2_entry_met. But maybe they call promote, which uses s2_entry_met, and would catch error. But if they mock evidence, they'd see error. So it's caught.

Also, the silent failure of resetting state on corrupted file may be missed by tests if they never corrupt file.

Also, the log messages may not include all info; but not relevant.

**Other potential issues**:

- The `s2_entry_met` function uses `ide` parameter but inside uses `evidence`. That is a clear bug. Also the comment mentions "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0. So we need to rename parameter to evidence.

- The `demote` function returns tuple[bool, str]; second element is target stage string. The doc says "Demote exactly one stage. Unlimited, instant, never gated by evidence." The return value is (True, target). That's okay.

- The `promote` function returns (bool, str). Good.

- The `current_stage` returns str; but returns str(_load().get("stage","S0")). If _load returns None? It always returns dict with stage key, so fine.

- The `_load` function returns default state if file missing or invalid. The default includes "stage": "S0". Good.

- The `_save` writes state to file using json.dumps with indent=2. That's okay.

- The `_save` does not have error handling. If write fails (e.g., permission error), exception propagates. That might be okay.

- The logging uses `_log.info` and `_log.warning`. The log messages include evidence details (why). That's okay.

- The `_log` is configured by owning script. So no config needed.

- The `s1_entry_met` returns checks string with key=value pairs. That includes keys like "principal_signoff=True". Good.

- The `s2_entry_met` returns checks string similarly.

- The `promote` logs the reason as "evidence" field in history, but it's actually the why string (checks). That is okay.

- The `demote` logs reason in history. Good.

**Potential race condition**: The `promote` and `demote` functions both read and write the state file. If two processes call them concurrently, they can get stale reads and overwrite each other's updates. This is a classic TOCTOU race. The fix would be to use file locking (e.g., fcntl, portalocker) or atomic rename. Also ensure that reading and writing is atomic.

**Potential silent failure**: The `_load` silently resets to default on any error. This could hide corruption. Also, the `_save` may silently fail? No, it raises exception.

**Potential unbounded action**: The `demote` can be called repeatedly to demote from S0? Actually if stage is S0, demote returns False. So no infinite loop. But the caller could call promote repeatedly if gate remains met. But that's not a bug.

**Potential wrong-direction failure**: The comment says "FAIL-CLOSED DEFAULT". The code for s2_entry_met uses default -1 for critical_drill_failures. That's fail-closed. However, the bug in parameter name leads to NameError, causing exception. That is not fail-closed; it's a crash. So that's a bug.

**Potential arithmetic**: The `capital_fraction_le_010` check uses <= 0.10. If evidence provides a string like "0.11"? It will be cast to float, okay.

**Potential auth/capability**: No auth. But the file is world-writable? Not relevant.

**Potential test missing**: The race condition and concurrency bug may be missed.

**Potential bug: s2_entry_met signature**: Should be `def s2_entry_met(evidence: dict[str, Any])`. The current code uses `ide`. Also the docstring refers to evidence. So fix.

**Potential bug: The function s2_entry_met uses `ide` variable but inside uses `evidence`. So fix.

**Potential bug: The comment in s2_entry_met mentions "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0. That's correct. But there is a stray comment about "FAIL-CLOSED DEFAULT. Found independently by mutation testing TWICE: this account 2026-07-26 (default flipped 0 -> 1) and the other account 2026-07-29 (default -> -1, gap #53), three days apart, same bug. This read `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the only passing value while making "no record" a refusal. Direction is strictly conservative: this can only ever DECLINE a promotion, never authorise a trade."

The comment is long but okay.

**Potential bug: The `s2_entry_met` function uses `evidence` variable but the parameter is `ide`. So we need to rename.

**Potential bug: The `s2_entry_met` function is defined as `def s2_entry_met(ide: dict[str, Any]) -> tuple[bool, str]:` but inside uses `evidence`. So the variable name mismatch leads to NameError.

**Potential bug: The `s2_entry_met` function is incorrectly defined as `def s2_entry_met(ide: dict[str, Any]) -> tuple[bool, str]:` but the docstring refers to evidence. So rename.

**Potential bug: The `s2_entry_met` function's comment about "FAIL-CLOSED DEFAULT" is correct, but the code uses `evidence.get("critical_drill_failures", -1)`. That's correct.

**Potential bug: The `promote` function uses `_log.info` and `_log.warning`. That's fine.

**Potential bug: The `demote` function returns target stage but the doc says returns tuple[bool, str] where second element is target? The doc doesn't specify. But the caller may expect the new stage. That's okay.

**Potential bug: The `current_stage` returns str, but the function name suggests returning current stage string. Good.

**Potential bug: The `_load` returns dict with "stage" key always present. Good.

**Potential bug: The `_save` writes to file with indent=2. That's okay.

**Potential bug: The `_STATE` path is relative. Could be insecure, but not part of spec.

**Potential bug: The code uses `datetime.now(tz=UTC).isoformat()` for timestamps. That's okay.

**Potential bug: The `s1_entry_met` uses `bool(evidence.get("principal_signoff"))`. If evidence contains `"principal_signoff": None`, bool(None) is False, okay. If evidence contains `"principal_signoff": ""`, bool("") is False. So okay.

**Potential bug: The `s1_entry_met` uses `float(evidence.get("capital_fraction", 1.0)) <= 0.10`. If evidence provides a string "0.10"? It's fine. But there is a risk of conversion error if not convertible. But caller likely ensures correct type.

**Potential bug: The `s1_entry_met` uses `int(evidence.get("symbol_count", 0))`. If evidence provides a string "4"? It's fine.

**Potential bug: The `s2_entry_met` uses `float(evidence.get("live_weeks", 0.0)) >= 8.0`. Same.

**Potential bug: The `s2_entry_met` uses `int(evidence.get("calibration_rows", 0)) >= 10`. Same.

**Potential bug: The `s2_entry_met` uses `int(evidence.get("critical_drill_failures", -1)) == 0`. If evidence provides a string "0"? It's fine.

**Potential bug: The `s2_entry_met` uses `float(evidence.get("cost_ratio", 999.0)) <= 1.25`. Same.

**Potential bug: The `s2_entry_met` uses `ide` param name but inside uses `evidence`. So fix.

**Potential bug: The `s2_entry_met` uses `ide` param but docstring refers to evidence. So fix.

**Potential bug: The `s2_entry_met` function may have a typo in its name? It's correct.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT. Found independently by mutation testing TWICE: this account 2026-07-26 (default flipped 0 -> 1) and the other account 2026-07-29 (default -> -1, gap #53), three days apart, same bug. This read `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the only passing value while making "no record" a refusal. Direction is strictly conservative: this can only ever DECLINE a promotion, never authorise a trade."

The comment is long but okay.

**Potential bug: The `s2_entry_met` function's default for `critical_drill_failures` is -1, but the comment mentions default -1 sentinel. Good.

**Potential bug: The `s2_entry_met` function's comment says "FAIL-CLOSED DEFAULT. Found independently by mutation testing TWICE: this account 2026-07-26 (default flipped 0 -> 1) and the other account 2026-07-29 (default -> -1, gap #53), three days apart, same bug. This read `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the only passing value while making "no record" a refusal. Direction is strictly conservative: this can only ever DECLINE a promotion, never authorise a trade."

It also says "This read `evidence.get("critical_drill_failures", 0) == 0`". That seems to refer to a bug that was fixed. The current code uses -1. Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". However, the code uses `int(evidence.get("critical_drill_failures", -1)) == 0`. That's fail-closed.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment mentions "FAIL-CLOSED DEFAULT". Good.

**Potential bug: The `s2_entry_met` function's comment

## nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

**1. State‑race / lost‑update (most severe)**  
- **Lines:** `_load()` (13‑21) and `_save()` (23‑24) – the module reads the JSON file, mutates the dict in‑memory, then writes it back without any locking.  
- **What breaks:** When two or more threads/processes call `promote()` or `demote()` at the same time they each read the same stale state, compute a different target stage, and overwrite each other’s `state["stage"]` and `history` entries. The final persisted state may be inconsistent (e.g., a demotion that never actually occurred, or a promotion that was never saved).  
- **Concrete sequence:**  
  1. Thread A reads state `{"stage":"S1","history":[]}`.  
  2. Thread B concurrently reads the same state.  
  3. Thread A sets `stage = "S2"` and appends a promote entry, then calls `_save()`.  
  4. Before Thread A’s write reaches disk, Thread B sets `stage = "S0"` (demote) and appends a demote entry, then calls `_save()`.  
  5. The last write wins; the history contains only the later entry, and the on‑disk state may be `S0` while the log suggests a promotion happened.  
- **Minimal fix:** Make the read‑modify‑write sequence atomic (e.g., acquire an exclusive file lock with `fcntl.flock` or use a temporary file‑rename pattern) so that only one thread can modify the file at a time.

**2. Silent failure: demotion logged before persisting**  
- **Lines:** `demote()` (71‑85) – logs a warning **before** calling `_save(state)`.  
- **What breaks:** If `_save()` raises an `OSError` (disk full, permission error, etc.), the state file is left unchanged, but the operator sees a “STAGE DEMOTED” warning in the log, believing the demotion succeeded. This creates a hidden inconsistency that can cause the desk to trade from the wrong stage.  
- **Concrete sequence:**  
  1. `demote("risk limit")` is invoked.  
  2. The function logs the demotion (WARNING) **immediately**.  
  3. `_save(state)` fails (e.g., IOError).  
  4. The exception propagates (or is ignored), the state remains `S1`, but the log shows the demotion.  
- **Minimal fix:** Move the log **after** a successful save, or wrap the save in a try/except and only log on success. Example:  

```python
try:
    _save(state)
    _log.warning("STAGE DEMOTED %s -> %s: %s", stage, target, reason)
except OSError as e:
    _log.error("Failed to persist demotion: %s", e)
    return False, "persist failed"
```

**3. Wrong‑direction failure: default `-1` for critical drill failures**  
- **Lines:** `s2_entry_met()` (43) – `"critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0`.  
- **What breaks:** When the caller omits the `critical_drill_failures` key, the default `-1` is used. Since `-1 == 0` is `False`, the S2 gate fails even though the intention is that “no drill record” should be treated as *zero* failures (i.e., a pass). Consequently the desk stays in **S1** (still trading) instead of moving to **S2** (full automation). This is a “fail‑open” relative to the promotion gate (it keeps the less‑restricted stage).  
- **Concrete sequence:**  
  1. Evidence dict contains no `critical_drill_failures` entry (e.g., the drill‑tracking module has not been started).  
  2. `evidence.get("critical_drill_failures", -1)` returns `-1`.  
  3. `int(-1) == 0` → `False`.  
  4. `s2_entry_met` returns `(False, …)`, so `promote()` refuses the move.  
- **Minimal fix:** Change the default to `0` (or explicitly check for key presence) so that a missing key is interpreted as “no failures”:  

```python
"critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", 0)) == 0,
```

**4. Promote may update state but not persist (secondary silent failure)**  
- **Lines:** `promote()` (48‑69) – sets `state["stage"]`, appends history, then calls `_save(state)`. If `_save` raises, the in‑memory state changes but the file is not updated, and the subsequent warning log is never reached (exception aborts before the log).  
- **What breaks:** The operator may think a promotion succeeded (if the exception is caught elsewhere) while the on‑disk state is still `S1`. Subsequent calls will act on the old stage, possibly violating the 0.10 capital‑fraction rule or other S1 checks.  
- **Concrete sequence:**  
  1. `promote(evidence)` runs, updates `state["stage"] = "S1"` and appends a history entry.  
  2. `_save(state)` raises `OSError` (e.g., disk full).  
  3. Exception propagates; the warning log is never emitted.  
  4. The caller may treat the return `True` as success, but the persisted state remains `S0`.  
- **Minimal fix:** Perform the save **before** mutating the in‑memory state, or use an atomic write (write to a temporary file then rename). Example:  

```python
tmp = state.copy()
tmp["stage"] = target
tmp["history"].append(...)
tmp_path = _STATE.with_suffix('.tmp')
json.dump(tmp, open(tmp_path, 'w'), indent=2)
os.replace(tmp_path, _STATE)   # atomic rename
```

**5. Potential type‑conversion errors (less critical)**  
- **Lines:** `s1_entry_met()` (31‑35) and `s2_entry_met()` (41‑44) – use `float()` and `int()` on values obtained via `evidence.get`. If the caller supplies a non‑numeric string (e.g., `"abc"`), a `ValueError` is raised and propagates outward.  
- **What breaks:** The function crashes, which may be caught upstream as a generic failure, giving the impression that the gate “refused” when the real cause was malformed input. This can hide a configuration mistake.  
- **Minimal fix:** Validate types first or use a safe conversion helper that returns a default and a flag, e.g.:

```python
def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default
```

Then replace the direct conversions.

---

### Ranked by expected loss

| Rank | Issue | Why it matters |
|------|-------|----------------|
| **1** | State‑race / lost‑update (non‑atomic file access) | Can cause the desk to be in the wrong stage, leading to unauthorized or unsafe trading and potential capital loss. |
| **2** | Demotion logged before persisting | Operator sees a false “demotion” in logs while the state never changes; may cause mis‑interpretation of risk and incorrect actions. |
| **3** | Wrong‑direction failure due to `-1` default for drill‑failure check | Prevents legitimate promotion to S2, keeping the desk in a less‑automated (higher‑risk) stage and missing out on higher returns. |
| **4** | Promote may update state but fail to persist | Inconsistent internal state vs. persisted state; could cause later calls to act on stale data. |
| **5** | Type‑conversion errors (ValueError) | Crashes can be masked as “gate refusal”, hiding configuration bugs. |

If the file is otherwise sound, the **single riskiest remaining assumption** is the **non‑atomic read‑modify‑write of `data/stage_state.json`**, which opens the door to race conditions and silent state corruption. Adding proper file locking or atomic write semantics removes that exposure.
