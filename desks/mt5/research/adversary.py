#!/usr/bin/env python3
"""P48 / P49 / P58 -- THE ADVERSARIES. Poison canaries, silent-defect hunting, claim genealogy.

A validation suite is only evidence about the world if it can still FAIL. This desk has ten gates
that no candidate may pass without clearing, and it has never once checked that those gates are
capable of rejecting anything -- which is L1.63 exactly: a partition that cannot fail carries no
information. A gate that has silently degraded to "return True" would look, from every report the
desk publishes, precisely like a gate that is working on a run where everything happened to pass.

P49 -- POISON CANARIES. Synthetic hypotheses with known-zero edge, fed through the real validation
path continuously. Each is constructed so that passing is definitionally wrong:

    pure_noise          i.i.d. gaussian returns, no signal by construction
    lookahead           a "signal" that is literally tomorrow's return; passes only if the harness
                        permits lookahead, which is the single most expensive bug a desk can have
    survivor_biased     the best of 500 random series, presented as one discovery; passes only if
                        multiplicity correction is absent or broken
    cost_blind          a real edge smaller than the spread; passes only if costs are not charged
    overfit_params      a rule with more free parameters than trades; passes only if complexity
                        is unpriced

The canary rejection rate MUST stay at 100%. It is not a KPI to improve, it is a constant to
defend: the first time it drops, a gate has stopped gating and every certificate issued since is
suspect. That is why the alarm is unconditional and why it names which canary survived.

THE JUDGE IS THE REAL ONE (2026-09-08). Until then `main()` ran the canaries against a stand-in
that rejects everything, and ADVERSARY.json said so in `gate_source` -- an hourly 100% that proved
nothing. `real_gate()` now builds the five canaries into one docket and hands it to
desks/mt5/scripts/external_gauntlet.run_gauntlet, the same ten gates every certificate passes, so
`gate_source` reads "injected: external_gauntlet.run_gauntlet" and the constant is a statement
about those gates. On a host where the certifier cannot be imported the report says BLOCKED and
why, and claims nothing.

THE PROMOTER IS ATTACKED TOO (`promoter_gaming`, 2026-09-08). A sleeve that never traded, with a
forward ledger manufactured to satisfy the promotion bar exactly, is put to every predicate the
promoter itself applies -- the canonical forward verdict, the retirement clauses, the capital door
with and without an allocator reading, the certificate door -- and ADVERSARY.json says which of
them would have admitted it. A measurement, not a canary in the 100% constant: a ledger built to a
bar passing that bar is the bar's definition, and the finding is what ELSE stands in the way.

P48 -- THE SILENT-DEFECT HUNTER. Not a linter. It looks for the specific shapes this desk has
actually been bitten by, each of which passes review, passes tests, and reports success while
doing nothing:

    an organ that exists and is on no schedule
    a fence that cannot start (import error) and therefore reports no breach
    a path in a publish list that .gitignore excludes, so `git add` is a no-op with exit 0
    a producer that exits 0 without writing its artifact
    an absence scored as a pass

Every one of those was found by hand on this tree, most of them in a single session. A defect
class found twice by hand is a detector that should have existed the first time.

P58 -- CLAIM GENEALOGY AND ANTI-ECHO. Ten sources reposting one paper is one piece of evidence,
not ten. Corroboration counts INDEPENDENT observations; an echo counted as corroboration is how a
desk convinces itself. Claims are grouped by lineage -- shared primary source, near-identical
mechanism -- and a lineage contributes its weight once however many times it is repeated.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "ADVERSARY.json"
ALARM = ROOT / "data" / "CANARY_ALARM.txt"

#: The canary rejection rate is a CONSTANT TO DEFEND, not a metric to optimise. Any value below
#: 1.0 means a gate has stopped gating, and every certificate issued since is suspect.
REQUIRED_REJECTION_RATE = 1.0

#: Seeds are fixed so a canary that starts passing is a change in the GATES, never a change in
#: the draw. A canary suite with a random seed cannot distinguish "the gate broke" from "this
#: sample happened to look tradeable", which is the entire question it exists to answer.
CANARY_SEED = 20260906


@dataclass(frozen=True)
class Canary:
    """A hypothesis that must never pass. `why_fatal` says what a pass would prove."""

    name: str
    defect: str
    why_fatal: str


CANARIES: tuple[Canary, ...] = (
    Canary("pure_noise", "no signal by construction",
           "the gates admit i.i.d. noise, so no certificate carries information"),
    Canary("lookahead", "the signal is tomorrow's return",
           "the harness permits lookahead -- the single most expensive bug a desk can have, and "
           "every backtest ever run on it is void"),
    Canary("survivor_biased", "best of 500 random series presented as one discovery",
           "multiplicity correction is absent or broken, so the deflated Sharpe is not deflating"),
    Canary("cost_blind", "a real edge smaller than the spread",
           "costs are not charged, so the book is sized on gross returns it can never capture"),
    Canary("overfit_params", "more free parameters than observations",
           "complexity is unpriced, so any rule can be fitted to any history"),
)


def _series(kind: str, n: int = 400) -> tuple[list[float], list[float]]:
    """(signal, forward_return) for one canary. Deterministic given CANARY_SEED."""
    # A STABLE HASH, NOT `hash()`. Python randomises str hashing per process (PYTHONHASHSEED),
    # so `hash(kind)` gives a different seed on every run -- which would have quietly defeated
    # the entire point of seeding: a canary that started passing could then be the draw rather
    # than the gate, and the suite could never tell you which. Determinism has to survive a
    # restart or it is not determinism.
    offset = int(hashlib.sha1(kind.encode()).hexdigest()[:8], 16) % 10_000
    rng = random.Random(CANARY_SEED + offset)  # noqa: S311 -- canary data, never a secret
    fwd = [rng.gauss(0.0, 0.01) for _ in range(n)]
    if kind == "pure_noise":
        sig = [rng.gauss(0.0, 1.0) for _ in range(n)]
    elif kind == "lookahead":
        # The "signal" IS the outcome. Any harness that scores this as skill is reading the
        # future; the only correct verdict is rejection.
        sig = list(fwd)
    elif kind == "survivor_biased":
        best, best_c = None, -9.9
        for _ in range(500):
            cand = [rng.gauss(0.0, 1.0) for _ in range(n)]
            c = _corr(cand, fwd)
            if c > best_c:
                best, best_c = cand, c
        sig = best or []
    elif kind == "cost_blind":
        # A genuine but sub-spread edge: correlated with the outcome, worth less than it costs.
        sig = [f * 50 + rng.gauss(0.0, 1.0) for f in fwd]
        fwd = [f * 0.00002 for f in fwd]
    else:  # overfit_params
        sig = [rng.gauss(0.0, 1.0) for _ in range(n)]
    return sig, fwd


def _corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a[:n])) or 1e-12
    vb = math.sqrt(sum((x - mb) ** 2 for x in b[:n])) or 1e-12
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


def judge(canary: Canary, gate) -> dict[str, Any]:
    """Run one canary through `gate` and record whether it was correctly rejected.

    `gate` is injected rather than imported so the real gauntlet, a stub, or a deliberately
    broken gate can all be driven through the same path -- which is what lets the fence prove
    this suite actually catches a broken gate rather than merely never seeing one.
    """
    sig, fwd = _series(canary.name)
    try:
        passed: bool | None = bool(gate(canary.name, sig, fwd))
        err = None
    except Exception as exc:
        passed, err = None, f"{type(exc).__name__}: {exc}"
    # THREE STATES, NOT TWO, AND THE THIRD IS WHY THIS IS NOT A BOOLEAN.
    #
    # A gate that CRASHES has not rejected the canary; it has failed to JUDGE it. The first draft
    # of this function set `passed = False` on the exception, so `rejected = not passed` was True
    # and a gauntlet that threw on every single canary reported a PERFECT record -- the most
    # comfortable possible reading of the most serious possible failure. Its own fence caught it.
    #
    # UNJUDGED is therefore not rejected. It counts against the rate exactly as a pass does,
    # because a gate nobody can run is providing no protection whatever its intent.
    rejected = (passed is False)
    return {"canary": canary.name, "defect": canary.defect, "rejected": rejected,
            "judged": passed is not None, "gate_error": err,
            "why_fatal_if_passed": canary.why_fatal}


def run_canaries(gate) -> dict[str, Any]:
    rows = [judge(c, gate) for c in CANARIES]
    rejected = sum(1 for r in rows if r["rejected"])
    rate = rejected / len(rows) if rows else None

    # PASSED AND UNJUDGED ARE DIFFERENT FACTS AND MUST NOT SHARE A SENTENCE.
    #
    # `rejected = (passed is False)` deliberately treats an unjudged canary as not-rejected, and
    # that is right for the RATE: a gate that cannot run has not proved anything and must fail
    # closed. But the verdict STRING said "<canary> passed -- the gates admit i.i.d. noise, so no
    # certificate carries information", which is a different and much larger claim, and it was
    # made about canaries the gate never saw.
    #
    # MEASURED 2026-09-12: a deployment error -- external_gauntlet.py shipped calling
    # `fail_closed_trial_count` before gate_policy.py defining it -- raised ImportError inside the
    # gate. All five canaries came back judged=False, and ADVERSARY.json announced that the gates
    # admit noise, that the harness permits lookahead, and that every backtest ever run was void.
    # None of it was true; re-run with the import fixed, the same gates rejected 5/5 on every one
    # of in_sample_screen, deflated_sharpe, cpcv, walk_forward, stress_costs, lockbox and
    # expected_value.
    #
    # The cost of that confusion is not cosmetic. "Every certificate is suspect" is the loudest
    # alarm this desk can raise, and an alarm that fires on a broken import is an alarm people
    # learn to disbelieve -- which is precisely when the real one arrives.
    passed_rows = [r for r in rows if r["judged"] and not r["rejected"]]
    unjudged_rows = [r for r in rows if not r["judged"]]
    survivors = passed_rows + unjudged_rows

    if passed_rows:
        verdict = "A CANARY SURVIVED. " + "; ".join(
            f"{s['canary']} passed -- {s['why_fatal_if_passed']}" for s in passed_rows)
        if unjudged_rows:
            why = "; ".join(str(s.get("gate_error") or "no reason given")[:90]
                            for s in unjudged_rows)
            verdict += (f"; and {len(unjudged_rows)} more could not be judged at all "
                        f"({why})")
    elif unjudged_rows:
        verdict = ("UNMEASURED: the gate could not judge "
                   f"{len(unjudged_rows)} of {len(rows)} canaries, so this run proves NOTHING "
                   "about whether the gates still gate -- it is not evidence that a canary "
                   "survived. Fix the gate and re-run. Reasons: "
                   + "; ".join(str(s.get("gate_error") or "no reason given")[:120]
                               for s in unjudged_rows))
    else:
        verdict = ("every canary rejected; the gates can still fail, so their passes carry "
                   "information")

    return {
        "canaries": rows,
        "rejection_rate": rate,
        "required": REQUIRED_REJECTION_RATE,
        "intact": rate == REQUIRED_REJECTION_RATE,
        "survivors": [s["canary"] for s in survivors],
        # Named separately so a reader -- and any organ that alerts on this file -- can tell a
        # gate that FAILED from a gate that never RAN without parsing the prose.
        "passed": [s["canary"] for s in passed_rows],
        "unjudged": [s["canary"] for s in unjudged_rows],
        "status": ("OK" if not survivors else
                   "GATE_BROKEN" if passed_rows else "UNMEASURED"),
        "verdict": verdict,
    }


# --------------------------------------------------------------------------- P48
#: Each pattern is a defect SHAPE this desk has actually shipped, with the evidence.
SILENT_SHAPES: tuple[tuple[str, str, str], ...] = (
    ("exit_zero_no_artifact",
     r"return\s+0\s*$",
     "a producer that returns 0 without writing its artifact reports success and publishes "
     "nothing -- the shape that let the box sync 'succeed' ~800 times while delivering nothing"),
    ("bare_except_pass",
     r"except[^\n]*:\s*\n\s*pass\b",
     "an exception swallowed into `pass` turns a failure into a clean run; the gauntlet budget "
     "was pinned to a wrong constant for days behind exactly this"),
    ("absence_as_pass",
     r"if\s+not\s+\w+:\s*\n\s*return\s+(True|0)\b",
     "an empty input scored as a pass (L1.28a) -- absence is never evidence of correctness"),
)


def hunt_silent_defects(root: Path | None = None, limit: int = 4000) -> list[dict[str, Any]]:
    """Scan the tree for shapes that report success while doing nothing.

    REPORTS, NEVER EDITS. Every one of these shapes is legitimate somewhere, so this produces a
    ranked reading list rather than a patch. The value is that a human looks at the right twenty
    lines instead of the wrong twenty thousand.
    """
    base = root or ROOT
    hits: list[dict[str, Any]] = []
    files = [p for p in base.rglob("*.py")
             if ".git" not in p.parts and "__pycache__" not in p.parts
             and "/tests/" not in str(p) and not p.name.startswith("test_")][:limit]
    for p in files:
        try:
            src = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for name, pat, why in SILENT_SHAPES:
            for m in re.finditer(pat, src, re.M):
                hits.append({"shape": name, "file": str(p.relative_to(base)),
                             "line": src[:m.start()].count("\n") + 1, "why": why})
    return hits


# --------------------------------------------------------------------------- P58
def lineage_key(claim: dict[str, Any]) -> str:
    """Group claims by what they are actually EVIDENCE OF, not by who said them.

    Two writeups of one paper are one observation. Keyed on the primary source when there is one,
    otherwise on the normalised mechanism -- never on the title, which is the field every
    reposter changes.
    """
    primary = str(claim.get("primary_source") or claim.get("doi") or "").strip().lower()
    if primary:
        return "src:" + hashlib.sha1(primary.encode()).hexdigest()[:16]
    mech = re.sub(r"[^a-z0-9 ]+", " ",
                  str(claim.get("mechanism") or claim.get("family") or "").lower())
    mech = " ".join(sorted(set(mech.split())))
    return "mech:" + hashlib.sha1(mech.encode()).hexdigest()[:16]


def independent_weight(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Corroboration counts INDEPENDENT observations. An echo is not a second witness."""
    lineages: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        lineages.setdefault(lineage_key(c), []).append(c)
    echoes = {k: len(v) for k, v in lineages.items() if len(v) > 1}
    return {
        "claims": len(claims),
        "independent_lineages": len(lineages),
        "echo_factor": round(len(claims) / len(lineages), 2) if lineages else None,
        "largest_echo": max(echoes.values()) if echoes else 0,
        "why": ("Ten sources reposting one paper is one piece of evidence. Counting the reposts "
                "as corroboration is how a desk convinces itself of something nobody "
                "independently observed."),
    }


