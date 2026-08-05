"""TRANSITIVE FRESHNESS (L1.54) -- an artifact is only as measured as the inputs it was built from.

THE CLASS THIS CLOSES, AND WHY THE FRESHNESS LAYER COULD NOT SEE IT. L1.44 put a max-age
contract at every decision-path READ, which answers "is the file I am reading current?" -- one
hop, and only about AGE. It cannot answer the question one level down: "was the producer of this
file able to read ITS inputs, or did it default them?" So an artifact can be young, well-formed,
pass every min_rows floor, satisfy its freshness contract, and still be FABRICATED END TO END.
Freshness does not compose, and nothing on this desk checked that it did.

THE PROVING INSTANCE, MEASURED 2026-08-05 AND STILL LIVE AT THE TIME OF WRITING:
`scripts/run_live_guard.py:167` reads `data/ramp_state.json` -- a file that HAS NEVER EXISTED on
this box -- through a `_load(path, {})` that returns its default for a missing file exactly as
for an empty one. The absent dict then flows into `state.get("size_fraction", SIZE_STEPS[0])`,
so the published artifact carries `"ramp": {"size_fraction": 0.1, "why": "blocked by:
a_cost_le_1_25x, b_live_sharpe_ge_0_6x_backtest, ...", "checks": {six keys, all false}}` -- six
conditions rendered as EVALUATED that were evaluated against nothing, and a ladder constant
rendered as a MEASUREMENT. `data/live_guard.json` is then consumed by the executor at
`run_cashcarry_executor.py:1487` through `read_fresh(max_age_h=0.25, min_rows=1)`, which reports
FRESH, and it sizes the book. `scripts/check_freshness.py` reports OK over the whole registry.
Every gate in the chain was green about an artifact built from a file that does not exist.

THE DIRECTION MATTERS AND IS NOT THE POINT. The ramp's own gate is fail-closed
(`ramp_gate._f` defaults every unreadable float to a value that FAILS its condition), so the
fabrication currently holds the book at the FLOOR rather than opening it -- conservative, not
loss-making. That is exactly why it survived every review: nobody audits a number that is
already small. But under L1.51 a clamp must carry a LIFTING CONDITION, and this clamp's lifting
condition is unevaluable -- its evidence file has no producer that has ever run. "Held at the
floor because the evidence failed" and "held at the floor because there is no evidence" are
different claims about the desk, and only one of them is true. Publishing the second as the
first is how a clamp becomes permanent without anyone deciding that it should.

THE MECHANISM. A producer declares the inputs it read, and the declaration is what gets
published beside the numbers:

    from libs.ops.input_provenance import Inputs

    inp = Inputs("run_live_guard._ramp")
    state = inp.read_json("data/ramp_state.json", default={}, max_age_h=168.0)
    ...
    report["ramp"] = {..., "provenance": inp.block(), "status": inp.status()}

`inp.status()` is the worst case over every declared input, and `inp.derived(value)` is the
refusal path: it returns the value when provenance permits a measurement and None when it does
not, so an UNMEASURED input cannot be published as a number by accident.

THE FIVE INPUT STATES, and each distinction is one the desk has paid for:
  * READ       -- the file existed, parsed, and was inside its declared age.
  * STALE      -- parsed, but older than the age the caller declared it could tolerate.
  * ABSENT     -- the path does not exist.
  * UNREADABLE -- the path exists but did not parse. DISTINCT FROM ABSENT BY DESIGN: the
    idiom this module replaces (`except (OSError, JSONDecodeError): return default`) collapses
    the two, and they demand opposite responses -- ABSENT means no producer has ever run (go
    build or schedule one), UNREADABLE means a producer ran and wrote garbage (go fix it, and
    suspect a torn write). A desk that cannot tell them apart debugs the wrong organ.
  * DEFAULTED  -- the caller substituted a value it did not read from anywhere. This is the
    state that makes a fresh stamp a lie, and it is recorded even when the substitution is
    harmless, because "harmless" is a judgement that ages badly.

THE ROLLUP, and the one rule that makes this a fence rather than a logger:
  OK         -- every declared input READ.
  DEGRADED   -- at least one STALE, none worse.
  UNMEASURED -- at least one ABSENT / UNREADABLE / DEFAULTED on a REQUIRED input,
                *or no inputs declared at all*.
ZERO DECLARED INPUTS CAN NEVER READ OK (L1.28a: unmeasured utilisation counts as zero
utilisation). An organ that forgets to declare is indistinguishable from one with nothing to
declare, and the safe reading of that ambiguity is the loud one.

WHAT THIS DELIBERATELY DOES NOT DO. It does not change any number, tighten any gate, or size
anything. It is a MEASUREMENT duty in the sense L1.51 uses the term: it puts a status on the
provenance of values the desk was already publishing, so that an absent input becomes arguable
instead of invisible. Nothing here can make the desk more timid; it can only make the desk
honest about which of its restraints were chosen and which were inherited from a missing file.

Recording is best-effort BY DESIGN, for the same reason `fresh.py` gives: a telemetry failure
must never break a money-path read. That is not a silent swallow -- an organ that declares
nothing surfaces at `scripts/check_input_provenance.py` as UNMEASURED, so the failure is still loud;
the reader is simply not the organ that screams.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent

#: The five input states, worst-last. Ordering IS the rollup: `max(..., key=_RANK.index)`.
READ = "READ"
STALE = "STALE"
DEFAULTED = "DEFAULTED"
UNREADABLE = "UNREADABLE"
ABSENT = "ABSENT"

_RANK: tuple[str, ...] = (READ, STALE, DEFAULTED, UNREADABLE, ABSENT)

#: Artifact-level rollups.
OK = "OK"
DEGRADED = "DEGRADED"
UNMEASURED = "UNMEASURED"

#: Input states that mean "this value was not measured" rather than "this value is old".
_FABRICATING: frozenset[str] = frozenset({DEFAULTED, UNREADABLE, ABSENT})


@dataclass
class InputRecord:
    """One declared input and what actually happened when it was read."""

    path: str
    status: str
    age_h: float | None = None
    max_age_h: float | None = None
    required: bool = True
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"path": self.path, "status": self.status}
        if self.age_h is not None:
            d["age_h"] = round(self.age_h, 3)
        if self.max_age_h is not None:
            d["max_age_h"] = self.max_age_h
        if not self.required:
            d["required"] = False
        if self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class Inputs:
    """Recorder for one producer's inputs. One instance per artifact written.

    `caller` names the organ and function, matching `fresh.read_fresh`'s convention so the two
    registries join on the same key.
    """

    caller: str
    records: list[InputRecord] = field(default_factory=list)

    # -- reading ---------------------------------------------------------------------------
    def read_json(self, path: str | Path, *, default: Any = None, max_age_h: float | None = None,
                  required: bool = True) -> Any:
        """Read a JSON artifact, RECORDING what happened, and return the parsed value or default.

        The return contract is deliberately identical to the `_load(p, default)` idiom this
        replaces, so a call site can adopt it without restructuring: the behaviour change is
        that the absence is now written down instead of vanishing into the default.
        """
        p = Path(path)
        if not p.is_absolute():
            p = _ROOT / p
        rel = self._rel(p)

        try:
            raw = p.read_text("utf-8")
        except FileNotFoundError:
            self.records.append(InputRecord(rel, ABSENT, required=required,
                                            detail="no such file -- has any producer ever run?"))
            return default
        except OSError as e:
            self.records.append(InputRecord(rel, UNREADABLE, required=required, detail=repr(e)))
            return default

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            self.records.append(InputRecord(rel, UNREADABLE, required=required,
                                            detail=f"exists but did not parse: {e!r}"))
            return default

        age_h = self._age_h(p, data)
        if max_age_h is not None and age_h is not None and age_h > max_age_h:
            self.records.append(InputRecord(rel, STALE, age_h=age_h, max_age_h=max_age_h,
                                            required=required))
        else:
            self.records.append(InputRecord(rel, READ, age_h=age_h, max_age_h=max_age_h,
                                            required=required))
        return data

    def defaulted(self, name: str, detail: str = "") -> None:
        """Record a value the caller substituted rather than read. See DEFAULTED above."""
        self.records.append(InputRecord(name, DEFAULTED, detail=detail))

    # -- verdicts --------------------------------------------------------------------------
    def status(self) -> str:
        """Worst-case rollup. NO DECLARED INPUTS IS UNMEASURED, NEVER OK (L1.28a)."""
        if not self.records:
            return UNMEASURED
        worst = max((r.status for r in self.records), key=_RANK.index)
        if worst == READ:
            return OK
        if worst == STALE:
            return DEGRADED
        # a non-required input may be absent without unmeasuring the artifact
        if any(r.status in _FABRICATING and r.required for r in self.records):
            return UNMEASURED
        return DEGRADED

    def fabricated(self) -> list[str]:
        """Declared inputs whose absence would make a published number a fabrication."""
        return [r.path for r in self.records if r.status in _FABRICATING and r.required]

    def measured(self) -> bool:
        return self.status() != UNMEASURED

    def derived(self, value: Any, *, unmeasured: Any = None) -> Any:
        """THE REFUSAL PATH. Return `value` only if provenance permits calling it a measurement.

        A caller that routes its published numbers through this cannot accidentally print a
        default as a finding -- which is the entire defect this module exists to prevent.
        """
        return value if self.measured() else unmeasured

    def block(self) -> list[dict[str, Any]]:
        """The `provenance` block to publish beside the numbers."""
        return [r.as_dict() for r in self.records]

    def why(self) -> str:
        """One line naming the absence, for an artifact's human-readable `why` field."""
        bad = [r for r in self.records if r.status in _FABRICATING and r.required]
        if not self.records:
            return "UNMEASURED: no inputs declared"
        if not bad:
            stale = [r.path for r in self.records if r.status == STALE]
            return f"DEGRADED: stale inputs {', '.join(stale)}" if stale else "inputs READ"
        return ("UNMEASURED: " + "; ".join(f"{r.path} {r.status}" for r in bad))

    # -- helpers ---------------------------------------------------------------------------
    @staticmethod
    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(_ROOT))
        except ValueError:
            return str(p)

    @staticmethod
    def _age_h(p: Path, data: Any) -> float | None:
        """Age from the artifact's OWN stamp where it has one, mtime otherwise.

        CONTENT OUTRANKS MTIME, for the reason `fresh.py` documents: the 10-minute auto-deploy
        and the puller's revert path rewrite files, so mtime lies FRESH after a deploy -- the
        dangerous direction. The stamp-key list is the desk's observed zoo, not a preference.
        """
        if isinstance(data, dict):
            for key in ("generated", "ts", "checked", "measured", "updated", "generated_at"):
                v = data.get(key)
                if isinstance(v, str):
                    try:
                        from datetime import datetime
                        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
                        return max(0.0, (time.time() - t.timestamp()) / 3600.0)
                    except ValueError:
                        continue
                if isinstance(v, (int, float)) and v > 1e8:  # epoch seconds
                    return max(0.0, (time.time() - float(v)) / 3600.0)
        try:
            return max(0.0, (time.time() - p.stat().st_mtime) / 3600.0)
        except OSError:
            return None
