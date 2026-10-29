"""LEAD-LEVEL BLIND REPLICATION -- an important lead is re-derived by a SECOND implementation
before it is allowed to spend anything expensive (ledger M13, principal 2026-09-17).

WHERE `blind_reviewer` STOPS. It re-derives a CERTIFIED CELL: the right question at the last
possible moment, after the sweep, the gauntlet, the clock and the multiplicity charge every other
cell then had to clear. A lead is a claim plus a rule, and two things can be wrong with it before
any gate runs -- the rule may not be what the miner implemented, and the implementation may not be
what the rule says. Ten gates cannot tell those apart: every gate reads the SAME signals from the
SAME call over the SAME frames.

THE FOUR MOVES, AND THE ORDER IS THE ARGUMENT:

    1 SELECT   important = the desk is about to treat it as important: a candidate in the TOP
               DECILE of the registry's scored population, a CERTIFIED cell, or named by the
               daily research OS. Replication is spent where the next decision is
    2 FREEZE   `data/replication/<discovery_id>.json`: claim, mechanism, instruments, exact rule.
               No family, no parameter the rule did not declare, no evidence number, no payload,
               no generator. `forbidden_in` walks the copy and a leak REFUSES the hand-over
    3 REDO     the second implementation reads the FROZEN COPY AND NOTHING ELSE: its own bar
               reader (`independent_bars`, pyarrow straight off the parquet with its own
               normaliser, never `proposer_common.bars` or `blind_reviewer.load_bars`), its own
               family and parameters re-derived from the rule TEXT, then the desk's own cheap
               screen (`proposer_common.screen`) for n, a direction and a t
    4 COMPARE  only now is the first pass's reading read at all -- `first_reading` is called AFTER
               `reproduce` returns, for the reason `blind_reviewer` reads the generator's
               rationale last: persuasion cannot move a number that already exists

THE VERDICT, the cell-level reviewer's shape on purpose (two organs answering "did it come back"
with two thresholds is the drift this desk keeps paying for). NOT_REPRODUCED when the second
disagrees in DIRECTION or its t is below 0.5x the first's (`T_RATIO`, and it is
`blind_reviewer.T_RATIO`'s half); UNMEASURED with no rule text, no family this tree answers to, no
bars, fewer trades than the screen's own floor, or NO FIRST READING to compare against (L1.28a);
REPRODUCED otherwise. A STRONGER SECOND READING IS A REPRODUCTION -- the band is a floor with no
ceiling, because a claim measured better is not a claim that failed (GROWTH GOVERNANCE Rule 1).

WHAT A VERDICT BUYS. NOT_REPRODUCED blocks the discovery with reason `replication_failed` and
marks its cells judged with failure_class `unstable` -- unconfirmed, not refuted. REPRODUCED earns
expensive resources: `expected_info_gain = 1.0` on every queued cell, the candidate score
recomputed so the term actually reorders the queue, and a `research_memory` row of kind
`replication`. It sizes nothing, trades nothing and reaches no order path.

    python desks/mt5/research/lead_replication.py [--dry-run] [--max-leads 10] [--budget-s 240]

numpy at module scope; pandas only inside the reproduction, and its absence is UNMEASURED by name.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
FROZEN_DIR = DESK / "data" / "replication"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
DAILY_OS = DESK / "reports" / "DAILY_RESEARCH_OS.json"
OUT = DESK / "reports" / "LEAD_REPLICATION.json"

REPRODUCED, NOT_REPRODUCED, UNMEASURED = "REPRODUCED", "NOT_REPRODUCED", "UNMEASURED"

MAX_LEADS = 10
BUDGET_S = 240.0
TOP_DECILE = 0.90
#: A decile over a handful of rows is not a decile: below this the axis is UNMEASURED and says so
#: rather than promoting whatever happened to sort first (L1.28a).
MIN_SCORED = 10
#: Half, and it is `blind_reviewer.T_RATIO`'s half: one desk, one "the number came back".
T_RATIO = 0.5
#: Frame floor, so an empty chart reads as absent rather than as a thin result. The screen keeps
#: its own trade floor (`proposer_common.MIN_TRADES`).
MIN_BARS = 200
INFO_GAIN_REPRODUCED = 1.0

#: Exactly what a frozen copy holds. `freeze` BUILDS this dict rather than filtering a registry
#: row into it -- a whitelist that is constructed, not a blacklist that is trusted.
FROZEN_FIELDS: tuple[str, ...] = ("discovery_id", "frozen_at", "claim", "mechanism",
                                  "instruments", "exact_rule")

#: Keys that may never appear in a frozen copy at any depth: the IMPLEMENTATION (the second must
#: re-derive it), the EVIDENCE (the comparison must not be primed) and the PERSUASION (minimal
#: context is the point). The check is on KEYS; the rule TEXT is scrubbed by `scrub_rule`.
FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "family", "families", "params", "parameters", "params_json", "param_grid", "defaults",
    "selector", "shadow_spec", "spec", "code", "expr", "recipe", "implementation", "signal",
    "signals", "side", "timeframe", "chart",
    "t", "t_stat", "tstat", "t_gross", "t_deflated", "t_deflated_sweep", "t_deflated_lifetime",
    "sharpe", "annual_sharpe", "oos_sharpe", "expectancy", "mean_r", "net_per_trade",
    "gross_per_trade", "pf", "profit_factor", "n", "n_trades", "n_independent", "n_obs",
    "p_value", "p_perm", "p_adverse", "baseline", "dsr", "pbo", "reality_p", "lift", "effect",
    "ci", "evidence", "metrics", "score", "fitness",
    "payload", "payload_json", "rationale", "economic_rationale", "why", "generator", "actor",
    "source_id", "novelty", "confidence", "first", "reproduced",
})

#: Evidence clauses redacted out of a PROSE rule. Tight on purpose: `ttl_bars=12` is the rule and
#: must survive, `t = 4.8` is the first pass's reading and must not.
_EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bt[-_ ]?stats?\s*[=:]\s*[+-]?\d+(?:\.\d+)?", re.I),
    re.compile(r"\bt\s*[=:]\s*[+-]?\d+(?:\.\d+)?", re.I),
    re.compile(r"\bp[-_ ]?(?:value|perm)?\s*[=:]\s*[\d.eE+-]+", re.I),
    re.compile(r"\bsharpe\s*[=:]\s*[+-]?\d+(?:\.\d+)?", re.I),
)
_REDACTED = "<evidence redacted>"

#: THE ONLY SOURCE OF PARAMETERS the second implementation may use. A parameter the rule did not
#: declare is the first implementation's choice, and inheriting it makes this a re-run.
_DECLARED_NUMBER = re.compile(r"\b([a-z][a-z0-9_]{1,31})\s*[=:]\s*([+-]?\d+(?:\.\d+)?)", re.I)
_TIMEFRAME = re.compile(r"\b(M1|M5|M15|M30|H1|H4|D1|W1)\b")
_SHORT_WORDS = ("short", "sell", "fade", "downside", "bearish", "mean revert", "reversion")

#: Loaders this module REFUSES, named so the refusal is a fact about the code rather than a
#: promise in prose. Both are the first pass's door into the parquet.
FIRST_PASS_DOORS: tuple[str, ...] = ("research.proposer_common.bars",
                                     "research.blind_reviewer.load_bars",
                                     "libs.research.research_api.data_query")
#: Every parquet THIS module opened itself, in order: the independence claim, auditable.
BARS_READ: list[str] = []

RULE = ("an important lead is frozen and reproduced by a second implementation with minimal "
        "context before it earns expensive resources")


# ------------------------------------------------------------------------------- small tools

def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _num(x: Any) -> float | None:
    """A finite number, or None. A STRING IS NEVER PARSED: prose has no route into a comparison
    of numbers -- `blind_reviewer._num`'s refusal, for its reason."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    f = float(x)
    return f if math.isfinite(f) else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only file is WinError 5 on
    this box, so the fallback is a plain write rather than a lost artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")