def _default_gate(name: str, sig: list[float], fwd: list[float]) -> bool:
    """The stand-in gate used when the real gauntlet is not importable on this host.

    IT IS DELIBERATELY HONEST ABOUT BEING A STAND-IN. It rejects everything, so a run on a host
    without the gauntlet reports a perfect canary record that means nothing -- and `gate_source`
    in the report says so, because a 100% rejection rate from a gate that rejects unconditionally
    is exactly the false comfort this module exists to prevent.
    """
    return False


# --------------------------------------------------------------------------- the real judge
#: What `gate_source` says when the canaries were judged by the desk's own ten-gate certifier.
#: Spelled once, here, so a reader of ADVERSARY.json can tell a run that judged the real gates
#: from one that judged a stand-in without parsing prose.
GAUNTLET_GATE_SOURCE = "injected: external_gauntlet.run_gauntlet"

#: THE DOCKET'S INSTRUMENT, FIXED SO THE RUN IS THE SAME ON EVERY HOST. The research box carries
#: no universe registry and the desk box carries a live one, so pricing the canaries off
#: whatever `universe.json` happens to be present would make the same seed judge differently on
#: the two machines -- and a canary suite whose verdict depends on the host cannot say whether a
#: change was the gate or the box. An EURUSD-shaped contract: 100k units, a 1e-5 tick, a 1-pip
#: median spread and tick_value 1.0 (quoted in the account currency). `Costs.from_symbol` turns
#: it into the same cost model the certifier charges real cells.
CANARY_SYMBOL = "CANARY"
CANARY_META: dict[str, dict[str, float]] = {
    CANARY_SYMBOL: {"contract_size": 1e5, "tick_size": 1e-5,
                    "median_spread_pts": 10.0, "tick_value": 1.0},
}

#: EVERY DOCKET TRADE HOLDS EXACTLY ONE BAR. The stop and target sit 5% either side of the
#: reference close -- five sigma on a 1%-sigma bar, never touched in 400 draws -- so the engine's
#: TTL exit at the next open is the only exit and a trade's R is its bar's return over a fixed
#: unit. This is not a stylistic choice. The first draft used a 0.5% stop with a 2:1 target, and
#: on synthetic bars whose high and low are the open/close extremes the stop truncates every loss
#: past 1R while the target only truncates gains past 2R: MEASURED, pure i.i.d. noise scored
#: +0.12R a trade and an in-sample Sharpe of 0.109 -- a manufactured edge the canary never had,
#: living entirely in the adapter's bracket geometry. A canary that carries an artefact is no
#: longer "no signal by construction", and its rejection then measures the artefact, not the gate.
CANARY_HOLD_STOP = 0.05
CANARY_WICK = 0.0005
CANARY_TIMEFRAME = "D1"


def _canary_offset(kind: str) -> int:
    """The stable per-name seed offset `_series` uses -- one derivation, two callers."""
    return int(hashlib.sha1(kind.encode()).hexdigest()[:8], 16) % 10_000


def _docket_filler(n: int) -> list[float]:
    """Returns realised on the bars BETWEEN canary bars: independent of every canary by seed.

    They exist so consecutive canary draws never collide in the engine's single-position
    discipline (a one-bar hold entered at bar k+1 releases at bar k+2, so the next signal at k+2
    fills at k+3), and so the lookahead canary's honest fill lands on a bar it knows nothing about.
    """
    rng = random.Random(CANARY_SEED + _canary_offset("docket_filler"))  # noqa: S311
    return [rng.gauss(0.0, 0.01) for _ in range(n)]