def _loads(text: Any) -> Any:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _as_list(text: Any) -> list[str]:
    doc = _loads(text)
    if isinstance(doc, list):
        return [str(x) for x in doc if x]
    return [str(text)] if isinstance(text, str) and text.strip() else []


def _fmt(x: Any, places: int = 2) -> str:
    v = _num(x)
    return "-" if v is None else f"{v:.{places}f}"


# ------------------------------------------------------------------------------- 1. selection

def certified_cells(survivors: Path | None = None) -> set[str]:
    """Every certified cell key the survivors registry holds, and the bare cell id too -- the
    registry keys them `<hunt>.<cell>` and candidates carry the cell id alone."""
    doc = _read_json(survivors or SURVIVORS)
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    out: set[str] = set()
    for key, row in (rows or {}).items():
        out.add(str(key))
        if isinstance(row, dict) and row.get("cell"):
            out.add(str(row["cell"]))
    return out


def named_by_daily_os(daily_os: Path | None = None) -> set[str]:
    """Discovery ids the daily research OS named last pass. Read as TEXT on purpose: the
    controller names leads in several blocks, and a reader that knows only today's block shape
    would silently stop seeing them tomorrow."""
    try:
        blob = Path(daily_os or DAILY_OS).read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"\bdisc_[0-9a-f]{8,}\b", blob))


def all_scores(*, conn: Any = None) -> list[float]:
    """Every scored candidate's score, one column of the whole table -- the population the decile
    is a decile OF."""
    c = conn or R.connect()
    try:
        rows = c.execute("SELECT score FROM research_candidates WHERE score IS NOT NULL").fetchall()
    finally:
        if conn is None:
            c.close()
    return [v for v in (_num(r[0]) for r in rows) if v is not None]