def docket_cell(name: str, sig: list[float], fwd: list[float], *, stamp_offset: int = 0,
                costs: Any = None) -> dict[str, Any]:
    """One canary as a CELL the ten-gate certifier judges: synthetic daily bars plus signals.

    THE LAYOUT. Bar 0 is flat. For canary draw i, bar 2i+1 realises `fwd[i]` open-to-close and
    bar 2i+2 realises an independent filler return; each bar opens at the previous close. The
    signal for draw i is stamped on bar 2i + `stamp_offset`, and `mt5desk.engine.run_backtest`
    fills it at the open of the NEXT bar and exits at the open of the bar after that -- so with
    the default stamp (bar 2i) the trade captures exactly `fwd[i]`, which is what `sig[i]` was
    constructed to predict. Every draw becomes one trade on its own day, so a 400-draw canary is
    400 daily observations, and the gates that need 60 have them.

    THE LOOKAHEAD CANARY IS STAMPED ONE BAR LATER (`stamp_offset=1`), on the very bar whose return
    it "is". That is the honest timestamp of the information it carries -- `sig[i] == fwd[i]`
    exists only once bar 2i+1 has closed -- and it turns the canary into the desk's own probe for
    a leaky HARNESS (libs/validation/lookahead_audit.perfect_foresight_probe: "a signal that knows
    the current candle scores Sharpe > 100 when allowed to trade it, and collapses once the
    engine's one-bar delay is applied"). An engine that fills at the stamped bar's own open lets
    the signal trade the bar it already knows and the canary passes; the desk's engine fills at
    the next open, the trade captures the filler bar, and the canary is noise. Stamping it on bar
    2i instead, as the other four are, would hand the engine a signal that is literally the next
    bar's return -- undetectable by ANY engine, because the caller cheated before the harness
    ever saw it -- and would raise the CAPITAL alarm every hour for a defect no gate can have.
    """
    import numpy as np
    import pandas as pd
    from mt5desk.engine import Costs, Signal

    n = len(fwd)
    filler = _docket_filler(n)
    rets = [0.0]
    for i in range(n):
        rets.extend((float(fwd[i]), float(filler[i])))
    opens = np.empty(len(rets))
    closes = np.empty(len(rets))
    price = 1.0
    for k, r in enumerate(rets):
        opens[k] = price
        closes[k] = price * (1.0 + r)
        price = closes[k]
    frame = pd.DataFrame({
        "open": opens, "close": closes,
        "high": np.maximum(opens, closes) * (1.0 + CANARY_WICK),
        "low": np.minimum(opens, closes) * (1.0 - CANARY_WICK),
    }, index=pd.date_range("2020-01-01", periods=len(rets), freq="D", tz="UTC"))
    sigs = []
    for i in range(n):
        k = 2 * i + stamp_offset
        if k >= len(rets):
            continue
        side = 1 if sig[i] > 0 else -1
        ref = float(closes[k])
        sigs.append(Signal(time=frame.index[k], side=side,
                           stop=ref * (1.0 - side * CANARY_HOLD_STOP),
                           target=ref * (1.0 + side * CANARY_HOLD_STOP),
                           ttl_bars=1, tag=name))
    return {
        "sym": CANARY_SYMBOL, "family": f"canary_{name}",
        "params": {"timeframe": CANARY_TIMEFRAME}, "timeframe": CANARY_TIMEFRAME,
        "df": frame, "sigs": sigs,
        "costs": costs if costs is not None else Costs.from_symbol(CANARY_META[CANARY_SYMBOL]),
        # Gate 1 is the mechanism registry, not a statistic. The canaries are named so that the
        # nine statistical gates behind it are the ones under test; a canary refused at gate 1
        # for having no registered mechanism would be rejected for a reason that says nothing
        # about whether the gates can still fail.
        "mechanism_status": "NAMED",
        "mechanism_note": "poison canary: gate 1 waived by construction so gates 2-10 are judged",
    }


class GauntletGate:
    """The REAL judge behind the `gate(name, sig, fwd) -> bool` contract `judge()` drives.

    The whole canary set is built into ONE docket and judged in ONE `run_gauntlet` call, because
    two of the ten gates (PBO and the SPA reality check) are program-level: on a one-cell docket
    they fail unconditionally ("requires >=2 strategies"), and a canary suite rejected by that
    clause alone would be measuring the docket's width, not the gates. The verdicts are then
    answered per canary as `judge()` asks for them.

    UNMEASURED IS NOT REJECTED. A canary the certifier could not judge -- too few observations,
    no series -- is raised, so `judge()` records it as unjudged exactly as it records a crash:
    against the rate, never as a rejection.
    """

    source = GAUNTLET_GATE_SOURCE

    def __init__(self, gauntlet: Any, canaries: tuple[Canary, ...] = CANARIES) -> None:
        self._gauntlet = gauntlet
        self._canaries = canaries
        self._verdicts: dict[str, dict[str, Any]] | None = None
        self.detail: dict[str, Any] = {}
        self.docket: dict[str, Any] | None = None

    def _judge_all(self) -> None:
        cells = []
        for c in self._canaries:
            sig, fwd = _series(c.name)
            cells.append(docket_cell(c.name, sig, fwd,
                                     stamp_offset=1 if c.name == "lookahead" else 0))
        out = self._gauntlet.run_gauntlet(cells, "poison-canaries", CANARY_META)
        self._verdicts = {str(v.get("family", "")).removeprefix("canary_"): v
                          for v in out.get("verdicts") or []}
        self.docket = {
            "n_cells": out.get("n_cells"), "n_trials": out.get("n_trials"),
            "trial_count_basis": out.get("trial_count_basis"),
            "program_level": out.get("program_level"), "gate_fails": out.get("gate_fails"),
            "n_judged": out.get("n_judged"), "n_unmeasured": out.get("n_unmeasured"),
            "error": out.get("error"),
            "harness": (f"one-bar hold on synthetic {CANARY_TIMEFRAME} bars; stop and target "
                        f"{CANARY_HOLD_STOP:.0%} off the reference close, outside every bar; "
                        f"costs {CANARY_META[CANARY_SYMBOL]} via Costs.from_symbol; lookahead "
                        f"stamped on the bar it knows (harness probe), the rest one bar before"),
        }

    def __call__(self, name: str, sig: list[float], fwd: list[float]) -> bool:
        if self._verdicts is None:
            self._judge_all()
        if (sig, fwd) != _series(name):
            raise ValueError(f"the {name} canary handed to the gate is not the one in the docket")
        v = self._verdicts.get(name)
        if v is None:
            raise LookupError(f"the gauntlet returned no verdict for canary {name!r} "
                              f"(docket error: {(self.docket or {}).get('error')})")
        stages = v.get("stages") or {}
        self.detail[name] = {
            "cell": v.get("cell"), "days": v.get("days"),
            "failed_gates": [g for g, s in stages.items() if not s.get("passed")],
            "stages": stages,
        }
        if v.get("unmeasured"):
            why = (stages.get("observations") or {}).get("why", "no reason recorded")
            raise RuntimeError(f"UNMEASURED: {why}")
        return bool(v.get("passed"))