def _discovery(discovery_id: str, *, conn: Any = None) -> dict[str, Any] | None:
    c = conn or R.connect()
    try:
        row = c.execute("SELECT * FROM discoveries WHERE discovery_id=?",
                        (discovery_id,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        if conn is None:
            c.close()


def important_leads(*, conn: Any = None, survivors: Path | None = None,
                    daily_os: Path | None = None, limit: int = MAX_LEADS
                    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The leads the desk is about to treat as important, each carrying WHY it qualified.
    Three axes, any one sufficient, every one a decision the desk already took elsewhere -- this
    organ adds no taste of its own. Returns (leads, diagnostics)."""
    page = max(int(limit) * 50, 500)
    # TWO PAGES, AND THE SECOND ONE IS NOT OPTIONAL. `candidates` orders by score, so the top page
    # answers the decile axis and cannot answer the certified one: a cell that survived the
    # gauntlet need not be near the top of the SEARCH score, and reading one page would have made
    # "certified" mean "certified and also highly scored".
    cands = R.candidates(limit=page, conn=conn)
    seen = {str(c.get("id")) for c in cands}
    cands += [c for c in R.candidates(status="survived", limit=page, conn=conn)
              if str(c.get("id")) not in seen]
    by_disc: dict[str, list[dict[str, Any]]] = {}
    for c in cands:
        did = str(c.get("discovery_id") or "")
        if did:
            by_disc.setdefault(did, []).append(dict(c))

    # THE QUANTILE IS TAKEN OVER THE WHOLE POPULATION, not over the page above: a decile of the
    # best 500 rows is not a decile, and every lead would clear it.
    scores = all_scores(conn=conn)
    decile = (float(np.quantile(np.asarray(scores, dtype=float), TOP_DECILE))
              if len(scores) >= MIN_SCORED else None)
    certified = certified_cells(survivors)
    named = named_by_daily_os(daily_os)

    reasons: dict[str, list[str]] = {}
    for did, rows in by_disc.items():
        best = max((_num(r.get("score")) or 0.0) for r in rows)
        if decile is not None and best >= decile:
            reasons.setdefault(did, []).append(
                f"top decile: best candidate score {best:.6g} >= the registry's {TOP_DECILE:.0%} "
                f"quantile {decile:.6g} over {len(scores)} scored candidate(s)")
        hit = [r for r in rows
               if str(r.get("id")) in certified or str(r.get("donated_cell") or "") in certified
               or int(_num(r.get("survived")) or 0) == 1
               or str(r.get("status") or "") == "survived"]
        if hit:
            reasons.setdefault(did, []).append(
                f"certified: {len(hit)} of its cell(s) hold a certificate or a survived verdict")
    for did in named:
        reasons.setdefault(did, []).append("the daily research OS named this lead in its last pass")

    leads: list[dict[str, Any]] = []
    for did, why in reasons.items():
        disc = _discovery(did, conn=conn)
        if disc is not None:
            leads.append({"discovery": disc, "candidates": by_disc.get(did, []), "why": why})
    leads.sort(key=lambda e: (-len(e["why"]), str(e["discovery"]["discovery_id"])))
    diag = {
        "scored_candidates": len(scores), "top_decile": decile,
        "top_decile_basis": (f"{TOP_DECILE:.0%} quantile over {len(scores)} scored candidate(s)"
                             if decile is not None else
                             f"UNMEASURED: {len(scores)} scored candidate(s) is under the "
                             f"{MIN_SCORED}-row floor, and a decile over a handful is not one"),
        "certified_cells": len(certified), "named_by_daily_os": len(named),
        "discoveries_with_candidates": len(by_disc),
    }
    return leads[:max(int(limit), 0)], diag


# ---------------------------------------------------------------------------------- 2. freeze

def scrub_rule(text: Any) -> str:
    """The rule with the first pass's EVIDENCE removed and its recipe intact: a JSON rule
    (this registry's common shape) loses every forbidden key, a prose rule keeps every word but
    the evidence clauses. `rr=2.0` is the rule, `t = 4.8` is the reading."""
    doc = _loads(text)
    if isinstance(doc, dict):
        kept = {k: v for k, v in doc.items() if str(k).lower() not in FORBIDDEN_FIELDS}
        return json.dumps(kept, sort_keys=True) if kept else ""
    out = str(text or "")
    for pat in _EVIDENCE_PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out.strip()


def freeze(disc: Mapping[str, Any]) -> dict[str, Any]:
    """The frozen copy: six fields, built rather than filtered. There is no seventh field and no
    code path that adds one."""
    return {
        "discovery_id": str(disc.get("discovery_id") or ""),
        "frozen_at": _now(),
        "claim": str(disc.get("economic_rationale") or disc.get("mechanism") or "").strip(),
        "mechanism": str(disc.get("mechanism_id") or disc.get("mechanism") or "").strip(),
        "instruments": _as_list(disc.get("assets_json")),
        "exact_rule": scrub_rule(disc.get("exact_rule")),
    }


def forbidden_in(doc: Any, path: str = "") -> list[str]:
    """Every forbidden key in a frozen copy, at any depth, as a dotted path. Empty is the
    contract; anything else means the freeze leaked and the lead is NOT handed over."""
    found: list[str] = []
    if isinstance(doc, dict):
        for key, value in doc.items():
            here = f"{path}.{key}" if path else str(key)
            if str(key).lower() in FORBIDDEN_FIELDS:
                found.append(here)
            found.extend(forbidden_in(value, here))
    elif isinstance(doc, list):
        for i, value in enumerate(doc):
            found.extend(forbidden_in(value, f"{path}[{i}]"))
    return found


def write_frozen(frozen: Mapping[str, Any], directory: Path | None = None) -> Path:
    path = Path(directory or FROZEN_DIR) / f"{frozen['discovery_id']}.json"
    _write_atomic(path, dict(frozen))
    return path


# -------------------------------------------------------------- 3. the second implementation

def _orthogonal() -> Iterable[str]:
    from mt5desk import families_orthogonal as fo
    return fo.ORTHOGONAL_FAMILIES


def _hunt16() -> Iterable[str]:
    from mt5desk.executables import hunt16_families
    return hunt16_families()


def family_names() -> dict[str, dict[str, Any]]:
    """Every family this tree implements, with its DECLARED defaults -- all three populations
    `executables.resolve_family` answers for, not just the decorated registry. A family missing
    here cannot be re-derived from a rule text, which is a named UNMEASURED and never a silently
    different family."""
    out: dict[str, dict[str, Any]] = {}
    try:
        from mt5desk.families import FAMILY_REGISTRY
        for name, row in FAMILY_REGISTRY.items():
            out[str(name)] = dict((row or {}).get("defaults") or {})
    except Exception:                                  # pragma: no cover - import environment
        pass
    for loader in (_orthogonal, _hunt16):
        try:
            for name in loader():
                out.setdefault(str(name), {})
        except Exception:                              # pragma: no cover - import environment
            continue
    return out


def resolve_family(name: str) -> Any:
    """The ONE constructor for a family name -- `executables.resolve_family`, never a second
    resolution order. Independence is about the DATA and the DERIVATION; a second way of finding
    the same function would be drift, not independence."""
    try:
        from mt5desk.executables import resolve_family as resolve
        return resolve(str(name))
    except Exception:                                  # pragma: no cover - import environment
        return None


def family_from_rule(text: str, known: Mapping[str, Any] | None = None) -> tuple[str, str]:
    """(family, why) re-derived FROM THE RULE TEXT; ("", why) when it names none. A verbatim
    name wins; otherwise a name whose every token appears in the text does, ties alphabetical so
    the answer is deterministic. A zero score REFUSES: the nearest family is a different claim."""
    table = dict(known if known is not None else family_names())
    low = f" {str(text or '').lower()} "
    for name in sorted(table):
        if re.search(rf"\b{re.escape(name.lower())}\b", low):
            return name, f"the rule names {name!r} verbatim"
    best, score = "", 0
    for name in sorted(table):
        tokens = [t for t in str(name).lower().split("_") if len(t) > 2]
        hits = sum(1 for t in tokens if re.search(rf"\b{re.escape(t)}", low))
        if tokens and hits == len(tokens) and hits > score:
            best, score = name, hits
    if best:
        return best, f"every token of {best!r} appears in the rule text ({score} token(s))"
    return "", ("the rule text names no family this tree implements; a nearest-match guess would "
                "replicate a different claim")


def accepted_keys(family: str, declared: Mapping[str, Any] | None) -> set[str] | None:
    """Parameter names this family will take: its DECLARED defaults when the registry has them,
    else its own signature. None means "anything" (a `**kwargs` family forwards what it is given).

    A number under a name the constructor does not take would raise TypeError at the call site
    and read downstream as a failed reproduction, when it is really a mismatched keyword.
    """
    if declared:
        return {str(k).lower() for k in declared}
    fn = resolve_family(family)
    if fn is None:
        return set()
    try:
        import inspect
        sig = inspect.signature(fn)
    except (TypeError, ValueError):                    # pragma: no cover - exotic callables
        return set()
    if any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values()):
        return None
    return {str(p).lower() for p in sig.parameters}


def declared_params(text: str, allowed: set[str] | None) -> dict[str, float]:
    """The numbers THE RULE declares, restricted to names the family takes.

    Both shapes this registry records: a JSON rule contributes its own numeric members, a prose
    rule its `key = value` clauses. A key the family takes but the rule does not name is left to
    the family's own default -- never copied from the first implementation.
    """
    found: dict[str, Any] = {}
    doc = _loads(text)
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found[str(key).lower()] = float(value)
            elif isinstance(value, str):
                found.update({k.lower(): v for k, v in _DECLARED_NUMBER.findall(value)})
    else:
        found.update({k.lower(): v for k, v in _DECLARED_NUMBER.findall(str(text or ""))})
    out: dict[str, float] = {}
    for low, value in found.items():
        if low in ("timeframe", "session", "side") or (allowed is not None and low not in allowed):
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        out[low] = int(num) if num.is_integer() and abs(num) < 1e9 else num
    return out


def _session_of(text: str) -> str | None:
    try:
        from mt5desk.family_call import SESSIONS
        names: tuple[str, ...] = tuple(SESSIONS)
    except Exception:                                  # pragma: no cover - import environment
        names = ("asia", "london", "ny", "all")
    low = str(text or "").lower()
    return next((n for n in names if re.search(rf"\b{re.escape(n)}\b", low)), None)


def reimplement(frozen: Mapping[str, Any], *, universe: Path | None = None,
                known: Mapping[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
    """A runnable spec derived FROM THE FROZEN COPY AND NOTHING ELSE. The frozen copy being
    the only argument is what makes the independence structural rather than promised: there is no
    parameter through which the first implementation could reach this function."""
    rule = str(frozen.get("exact_rule") or "")
    if not rule.strip():
        return None, "the lead records no exact rule; there is nothing to re-implement"
    text = " ".join(x for x in (rule, str(frozen.get("mechanism") or ""),
                                str(frozen.get("claim") or "")) if x)
    table = dict(known if known is not None else family_names())
    family, why = family_from_rule(text, table)
    if not family:
        return None, why
    hit = _TIMEFRAME.search(text.upper())
    timeframe = hit.group(1) if hit is not None else "H1"
    uni = Path(universe or UNIVERSE)
    instruments = [str(s) for s in (frozen.get("instruments") or []) if str(s).strip()]
    symbol = next((s for s in instruments if (uni / f"{s}_{timeframe}.parquet").exists()), "")
    if not symbol:
        return None, (f"none of the declared instrument(s) {instruments or '[]'} has a "
                      f"{timeframe} chart under {uni}")
    low = text.lower()
    # ONLY THE RULE DECLARES PARAMETERS. The claim is persuasion and the mechanism is a label;
    # a number scraped out of either would be a parameter nobody wrote down as part of the rule.
    return {"symbol": symbol, "family": family, "timeframe": timeframe,
            "session": _session_of(text),
            "side": -1 if any(w in low for w in _SHORT_WORDS) else 1,
            "params": declared_params(rule, accepted_keys(family, table.get(family))),
            "derivation": why}, "ok"


def independent_bars(symbol: str, timeframe: str, universe: Path | None = None) -> Any:
    """`<SYM>_<TF>.parquet`, opened by THIS module and normalised by THIS module.

    THE SECOND READER IS THE POINT. `proposer_common.bars` and `blind_reviewer.load_bars` are the
    first pass's doors, both `pd.read_parquet` through the desk's shared `_h1`. This one goes to
    pyarrow directly with its own two rules (tz-aware UTC index, sorted, no resample), so a defect
    in the shared normaliser SHOWS UP instead of being faithfully reproduced twice."""
    path = Path(universe or UNIVERSE) / f"{symbol}_{str(timeframe).upper()}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd
    except Exception:                                  # pragma: no cover - import environment
        return None
    try:
        import pyarrow.parquet as pq
        frame = pq.read_table(path).to_pandas()
    except Exception:
        try:
            frame = pd.read_parquet(path)
        except Exception:
            return None
    BARS_READ.append(str(path))
    try:
        if "time" in frame.columns:
            frame = frame.set_index("time")
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~frame.index.isna()].sort_index()
    except Exception:
        return None
    return None if len(frame) == 0 or "close" not in frame.columns else frame


def _cost_of(symbol: str, frame: Any) -> tuple[float, str]:
    """Round trip as a fraction of price, through the desk's own model. A symbol the universe
    registry does not price is replayed at ZERO cost and SAYS SO -- a hidden zero biases this
    organ toward agreement, the one direction a replicator must never lean."""
    try:
        from research import proposer_common as pc
        cost = pc.cost_frac(symbol, pc.universe_meta(), frame["close"])
    except Exception:                                  # pragma: no cover - import environment
        cost = None
    if cost is None:
        return 0.0, "cost UNMEASURED: the universe registry does not price this symbol"
    return float(cost), "universe_registry"


def reproduce(spec: Mapping[str, Any], *, universe: Path | None = None) -> dict[str, Any]:
    """Run the re-derived rule: n, direction, t and the basis of all three. The screen is the
    desk's own `proposer_common.screen` on purpose -- an independent LOAD and an independent
    DERIVATION disagree about the CLAIM, a second statistic disagrees about arithmetic."""
    out: dict[str, Any] = {"n": None, "t": None, "direction": None, "why": "", "basis": ""}
    frame = independent_bars(str(spec.get("symbol") or ""), str(spec.get("timeframe") or "H1"),
                             universe)
    if frame is None or len(frame) < MIN_BARS:
        out["why"] = (f"{spec.get('symbol')}_{spec.get('timeframe')} bars are absent or shorter "
                      f"than {MIN_BARS} rows")
        return out
    fn = resolve_family(str(spec.get("family") or ""))
    if fn is None:
        out["why"] = f"no constructor for family {spec.get('family')!r} on this tree"
        return out
    try:
        from mt5desk.family_call import signals as family_signals

        from research import proposer_common as pc
    except Exception as exc:                           # pragma: no cover - import environment
        out["why"] = f"the reproduction cannot run here ({type(exc).__name__}: {exc})"
        return out
    params = dict(spec.get("params") or {})
    if spec.get("session"):
        params["session"] = spec["session"]
    try:
        sigs = list(family_signals(fn, frame, side=int(spec.get("side") or 1), params=params))
    except Exception as exc:
        out["why"] = f"the re-implemented rule raised ({type(exc).__name__}: {exc})"
        return out
    cost, cost_basis = _cost_of(str(spec.get("symbol") or ""), frame)
    try:
        got = pc.screen(frame, sigs, cost, pc.artifact_hours(frame))
    except Exception as exc:
        out["why"] = f"the screen raised ({type(exc).__name__}: {exc})"
        return out
    out["basis"] = f"proposer_common.screen/{cost_basis}/independent_bars"
    if got is None:
        out["why"] = (f"the reproduction produced fewer than {pc.MIN_TRADES} independent trade(s)"
                      f" from {len(sigs)} signal(s); a mean over fewer is an anecdote")
        return out
    net = _num(got.get("net_per_trade"))
    out.update({"n": int(got.get("n_independent") or 0), "t": _num(got.get("t_gross")),
                "direction": None if not net else (1 if net > 0 else -1),
                "net_per_trade": net, "gross_per_trade": _num(got.get("gross_per_trade")),
                "cost_frac": _num(got.get("cost_frac")), "n_bars": len(frame),
                "refused_unfillable": int(got.get("refused_unfillable") or 0)})
    return out


# --------------------------------------------------------------------------- 4. the comparison

_T_KEYS = ("t", "t_stat", "tstat", "t_gross", "t_deflated_sweep", "t_deflated_lifetime",
           "t_deflated", "t_value")
_DIRECTION_KEYS = ("net_per_trade", "gross_per_trade", "expectancy", "mean_r", "exp_r",
                   "exp_r_net", "edge", "lift", "effect_size")


def _deep_num(node: Any, names: Sequence[str], depth: int = 4) -> float | None:
    if depth < 0:
        return None
    if isinstance(node, dict):
        for name in names:
            v = _num(node.get(name))
            if v is not None:
                return v
        for value in node.values():
            v = _deep_num(value, names, depth - 1)
            if v is not None:
                return v
    elif isinstance(node, list):
        for value in node[:64]:
            v = _deep_num(value, names, depth - 1)
            if v is not None:
                return v
    return None


def _certificate_reading(cands: Sequence[Mapping[str, Any]], survivors: Path | None
                         ) -> tuple[float, int | None, str] | None:
    doc = _read_json(survivors or SURVIVORS)
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return None
    ids = {str(c.get("id")) for c in cands} | {str(c.get("donated_cell") or "") for c in cands}
    try:
        from research.blind_reviewer import certified_stats
    except Exception:                                  # pragma: no cover - import environment
        return None
    for key, row in rows.items():
        if key not in ids and str((row or {}).get("cell") or key) not in ids:
            continue
        stats = certified_stats(row)
        t, exp = _num(stats.get("t")), _num(stats.get("expectancy"))
        if t is not None:
            return t, (None if not exp else (1 if exp > 0 else -1)), \
                f"certificate {key} via blind_reviewer.certified_stats"
    return None


def first_reading(disc: Mapping[str, Any], cands: Sequence[Mapping[str, Any]] = (),
                  *, survivors: Path | None = None) -> dict[str, Any]:
    """The FIRST implementation's t and direction -- numbers only, READ LAST. Two places: the
    discovery's payload and rule, then its certified cell through
    `blind_reviewer.certified_stats` (numbers-only by construction).

    `annual_sharpe` IS DELIBERATELY NOT A FALLBACK: a sharpe and a screen t are different
    statistics on different scales, and comparing them would fire NOT_REPRODUCED -- which BLOCKS
    a discovery -- about the scale rather than the claim. No recorded t is UNMEASURED (L1.28a)."""
    payload, rule = _loads(disc.get("payload_json")), _loads(disc.get("exact_rule"))
    t = _deep_num(payload, _T_KEYS)
    if t is None:
        t = _deep_num(rule, _T_KEYS)
    d = _deep_num(payload, _DIRECTION_KEYS)
    if d is None:
        d = _deep_num(rule, _DIRECTION_KEYS)
    basis = "discovery payload/rule numbers"
    if t is None:
        cert = _certificate_reading(cands, survivors)
        if cert is not None:
            t, cert_d, basis = cert
            d = cert_d if d is None else d
    direction = None if not d else (1 if d > 0 else -1)
    if direction is None and t is not None:
        direction = 1 if t > 0 else -1
        basis += "; direction implied from the sign of the first t"
    return {"t": t, "direction": direction, "basis": basis if t is not None else UNMEASURED}


def judge(first: Mapping[str, Any], second: Mapping[str, Any]) -> tuple[str, list[str]]:
    """REPRODUCED / NOT_REPRODUCED / UNMEASURED, from numbers only. Pure, so the rule is testable
    without bars, a registry or a family."""
    n, t2, d2 = second.get("n"), _num(second.get("t")), second.get("direction")
    if not isinstance(n, int) or n <= 0 or t2 is None or d2 is None:
        return UNMEASURED, [str(second.get("why") or "the second implementation read nothing")]
    t1, d1 = _num(first.get("t")), first.get("direction")
    if t1 is None or d1 is None:
        return UNMEASURED, [
            "the first pass recorded no t and no direction on this lead, so there is nothing to "
            "reproduce WITHIN; the second reading is published beside it rather than compared "
            f"(second t={t2:+.2f} on {n} trade(s))"]
    why: list[str] = []
    if int(d1) != int(d2):
        why.append(f"DIRECTION disagrees: the lead reads {int(d1):+d} ({first.get('basis')}), "
                   f"the second implementation {int(d2):+d} on {n} trade(s)")
    if (t1 > 0) != (t2 > 0) or abs(t2) < T_RATIO * abs(t1):
        why.append(f"t={t2:+.2f} is below {T_RATIO:g}x the lead's t={t1:+.2f} "
                   f"({first.get('basis')})")
    if why:
        return NOT_REPRODUCED, why
    return REPRODUCED, [f"the claim comes back: direction {int(d2):+d}, t={t2:+.2f} against the "
                        f"lead's {t1:+.2f} on {n} independent trade(s) [{second.get('basis')}]"]


# ---------------------------------------------------------------------------------- the pass

def replicate_lead(entry: Mapping[str, Any], *, universe: Path | None = None,
                   survivors: Path | None = None, frozen_dir: Path | None = None,
                   dry_run: bool = False, known: Mapping[str, Any] | None = None
                   ) -> dict[str, Any]:
    """One lead, frozen and redone. THE ORDER IN THIS FUNCTION IS THE BLINDNESS: freeze,
    re-derive, reproduce, and only then read what the first pass said. Hoisting `first_reading`
    above `reproduce` would compile and would quietly make this a confirmation device."""
    t0 = time.monotonic()
    disc = dict(entry["discovery"])
    cands = list(entry.get("candidates") or [])
    frozen = freeze(disc)
    row: dict[str, Any] = {
        "discovery_id": str(disc.get("discovery_id") or ""), "verdict": UNMEASURED, "why": [],
        "first": {}, "second": {}, "why_important": list(entry.get("why") or []),
        "frozen_path": None, "mechanism": frozen["mechanism"],
        "instruments": frozen["instruments"]}

    def done(**kw: Any) -> dict[str, Any]:
        row.update(kw)
        row["seconds"] = round(time.monotonic() - t0, 2)
        return row

    leaked = forbidden_in(frozen)
    if leaked:                                         # pragma: no cover - the whitelist forbids
        return done(why=[f"the frozen copy leaked implementation context ({', '.join(leaked)}); "
                         "the lead is NOT handed to a second implementation"])
    if not dry_run:
        row["frozen_path"] = str(write_frozen(frozen, frozen_dir))
    spec, why = reimplement(frozen, universe=universe, known=known)
    if spec is None:
        return done(why=[why])
    row["reimplementation"] = {k: spec[k] for k in ("symbol", "family", "timeframe", "session",
                                                    "side", "params", "derivation")}
    second = reproduce(spec, universe=universe)
    # READ LAST, ON PURPOSE. Everything above this line ran without it.
    first = first_reading(disc, cands, survivors=survivors)
    verdict, reasons = judge(first, second)
    return done(verdict=verdict, why=reasons,
                first={"t": first.get("t"), "direction": first.get("direction"),
                       "basis": first.get("basis")},
                second={"t": second.get("t"), "direction": second.get("direction"),
                        "n": second.get("n"), "basis": second.get("basis"),
                        "why": second.get("why")})


def apply_verdict(row: Mapping[str, Any], cands: Sequence[Mapping[str, Any]], *,
                  conn: Any = None) -> dict[str, Any]:
    """What the verdict BUYS in the registry, which is the whole of this organ's authority.

    REPRODUCED recomputes the candidate score with the raised information-gain term so it actually
    reorders `claim_candidates`' queue rather than writing a column nobody reads (III.16). The
    recomputation can only RAISE the score: a successful replication that lowered a claim's
    priority -- because some other organ had written a higher number by a route this one cannot
    see -- would be a restriction bought with a positive result (GROWTH GOVERNANCE Rule 1).
    """
    did = str(row.get("discovery_id") or "")
    out: dict[str, Any] = {"blocked": False, "promoted": 0, "judged": 0, "memory_id": None}
    if row.get("verdict") == NOT_REPRODUCED:
        R.set_discovery_state(did, "BLOCKED", reason="replication_failed", conn=conn)
        out["blocked"] = True
        for cand in cands:
            if R.mark_candidate(str(cand.get("id")), "judged", conn=conn,
                                failure_class="unstable", judged_at=_now(),
                                rejection_reason="replication_failed"):
                out["judged"] += 1
    elif row.get("verdict") == REPRODUCED:
        for cand in cands:
            if str(cand.get("status") or "") != "queued":
                continue
            fields = {**dict(cand), "expected_info_gain": INFO_GAIN_REPRODUCED}
            score = max(R.score_candidate(fields, bool(_num(cand.get("empty_axis_bonus")))),
                        _num(cand.get("score")) or 0.0)
            if R.mark_candidate(str(cand.get("id")), "queued", conn=conn,
                                expected_info_gain=INFO_GAIN_REPRODUCED, score=score):
                out["promoted"] += 1
        out["memory_id"] = R.remember(
            "replication",
            f"lead {did} was frozen and reproduced by a second implementation: "
            f"{'; '.join(row.get('why') or [])}",
            kind="replication", memory_key=f"replication:{did}", result=REPRODUCED,
            payload={"first": row.get("first"), "second": row.get("second"),
                     "reimplementation": row.get("reimplementation"),
                     "why_important": row.get("why_important")},
            evidence={"rule": RULE, "at": _now()}, conn=conn)
    return out


def build(*, max_leads: int = MAX_LEADS, budget_s: float = BUDGET_S, dry_run: bool = False,
          universe: Path | None = None, survivors: Path | None = None,
          daily_os: Path | None = None, frozen_dir: Path | None = None,
          conn: Any = None) -> dict[str, Any]:
    """Select, freeze, redo, compare and -- unless dry -- record. Returns the artifact."""
    t0 = time.monotonic()
    c = conn or R.connect()
    try:
        leads, diag = important_leads(conn=c, survivors=survivors, daily_os=daily_os,
                                      limit=max(int(max_leads), 0))
        verdicts: list[dict[str, Any]] = []
        blocked: list[str] = []
        promoted: list[str] = []
        unmeasured: list[dict[str, str]] = []
        frozen_n = 0
        for entry in leads:
            if budget_s - (time.monotonic() - t0) <= 0:
                unmeasured.append({"what": str(entry["discovery"]["discovery_id"]),
                                   "why": f"budget: {budget_s:g}s spent before this lead"})
                continue
            row = replicate_lead(entry, universe=universe, survivors=survivors,
                                 frozen_dir=frozen_dir, dry_run=dry_run)
            frozen_n += int(bool(row.get("frozen_path")))
            verdicts.append(row)
            if row["verdict"] == UNMEASURED:
                unmeasured.append({"what": row["discovery_id"],
                                   "why": "; ".join(row.get("why") or []) or "no reading"})
            if dry_run:
                continue
            effects = apply_verdict(row, entry.get("candidates") or [], conn=c)
            if effects["blocked"]:
                blocked.append(row["discovery_id"])
            if effects["promoted"] or effects["memory_id"]:
                promoted.append(row["discovery_id"])
        if diag.get("top_decile") is None:
            unmeasured.append({"what": "top_decile", "why": str(diag["top_decile_basis"])})
        if not leads:
            unmeasured.append({"what": "important_leads", "why": (
                "no discovery qualified on any of the three axes (top-decile candidate score, a "
                "certified cell, named by the daily research OS); an empty selection is a "
                "measurement, not an idle organ")})
        return {
            "at": _now(), "n_important": len(leads), "frozen": frozen_n, "verdicts": verdicts,
            "blocked": blocked, "promoted": promoted, "unmeasured": unmeasured,
            "counts": {"reproduced": sum(1 for r in verdicts if r["verdict"] == REPRODUCED),
                       "not_reproduced": sum(1 for r in verdicts
                                             if r["verdict"] == NOT_REPRODUCED),
                       "unmeasured": sum(1 for r in verdicts if r["verdict"] == UNMEASURED)},
            "selection": diag,
            "independence": {
                "bars_read_by_this_module": list(BARS_READ[-50:]),
                "loaders_refused": list(FIRST_PASS_DOORS),
                "frozen_fields": list(FROZEN_FIELDS),
                "why": ("the second implementation is handed the frozen copy and nothing else: "
                        "its bars come from this module's own reader, its family and parameters "
                        "are re-derived from the rule text, and the first pass's numbers are read "
                        "only after its own reading exists")},
            "seconds": round(time.monotonic() - t0, 2), "dry_run": bool(dry_run), "rule": RULE,
        }
    finally:
        if conn is None:
            c.close()


def render(doc: Mapping[str, Any]) -> list[str]:
    counts, sel = doc.get("counts") or {}, doc.get("selection") or {}
    lines = [f"LEAD REPLICATION  {doc['n_important']} important lead(s), {doc['frozen']} frozen -- "
             f"{counts.get('reproduced', 0)} REPRODUCED, "
             f"{counts.get('not_reproduced', 0)} NOT_REPRODUCED, "
             f"{counts.get('unmeasured', 0)} UNMEASURED  [{doc['rule']}]",
             f"  selection: {sel.get('top_decile_basis')}; {sel.get('certified_cells')} certified "
             f"cell(s); {sel.get('named_by_daily_os')} named by the daily OS"]
    for row in (doc.get("verdicts") or [])[:12]:
        first, second = row.get("first") or {}, row.get("second") or {}
        lines.append(f"  {row['verdict']:<15} {str(row['discovery_id'])[:40]:<40} "
                     f"first t={_fmt(first.get('t'))} dir={first.get('direction')} | "
                     f"second t={_fmt(second.get('t'))} dir={second.get('direction')} "
                     f"n={second.get('n')}")
        for line in (row.get("why") or [])[:2]:
            lines.append(f"      - {line}")
    if doc.get("blocked"):
        lines.append(f"  BLOCKED replication_failed: {', '.join(doc['blocked'][:6])}")
    if doc.get("promoted"):
        lines.append(f"  earned expensive resources: {', '.join(doc['promoted'][:6])}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="freeze an important lead and hand it to a second implementation")
    ap.add_argument("--max-leads", type=int, default=MAX_LEADS,
                    help=f"leads per run (default {MAX_LEADS})")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S,
                    help=f"seconds for the whole run (default {BUDGET_S:g})")
    ap.add_argument("--dry-run", action="store_true",
                    help="select, freeze in memory, reproduce and print; write no frozen copy, "
                         "no artifact, and leave the registry untouched")
    a = ap.parse_args(argv)
    doc = build(max_leads=a.max_leads, budget_s=a.budget_s, dry_run=a.dry_run)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: no frozen copy, no artifact, no registry effect")
        return 0
    _write_atomic(OUT, doc)
    print(f"  -> {OUT}")
    print(f"  -> {FROZEN_DIR} ({doc['frozen']} frozen cop(y/ies) this run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