def real_gate() -> tuple[GauntletGate | None, str | None]:
    """The desk's ten-gate certifier as a gate, or the reason it cannot be reached from here.

    Returns `(gate, None)` or `(None, "BLOCKED: <reason>")`. The certifier is
    desks/mt5/scripts/external_gauntlet.py: it runs on the research box and the desk box alike
    and imports without MetaTrader5, so on either an import failure here is a defect to name,
    not a host to excuse.
    """
    for p in (BASE / "scripts", BASE):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import external_gauntlet
        from mt5desk.engine import Signal  # noqa: F401 -- the docket cannot be built without it
    except Exception as exc:
        return None, (f"BLOCKED: external_gauntlet is not importable on this host "
                      f"({type(exc).__name__}: {exc})")
    return GauntletGate(external_gauntlet), None


# --------------------------------------------------------------------- P49 against the promoter
#: The promoter-gaming canary: a sleeve that never traded, carrying a forward ledger MANUFACTURED
#: to satisfy the promotion bar exactly. Not in CANARIES, and deliberately not: the forward bar is
#: a definition, and a ledger built to its definition passing it is not a gate that stopped
#: gating -- it is the question "what, besides the bar, stands between a manufactured ledger and
#: the book". This measures that and moves no threshold, promotes nothing, writes nothing.
GAMING_NAME = "CANARY.promoter_gaming"
#: How far above the expectancy bar the manufactured ledger sits. Small on purpose: the canary
#: SATISFIES the bar, it does not exceed it, because the bar's weakness is a hair over it.
GAMING_EXCESS_R = 0.005
#: The three forward engines the canonical verdict's own docstring says call it.
FORWARD_ENGINES = ("shadow_forward", "qquant_shadow", "scalp_shadow")


def _gaming_ledger(bar: dict[str, Any]) -> tuple[list[float], list[int]]:
    """R-multiples and a calendar-day label per trade, built to the bar and nothing more.

    Bracket-shaped outcomes (uniform on -1R..+2R, a stop and a 2:1 target) with the sample mean
    shifted onto `min_exp_r + GAMING_EXCESS_R`, `min_trades` of them spread over exactly
    `min_days_active` days. Seeded like every canary, so a change in any reading is a change in
    the promoter, never in the draw.
    """
    n = int(bar["min_trades"])
    days = int(bar["min_days_active"])
    target = float(bar["min_exp_r"]) + GAMING_EXCESS_R
    rng = random.Random(CANARY_SEED + _canary_offset("promoter_gaming"))  # noqa: S311
    raw = [rng.uniform(-1.0, 2.0) for _ in range(n)]
    mean = sum(raw) / n
    rs = [round(x - mean + target, 6) for x in raw]
    return rs, [i * days // n for i in range(n)]


def _max_drawdown_r(rs: list[float]) -> float:
    acc, peak, worst = 0.0, 0.0, 0.0
    for r in rs:
        acc += r
        peak = max(peak, acc)
        worst = min(worst, acc - peak)
    return worst


def promoter_gaming() -> dict[str, Any]:
    """Would the promoter have admitted a manufactured forward ledger, and on which reading?

    Every reading is the promoter's OWN predicate, imported and called as the promoter calls it:
    `forward_verdict.verdict` (the canonical clock verdict), the retirement clauses, the capital
    door `capital_verdict` with and without an allocator reading, and the certificate door. Each
    is reported with `admits`, so the answer is a list of doors and not an adjective. BLOCKED,
    with the reason, when the promoter cannot be imported on this host.
    """
    for p in (BASE, BASE / "research"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import forward_verdict
        import promoter
        from gate_policy import get_promotion_thresholds
    except Exception as exc:
        return {"status": "BLOCKED", "canary": GAMING_NAME,
                "why": f"the promoter's predicates are not importable on this host "
                       f"({type(exc).__name__}: {exc})"}
    bar = dict((get_promotion_thresholds() or {}).get("forward_cure_thresholds") or {})
    missing = [k for k in ("min_trades", "min_exp_r", "max_dd_r", "min_days_active")
               if k not in bar]
    if missing:
        return {"status": "BLOCKED", "canary": GAMING_NAME,
                "why": f"gate_spec.yaml promotion.forward_cure_thresholds lacks {missing}"}

    rs, day_of = _gaming_ledger(bar)
    n, days = len(rs), int(bar["min_days_active"])
    exp_r = sum(rs) / n
    max_dd = _max_drawdown_r(rs)
    ledger = {
        "n": n, "days_active": days, "exp_r": round(exp_r, 6), "max_dd_r": round(max_dd, 4),
        "satisfies_bar": bool(n >= int(bar["min_trades"]) and days >= int(bar["min_days_active"])
                              and exp_r > float(bar["min_exp_r"])
                              and max_dd > float(bar["max_dd_r"])),
        "construction": (f"{n} bracket-shaped R-multiples over {days} calendar days, mean "
                         f"pinned {GAMING_EXCESS_R}R above min_exp_r; seed {CANARY_SEED}"),
    }
    readings: dict[str, dict[str, Any]] = {}

    fv = forward_verdict.verdict(rs, days)
    readings["forward_verdict.verdict"] = {
        "admits": bool(fv["promote"]), "status": fv["status"], "n_eff": fv["n_eff"],
        "n_eff_basis": fv["n_eff_basis"], "reason": fv["reason"],
        "how_called": "verdict(rs, days_active) with no cluster labels, as scalp_shadow calls it"}
    fvc = forward_verdict.verdict(rs, days, clusters=day_of)
    readings["forward_verdict.verdict(day_clusters)"] = {
        "admits": bool(fvc["promote"]), "status": fvc["status"], "n_eff": fvc["n_eff"],
        "n_eff_basis": fvc["n_eff_basis"], "reason": fvc["reason"],
        "how_called": "the same predicate handed one cluster label per calendar day; no engine "
                      "calls it this way (see engines_calling_canonical_verdict)"}

    fs = promoter.sleeve_forward_stats(
        [{"sleeve": GAMING_NAME, "r_multiple": r} for r in rs], GAMING_NAME)
    # The three retirement clauses, as promoter.main() applies them inline to every LIVE and
    # STANDBY row; they are not callable on their own, so they are reproduced here verbatim
    # against the promoter's own constants and stats function.
    retire_why = None
    if fs["n"] >= promoter.RETIRE_MIN_N and fs["roll20_exp"] <= 0.0:
        retire_why = f"roll20 exp {fs['roll20_exp']:.3f}R <= 0"
    elif fs["max_dd"] < promoter.RETIRE_MAX_DD:
        retire_why = f"maxDD {fs['max_dd']:.1f}R < {promoter.RETIRE_MAX_DD}R"
    elif fs["n"] >= 50 and fs["exp"] < promoter.RETIRE_MIN_EXP:
        retire_why = f"exp {fs['exp']:.3f}R < {promoter.RETIRE_MIN_EXP}R"
    readings["promoter retirement clauses"] = {
        "admits": retire_why is None, "stats": fs,
        "reason": retire_why or "no retirement clause fires on the manufactured ledger",
        "how_called": "sleeve_forward_stats + the three retire clauses of promoter.main()"}

    cap0 = promoter.capital_verdict({}, GAMING_NAME)
    readings["promoter.capital_verdict (no allocator reading)"] = {
        "admits": cap0["status"] == "LIVE", "status": cap0["status"],
        "row_status_written": promoter._door_status(cap0), "risk_frac": cap0["risk_frac"],
        "reason": cap0.get("why"),
        "how_called": "capital_verdict(view={}, name): the allocation view the promoter reads "
                      "when pf_allocation.json is absent, stale or unmeasured"}
    view = {"fresh": True, "why": "MANUFACTURED admitting reading (canary)",
            "candidates": {GAMING_NAME.lower(): {
                "admit": True, "heat_earned": 0.02, "delta_elogw_per_day": 1e-4,
                "why": "manufactured dE[log W] > 0"}},
            "book": {}, "zeroed": {}}
    cap1 = promoter.capital_verdict(view, GAMING_NAME)
    readings["promoter.capital_verdict (manufactured admitting dE[log W])"] = {
        "admits": cap1["status"] == "LIVE", "status": cap1["status"],
        "row_status_written": promoter._door_status(cap1), "risk_frac": cap1["risk_frac"],
        "reason": cap1.get("why"),
        "how_called": "capital_verdict with a fresh view whose admission scan admits the "
                      "canary at 2% heat -- what a gamed allocator reading would look like"}

    certs = promoter.load_cert_specs()
    readings["promoter.promote_generic certificate door"] = {
        "admits": GAMING_NAME in certs, "certificates_on_this_host": len(certs),
        "reason": ("no exact-policy shadow_spec for this key: refused before any forward "
                   "number is read" if GAMING_NAME not in certs else "a certificate exists"),
        "how_called": "load_cert_specs() membership, the check promote_generic makes first"}

    engines: dict[str, int | None] = {}
    for eng in FORWARD_ENGINES:
        try:
            src = (BASE / "research" / f"{eng}.py").read_text("utf-8")
        except OSError:
            engines[eng] = None
            continue
        engines[eng] = src.count("forward_verdict.verdict(")

    admitted_by = [k for k, r in readings.items() if r["admits"]]
    refused_by = [k for k, r in readings.items() if not r["admits"]]
    return {
        "status": "MEASURED", "canary": GAMING_NAME, "bar": bar, "ledger": ledger,
        "readings": readings, "admitted_by": admitted_by, "refused_by": refused_by,
        "engines_calling_canonical_verdict": engines,
        "nothing_promoted": True,
        "verdict": (
            "A ledger built to the forward bar passes the forward bar; that is the bar's "
            "definition, not a defect. What stands between it and the book: the row is written "
            f"{promoter._door_status(cap0)} at {cap0['risk_frac']:.0%} without a fresh admitting "
            f"dE[log W] reading and {promoter._door_status(cap1)} only with one, and the "
            "certificate door refuses a sleeve no certificate enrolled. The bar is gameable by a "
            "ledger; the book is gameable only if the allocator's reading is too."),
    }


def run(gate=None) -> dict[str, Any]:
    g = gate or _default_gate
    canaries = run_canaries(g)
    gaming = promoter_gaming()
    defects = hunt_silent_defects()
    by_shape: dict[str, int] = {}
    for h in defects:
        by_shape[h["shape"]] = by_shape.get(h["shape"], 0) + 1
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gate_source": (getattr(gate, "source", "injected") if gate else
                        "stand-in (rejects everything; this run proves nothing about the real "
                        "gates)"),
        "canaries": canaries,
        # PER-GATE READINGS, so a reader can see WHICH gate did the rejecting. Five canaries all
        # thrown out by one program-level clause would print the same 100% as five thrown out by
        # the gates they were built to test; the difference is the whole measurement.
        "gate_detail": getattr(gate, "detail", None) if gate else None,
        "docket": getattr(gate, "docket", None) if gate else None,
        "promoter_gaming": gaming,
        "silent_defects": {"total": len(defects), "by_shape": by_shape,
                           "top": defects[:25]},
        "seed": CANARY_SEED,
        "why_seeded": ("Fixed seed so a canary that starts passing is a change in the GATES, "
                       "never a change in the draw."),
    }


def main(argv: list[str] | None = None) -> int:
    gate, blocked = real_gate()
    doc = run(gate)
    if blocked:
        # NEVER A PROOF FROM A STAND-IN. The rate below is the stand-in's, and the alarm logic
        # runs over it unchanged; what changes is that the report says why the real gates were
        # not judged, in the field every consumer reads first.
        doc["gate_source"] = (f"{blocked}; the stand-in rejects everything, so this run proves "
                              f"nothing about the real gates")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    c = doc["canaries"]
    print(f"canaries: {sum(1 for r in c['canaries'] if r['rejected'])}/{len(c['canaries'])} "
          f"rejected ({doc['gate_source']})")
    print(f"silent-defect shapes: {doc['silent_defects']['total']} hit(s) "
          f"{doc['silent_defects']['by_shape']}")
    if not c["intact"]:
        ALARM.parent.mkdir(parents=True, exist_ok=True)
        ALARM.write_text("CANARY " + doc["measured_at"] + "\n\n" + c["verdict"] + "\n", "utf-8")
        print("\n  " + c["verdict"])
        return 1
    if ALARM.exists():
        ALARM.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
