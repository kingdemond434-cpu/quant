"""THE OCCUPANCY MAP: where in strategy space the desk has looked, what it found there, and which
empty ground sits right next to what already pays.

WHAT ALREADY EXISTED, AND WHY IT WAS NOT THIS (surveyed 2026-09-30 before a line was written):

    research/axis_registry.py      ten axes, ONE state per cell (the strongest any source claims)
                                   and 2-axis occupancy PAIRS. It cannot say how many hypotheses
                                   a cell took, how many were judged, or what the best forward
                                   clock there earned -- a state is not a count.
    research/qd_frontier.py        one ELITE per eight-axis behavioural niche; its explorer takes
                                   empty niches one axis from an occupied one. It keeps the best
                                   cell, never the funnel, and its niche key has no chart and no
                                   family (it speaks mechanisms).
    research/docket_keff.py        per (family, symbol) marginal k_eff against the LIVE book --
                                   blind to the certified set and to chart/session/horizon.
    research/orthogonality.py      tail dependence BETWEEN live sleeves. Candidates never appear.
    research/orthogonality_yield   per PRODUCER leave-one-out effective rank; not per cell.
    research/alpha_breadth.py      breadth of the book, not of the search.
    libs/tiers/qd_axes.py          correlation-cluster and capacity DESCRIPTORS for the archive.
    research_diversity_archive     QD archive of experiments by information source/mechanism.

So every organ above answers "is this new?" or "is the book diverse?", and none answers the
question the principal asked: on the grid FAMILY x ASSET CLASS x TIMEFRAME x SESSION x HORIZON,
how many hypotheses were TRIED, JUDGED, CERTIFIED, FORWARD-ENROLLED and LIVE per cell, what is
the best FORWARD expectancy there, how long since anyone tried it -- and which cells with no
certificate and few trials sit next to cells that already pay. That is this file.

THE THREE THINGS IT PUBLISHES (reports/OCCUPANCY_MAP.json, hourly leg `occupancy_map`):

  1. `cells`: the funnel per occupied cell, with best forward exp_r (n >= MIN_FORWARD_N only;
     an exp_r on two trades is noise wearing a number) and hours since the cell was last tried.
  2. `targets`: EMPTY and UNDER-TRIED cells (no certificate, no LIVE sleeve, fewer than
     UNDER_TRIED_MAX hypotheses) that are ONE AXIS from a SUCCESSFUL cell (certified, LIVE, or a
     positive forward clock), ranked by summed adjacency success / (1 + tried). Only hypothesis-
     lane asset classes and registered, unbanned families are named -- the two-lane order.
  3. `orthogonality`: per docket (family, symbol) key, the candidate's EXPECTED CORRELATION to
     the LIVE book and to the CERTIFIED set. The instrument term reuses the desk's own daily
     panel (`docket_keff.daily_returns`, the same series marginal k_eff is computed on); the
     signal-overlap term is a DECLARED prior on how much two rules on correlated instruments
     share (same family 1.0, same `axis_registry` mechanism 0.5, otherwise 0.25), because the
     repo holds no per-candidate return series to measure it on before the candidate is judged.
     score = 1 - mean(corr_live, corr_certified). A side with no measurable member is UNMEASURED
     and the score falls to par on it -- never to 0 and never to 1 (L1.28a).

THE TWO CONSUMERS, both REORDER-OR-ADD ONLY (standing order: never reduce research generation or
raw cell mining):

  * `research/judge_coverage.py` calls `stamp()` on the docket: `_occ` (a target cell's
    normalised priority x OCC_WEIGHT) and `_orth` (ORTH_WEIGHT x (score - par)) are added to the
    marginal-k_eff term inside each family stream of `coverage_order`. Rows move; none leaves.
    Each docket row also carries its published `orthogonality` score.
  * This leg donates hypothesis rows for the best EMPTY targets into
    `data/intelligence/occupancy_map/` -- the compiler's intake -- so ground with no row at all
    gets generation, not merely priority. It adds rows; it removes none.

    python desks/mt5/research/occupancy_map.py [--once] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(ROOT), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from research import axis_registry as ar
except Exception:                                     # pragma: no cover - run as a script
    import axis_registry as ar  # type: ignore[no-redef,import-not-found]

HYP = BASE / "data" / "hypotheses"
DOCKET = HYP / "external_survivors.json"
STUDY_BANK = HYP / "study_bank.json"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SHADOW_STATE = BASE / "reports" / "shadow" / "shadow_state.json"
SLEEVES = BASE / "data" / "sleeves.json"
REPORT = BASE / "reports" / "OCCUPANCY_MAP.json"
INTAKE = BASE / "data" / "intelligence" / "occupancy_map"

UNKNOWN = "UNKNOWN"
AXES = ("family", "asset_class", "timeframe", "session", "horizon")

#: A cell with fewer distinct hypotheses than this and no certificate is UNDER-TRIED. Five is the
#: point below which "nothing certified here" is not evidence about the ground -- a handful of
#: parameterisations of one rule is one look, not a search.
UNDER_TRIED_MAX = 5
#: Forward clocks with fewer trades than this do not set a cell's best forward expectancy.
MIN_FORWARD_N = 5
#: Cells published in `targets`; the docket stamp reads only these.
MAX_TARGETS = 500
MAX_CELLS_PUBLISHED = 20000
MAX_ORTH_KEYS = 20000
#: Proposals donated per hour, the same structural ceiling axis_registry and qd_frontier use so
#: no one organ floods the compiler.
MAX_PROPOSALS = 60
PROPOSAL_SYMBOLS = 3
#: The map the docket stamp reads must be this fresh; older reads as UNMEASURED (par for all).
MAX_AGE_H = 6.0

#: Signal-overlap prior (declared, not fitted -- see module docstring).
SAME_FAMILY_OVERLAP = 1.0
SAME_MECHANISM_OVERLAP = 0.5
OTHER_OVERLAP = 0.25
#: Shared daily observations below which an instrument correlation is UNMEASURED.
MIN_OVERLAP_DAYS = 60

#: Units: effective bets, the same as docket_keff's priority, which these are added to. A first
#: row in empty ground adjacent to proven ground is worth about one independent bet, the same
#: reading docket_keff gives a first sleeve in an empty cluster.
OCC_WEIGHT = 1.0
ORTH_WEIGHT = 1.0

#: Hold lengths tried when deriving which horizons a chart can reach (bars).
_HOLD_PROBE = (1, 2, 3, 4, 6, 8, 12, 16, 24, 48, 96, 200, 400)

RULE = ("cells are FAMILY x ASSET_CLASS x TIMEFRAME x SESSION x HORIZON (axis_registry "
        "derivations); a TARGET has no certificate, no LIVE sleeve and fewer than "
        f"{UNDER_TRIED_MAX} hypotheses and sits one axis from a successful cell; priority = "
        "sum(adjacent success) / (1 + tried). REORDER OR ADD ONLY: the docket stamp moves rows, "
        "the intake donation adds rows, nothing is removed")


# ------------------------------------------------------------------------------ reading
def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


# ------------------------------------------------------------------------------ the grid
@lru_cache(maxsize=4096)
def _asset_class(symbol: str) -> str:
    return ar.asset_class_of(symbol) if symbol else UNKNOWN


def cell_axes(symbol: Any, family: Any, params: Mapping[str, Any] | None = None,
              timeframe: Any = None, session: Any = None) -> dict[str, str]:
    """The five-axis coordinate. Every axis resolves to a token; UNKNOWN is counted, not guessed."""
    p = dict(params) if isinstance(params, Mapping) else {}
    chart = ar.normalise_chart(timeframe if timeframe is not None else p.get("timeframe"))
    sess = ar.normalise_session(session if session is not None else p.get("session"))
    if chart == "D1":
        sess = "all"                   # daily bars carry no session
    return {"family": ar._tok(family) or UNKNOWN,
            "asset_class": _asset_class(str(symbol or "").strip().upper()),
            "timeframe": chart, "session": sess, "horizon": ar.horizon_of(chart, p)}


def row_axes(row: Mapping[str, Any]) -> dict[str, str]:
    """A docket row's coordinate: params first, then the row's own fields."""
    raw = row.get("params")
    params: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    tf = params.get("timeframe") or row.get("timeframe")
    sess = params.get("session") or row.get("session") or row.get("selector")
    sym = row.get("symbol") or row.get("sym")
    if not sym and isinstance(row.get("symbols"), list) and row["symbols"]:
        sym = row["symbols"][0]
    return cell_axes(sym, row.get("family"), params, tf, sess)


def cell_key(axes: Mapping[str, str]) -> str:
    return "|".join(str(axes.get(a, UNKNOWN)) for a in AXES)


def _frontier_id(row: Mapping[str, Any]) -> str:
    """The gauntlet's own identity for a docket row (the ledger's `cell`), imported, never
    re-implemented; a JSON spelling when the identity module cannot load."""
    try:
        from research.frontier_identity import cell_id
        return str(cell_id({"sym": row.get("symbol") or row.get("sym"),
                            "family": row.get("family"),
                            "params": row.get("params") or {},
                            "timeframe": row.get("timeframe")}))
    except Exception:
        return json.dumps([row.get("symbol"), row.get("family"), row.get("params"),
                           row.get("timeframe")], sort_keys=True, default=str)


def _blank(axes: Mapping[str, str]) -> dict[str, Any]:
    return {**axes, "tried": 0, "judged": 0, "certified": 0, "forward_enrolled": 0, "live": 0,
            "best_forward_exp_r": None, "best_forward_n": None, "last_tried_at": None,
            "_tried": set(), "_judged": set(), "_passed": set(), "_canon": 0}


def _touch(cell: dict[str, Any], at: datetime | None) -> None:
    if at is None:
        return
    prev = cell["last_tried_at"]
    if prev is None or at > prev:
        cell["last_tried_at"] = at


def _forward(cell: dict[str, Any], exp_r: float | None, n: float | None) -> None:
    if exp_r is None or n is None or n < MIN_FORWARD_N:
        return
    best = cell["best_forward_exp_r"]
    if best is None or exp_r > best:
        cell["best_forward_exp_r"], cell["best_forward_n"] = exp_r, int(n)


def collect(*, docket: list[dict[str, Any]] | None = None,
            ledger: list[dict[str, Any]] | None = None, canon: Any = None,
            shadow: Any = None, sleeves: Any = None,
            note: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """{cell key: funnel counts} from the docket, the gate ledger, the canon, the forward clocks
    and the sleeves. Every argument left None is read from its artifact."""
    note = note if note is not None else {}
    cells: dict[str, dict[str, Any]] = {}

    def cell(axes: Mapping[str, str]) -> dict[str, Any]:
        k = cell_key(axes)
        c = cells.get(k)
        if c is None:
            c = cells[k] = _blank(axes)
        return c

    if docket is None:
        docket = []
        for path in (DOCKET, STUDY_BANK):
            doc = _read(path)
            note[path.name] = "READ" if isinstance(doc, list) else "ABSENT"
            docket.extend(r for r in (doc or []) if isinstance(r, dict))
    id_to_key: dict[str, str] = {}
    for row in docket:
        axes = row_axes(row)
        c = cell(axes)
        fid = _frontier_id(row)
        id_to_key[fid] = cell_key(axes)
        c["_tried"].add(fid)
        _touch(c, _ts(row.get("first_seen")))

    if ledger is None:
        ledger = _read_jsonl(GATE_LEDGER)
        note[GATE_LEDGER.name] = f"{len(ledger)} rows" if ledger else "ABSENT_OR_EMPTY"
    for row in ledger:
        # The same verdict filter judge_coverage.judged_index applies: a NOT_RUN deferral is not
        # a verdict, and a row with neither pass/fail nor terminal gate is not one either.
        if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
            continue
        if row.get("passed") in (None, "None") and not row.get("terminal_gate"):
            continue
        cid = str(row.get("cell") or "")
        if not cid:
            continue
        key = id_to_key.get(cid)
        if key is not None:
            c = cells[key]
        else:
            parsed = ar.parse_shadow_key(cid)
            c = cell(cell_axes(row.get("sym") or parsed["symbol"],
                               row.get("family") or parsed["family"], None, None,
                               parsed["session"]))
        c["_tried"].add(cid)
        c["_judged"].add(cid)
        if row.get("passed") is True:
            c["_passed"].add(cid)
        _touch(c, _ts(row.get("at")))

    canon = _read(CANON) if canon is None else canon
    survivors = canon.get("survivors") if isinstance(canon, dict) else None
    note[CANON.name] = "READ" if isinstance(survivors, dict) else "ABSENT"
    for key, row in (survivors or {}).items():
        if not isinstance(row, dict):
            continue
        raw = row.get("shadow_spec")
        spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
        c = cell(cell_axes(spec.get("symbol") or row.get("sym"),
                           spec.get("family") or row.get("family"), spec.get("params"),
                           spec.get("timeframe"), spec.get("selector")))
        c["_canon"] += 1
        c["_tried"].add(f"canon:{key}")

    shadow = _read(SHADOW_STATE) if shadow is None else shadow
    note[SHADOW_STATE.name] = "READ" if isinstance(shadow, dict) else "ABSENT"
    for key, row in (shadow or {}).items():
        if not isinstance(row, dict):
            continue
        parsed = ar.parse_shadow_key(str(key))
        if not parsed["symbol"]:
            continue
        n = _num(row.get("n"))
        # A REFUSED or BLOCKED clock produced no forward observation (qd_frontier's rule).
        ran = bool(n) or str(row.get("status") or "").upper().startswith(("ACTIVE", "PROMOTION"))
        if not ran:
            continue
        c = cell(cell_axes(parsed["symbol"], parsed["family"],
                           dict.fromkeys(parsed["param_names"], True), None, parsed["session"]))
        c["forward_enrolled"] += 1
        _forward(c, _num(row.get("exp_r")), n)

    sleeves = _read(SLEEVES) if sleeves is None else sleeves
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    note[SLEEVES.name] = "READ" if isinstance(rows, list) else "ABSENT"
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or str(row.get("status") or "").upper() != "LIVE":
            continue
        c = cell(cell_axes(row.get("symbol"), row.get("family"), row, row.get("timeframe"),
                           row.get("session") or row.get("selector") or row.get("window")))
        c["live"] += 1
        _forward(c, _num(row.get("shadow_exp")), _num(row.get("shadow_n")))

    for c in cells.values():
        c["tried"] = len(c["_tried"])
        c["judged"] = len(c["_judged"])
        c["certified"] = max(c["_canon"], len(c["_passed"]))
    return cells


def success(cell: Mapping[str, Any]) -> int:
    """0..3: certified, LIVE, and a positive forward expectancy each count once."""
    fwd = cell.get("best_forward_exp_r")
    return (int(int(cell.get("certified") or 0) > 0) + int(int(cell.get("live") or 0) > 0)
            + int(fwd is not None and float(fwd) > 0))


# ------------------------------------------------------------------------------ adjacency
@lru_cache(maxsize=16)
def reachable_horizons(chart: str) -> tuple[str, ...]:
    """Horizons a chart can actually reach through a hold length, derived via horizon_of."""
    out = {ar.horizon_of(chart, {"max_hold": b}) for b in _HOLD_PROBE}
    out.discard(UNKNOWN)
    return tuple(sorted(out))


def hold_for(chart: str, horizon: str) -> int | None:
    """The shortest hold (bars) that reaches `horizon` on `chart`, or None when the chart's own
    default already is that horizon (no hold parameter needed)."""
    if ar.horizon_of(chart, None) == horizon:
        return None
    for b in _HOLD_PROBE:
        if ar.horizon_of(chart, {"max_hold": b}) == horizon:
            return b
    return None


def neighbours(axes: Mapping[str, str], families: Iterable[str],
               classes: Iterable[str]) -> list[dict[str, str]]:
    """Every coordinate ONE axis away. Family moves stay inside the same mechanism (a family in
    another mechanism is not adjacent ground, it is other ground); a chart move takes the new
    chart's own default horizon; D1 carries no session."""
    base = dict(axes)
    out: list[dict[str, str]] = []
    mech = ar.classify_family(base["family"])[0]
    if mech != UNKNOWN:
        for f in families:
            if f != base["family"] and ar.classify_family(f)[0] == mech:
                out.append({**base, "family": f})
    for k in classes:
        if k != base["asset_class"]:
            out.append({**base, "asset_class": k})
    for chart in ar.CHARTS:
        if chart != base["timeframe"]:
            out.append({**base, "timeframe": chart, "horizon": ar.horizon_of(chart, None),
                        "session": "all" if chart == "D1" else base["session"]})
    if base["timeframe"] != "D1":
        for s in ar.PROPOSABLE_SESSIONS:
            if s != base["session"]:
                out.append({**base, "session": s})
    for h in reachable_horizons(base["timeframe"]):
        if h != base["horizon"]:
            out.append({**base, "horizon": h})
    return out


def _families() -> list[str]:
    try:
        return sorted({ar._tok(f) for f in ar.registered_families()} - {""})
    except Exception:
        return []


def targets(cells: Mapping[str, Mapping[str, Any]], *, families: Iterable[str] | None = None,
            classes: Iterable[str] | None = None,
            banned: Callable[[str], bool] | None = None,
            limit: int = MAX_TARGETS) -> list[dict[str, Any]]:
    """EMPTY and UNDER-TRIED cells one axis from a successful cell, best first."""
    fams = sorted(set(families) if families is not None else set(_families())
                  or {c["family"] for c in cells.values() if c["family"] != UNKNOWN})
    if classes is None:
        try:
            classes = sorted(ar.instruments_by_class())
        except Exception:
            classes = []
    klass = sorted(set(classes)) or sorted({c["asset_class"] for c in cells.values()
                                             if c["asset_class"] != UNKNOWN})
    is_banned = banned or ar._banned
    fam_ok = set(fams)
    class_ok = set(klass)
    adj: dict[str, float] = {}
    via: dict[str, list[str]] = {}
    axes_of: dict[str, dict[str, str]] = {}
    for src_key, src in cells.items():
        s = success(src)
        if not s or any(src.get(a) == UNKNOWN for a in AXES):
            continue
        for nb in neighbours({a: str(src[a]) for a in AXES}, fams, klass):
            if nb["family"] not in fam_ok or nb["asset_class"] not in class_ok:
                continue
            k = cell_key(nb)
            have = cells.get(k)
            if have is not None and (int(have.get("certified") or 0) > 0
                                     or int(have.get("live") or 0) > 0
                                     or int(have.get("tried") or 0) >= UNDER_TRIED_MAX):
                continue
            adj[k] = adj.get(k, 0.0) + s
            axes_of[k] = nb
            lst = via.setdefault(k, [])
            if len(lst) < 3:
                lst.append(src_key)
    banned_cache: dict[str, bool] = {}
    out: list[dict[str, Any]] = []
    for k, a in adj.items():
        fam = axes_of[k]["family"]
        if fam not in banned_cache:
            try:
                banned_cache[fam] = bool(is_banned(fam))
            except Exception:
                banned_cache[fam] = False
        if banned_cache[fam]:
            continue
        have = cells.get(k)
        tried = int(have.get("tried") or 0) if have is not None else 0
        out.append({**axes_of[k], "key": k, "kind": "UNDER_TRIED" if have else "EMPTY",
                    "tried": tried, "adjacency": a, "priority": round(a / (1.0 + tried), 6),
                    "adjacent_to": via[k]})
    out.sort(key=lambda r: (-r["priority"], r["key"]))
    out = out[:max(0, int(limit))]
    top = out[0]["priority"] if out else 0.0
    for r in out:
        r["occupancy_priority"] = round(r["priority"] / top, 6) if top > 0 else 0.0
    return out


# ------------------------------------------------------------------------------ orthogonality
def _overlap(fa: str, fb: str) -> float:
    if fa == fb:
        return SAME_FAMILY_OVERLAP
    ma = ar.classify_family(fa)[0]
    return SAME_MECHANISM_OVERLAP if ma != UNKNOWN and ma == ar.classify_family(fb)[0] \
        else OTHER_OVERLAP


def book_members(sleeves: Any = None, canon: Any = None
                 ) -> tuple[list[tuple[str, str, float]], list[tuple[str, str, float]]]:
    """(LIVE members, CERTIFIED members) as (family token, SYMBOL, weight)."""
    sleeves = _read(SLEEVES) if sleeves is None else sleeves
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else sleeves
    live: list[tuple[str, str, float]] = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE":
            sym = str(r.get("symbol") or "").strip().upper()
            if sym:
                w = _num(r.get("risk_frac"))
                live.append((ar._tok(r.get("family")), sym, w if w and w > 0 else 1.0))
    canon = _read(CANON) if canon is None else canon
    cert: list[tuple[str, str, float]] = []
    survivors = canon.get("survivors") if isinstance(canon, dict) else None
    for r in (survivors or {}).values():
        if not isinstance(r, dict):
            continue
        raw = r.get("shadow_spec")
        spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
        sym = str(spec.get("symbol") or r.get("sym") or "").strip().upper()
        if sym:
            cert.append((ar._tok(spec.get("family") or r.get("family")), sym, 1.0))
    return live, cert


def _corr_frame(symbols: Iterable[str], loader: Callable[[str], Any]) -> Any:
    import pandas as pd
    series = {}
    for s in sorted(set(symbols)):
        r = loader(s)
        if r is not None and len(r):
            series[s] = r
    if not series:
        return None
    return pd.DataFrame(series).corr(min_periods=MIN_OVERLAP_DAYS).abs()


def _expected(fam: str, sym: str, members: list[tuple[str, str, float]], corr: Any
              ) -> tuple[float | None, float | None]:
    """(risk-weighted mean, max) expected correlation to `members`; (None, None) unmeasured.

    A candidate whose own instrument has no series is UNMEASURED on the whole side -- scoring it
    only against members on its own symbol would read "unmeasured" as "the same bet"."""
    if corr is None or sym not in getattr(corr, "index", ()):
        return None, None
    num = den = 0.0
    worst: float | None = None
    for mf, ms, w in members:
        if ms == sym:
            rho = 1.0
        else:
            try:
                rho = float(corr.at[sym, ms])
            except (KeyError, AttributeError, TypeError, ValueError):
                continue
            if not math.isfinite(rho):
                continue
        e = rho * _overlap(fam, mf)
        num += w * e
        den += w
        worst = e if worst is None else max(worst, e)
    return (num / den if den > 0 else None), worst


def orthogonality(candidates: Iterable[tuple[str, str]], *, sleeves: Any = None,
                  canon: Any = None, loader: Callable[[str], Any] | None = None
                  ) -> dict[str, Any]:
    """Per candidate (family, SYMBOL): expected correlation to the LIVE book and the CERTIFIED
    set, and score = 1 - mean(available sides). Keys are docket_keff.cell_key spellings."""
    if loader is None:
        from research.docket_keff import daily_returns
        loader = daily_returns
    live, cert = book_members(sleeves, canon)
    cands = sorted({(str(f), str(s).strip().upper()) for f, s in candidates if s})
    syms = {s for _, s in cands} | {s for _, s, _ in live} | {s for _, s, _ in cert}
    try:
        corr = _corr_frame(syms, loader)
        corr_status = "MEASURED" if corr is not None else "UNMEASURED"
    except Exception as exc:                                         # pragma: no cover
        corr, corr_status = None, f"UNMEASURED: {type(exc).__name__}"
    cells: dict[str, dict[str, Any]] = {}
    for fam, sym in cands:
        ft = ar._tok(fam)
        cl, cl_max = _expected(ft, sym, live, corr)
        cc, cc_max = _expected(ft, sym, cert, corr)
        sides = [v for v in (cl, cc) if v is not None]
        cells[f"{fam}|{sym}"] = {
            "corr_live": None if cl is None else round(cl, 4),
            "corr_live_max": None if cl_max is None else round(cl_max, 4),
            "corr_certified": None if cc is None else round(cc, 4),
            "corr_certified_max": None if cc_max is None else round(cc_max, 4),
            "score": round(1.0 - sum(sides) / len(sides), 4) if sides else None}
    measured = [c["score"] for c in cells.values() if c["score"] is not None]
    par = statistics.median(measured) if measured else None
    return {"status": "MEASURED" if measured else "UNMEASURED", "correlation": corr_status,
            "par": None if par is None else round(par, 4),
            "live_members": len(live), "certified_members": len(cert),
            "candidates": len(cands), "measured": len(measured),
            "rule": ("expected corr to a set = risk-weighted mean over members of |rho(daily "
                     "returns, docket_keff panel)| x signal overlap (same family "
                     f"{SAME_FAMILY_OVERLAP}, same mechanism {SAME_MECHANISM_OVERLAP}, else "
                     f"{OTHER_OVERLAP}); score = 1 - mean(corr_live, corr_certified); a side "
                     "with no measurable member is left out, a candidate with neither sits at "
                     "par"),
            "cells": cells}


# ------------------------------------------------------------------------------ generation
def proposals(tgts: list[dict[str, Any]], *, by_class: Mapping[str, list[str]] | None = None,
              limit: int = MAX_PROPOSALS) -> list[dict[str, Any]]:
    """Intake rows for the best EMPTY targets -- ground with no docket row at all. ADD only."""
    if by_class is None:
        try:
            by_class = ar.instruments_by_class()
        except Exception:
            by_class = {}
    out: list[dict[str, Any]] = []
    for t in tgts:
        if len(out) >= limit:
            break
        if t["kind"] != "EMPTY" or t["session"] not in ar.PROPOSABLE_SESSIONS:
            continue
        symbols = [s for s in by_class.get(t["asset_class"], []) if ar.may_hypothesise(s)]
        symbols = symbols[:PROPOSAL_SYMBOLS]
        if not symbols:
            continue
        params: dict[str, Any] = {}
        if t["timeframe"] != ar.DEFAULT_CHART:
            params["timeframe"] = t["timeframe"]
        if t["session"] != "all":
            params["session"] = t["session"]
        hold = hold_for(t["timeframe"], t["horizon"])
        if hold is not None:
            params["max_hold"] = hold
        out.append({"kind": "hypothesis", "family": t["family"], "symbols": symbols,
                    "params": params, "timeframe": t["timeframe"], "session": t["session"],
                    "source": "occupancy_map", "occupancy_cell": t["key"],
                    "rank_score": t["priority"],
                    "why": (f"EMPTY cell {t['key']} sits one axis from "
                            f"{', '.join(t['adjacent_to'])} (adjacent success "
                            f"{t['adjacency']:g}); nothing has ever been tried there")})
    return out


# ------------------------------------------------------------------------------ the whole map
def _public(c: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    last = c.get("last_tried_at")
    return {**{a: c[a] for a in AXES},
            **{k: c[k] for k in ("tried", "judged", "certified", "forward_enrolled", "live",
                                 "best_forward_n")},
            "best_forward_exp_r": (None if c["best_forward_exp_r"] is None
                                   else round(float(c["best_forward_exp_r"]), 6)),
            "last_tried_at": last.isoformat(timespec="seconds") if last else None,
            "hours_since_tried": (round((now - last).total_seconds() / 3600.0, 2)
                                  if last else None),
            "success": success(c)}


def build(*, now: datetime | None = None, docket: list[dict[str, Any]] | None = None,
          ledger: list[dict[str, Any]] | None = None, canon: Any = None, shadow: Any = None,
          sleeves: Any = None, loader: Callable[[str], Any] | None = None,
          families: Iterable[str] | None = None, classes: Iterable[str] | None = None,
          banned: Callable[[str], bool] | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    note: dict[str, str] = {}
    if docket is None:
        docket = []
        for path in (DOCKET, STUDY_BANK):
            doc = _read(path)
            note[path.name] = "READ" if isinstance(doc, list) else "ABSENT"
            docket.extend(r for r in (doc or []) if isinstance(r, dict))
    canon = _read(CANON) if canon is None else canon
    sleeves = _read(SLEEVES) if sleeves is None else sleeves
    cells = collect(docket=docket, ledger=ledger, canon=canon, shadow=shadow, sleeves=sleeves,
                    note=note)
    tgts = targets(cells, families=families, classes=classes, banned=banned)
    cands = {(str(r.get("family") or ""), str(r.get("symbol") or r.get("sym") or ""))
             for r in docket}
    orth = orthogonality(cands, sleeves=sleeves, canon=canon, loader=loader)
    pub = sorted((_public(c, at) for c in cells.values()),
                 key=lambda r: (-r["success"], -r["tried"], cell_key(r)))
    by_axis = {a: dict(sorted({str(c[a]): 0 for c in cells.values()}.items())) for a in AXES}
    for c in cells.values():
        for a in AXES:
            by_axis[a][str(c[a])] += int(c["tried"])
    return {
        "at": at.isoformat(timespec="seconds"), "rule": RULE, "axes": list(AXES),
        "inputs": note,
        "totals": {"cells_occupied": len(cells),
                   "cells_successful": sum(1 for c in cells.values() if success(c)),
                   "tried": sum(int(c["tried"]) for c in cells.values()),
                   "judged": sum(int(c["judged"]) for c in cells.values()),
                   "certified": sum(int(c["certified"]) for c in cells.values()),
                   "forward_enrolled": sum(int(c["forward_enrolled"]) for c in cells.values()),
                   "live": sum(int(c["live"]) for c in cells.values()),
                   "targets": len(tgts),
                   "targets_empty": sum(1 for t in tgts if t["kind"] == "EMPTY"),
                   "targets_under_tried": sum(1 for t in tgts if t["kind"] == "UNDER_TRIED")},
        "tried_by_axis": by_axis,
        "unknown_cells": {a: sum(1 for c in cells.values() if c[a] == UNKNOWN) for a in AXES},
        "targets": tgts,
        "cells": pub[:MAX_CELLS_PUBLISHED], "cells_total": len(pub),
        "orthogonality": {**{k: v for k, v in orth.items() if k != "cells"},
                          "cells": dict(sorted(orth["cells"].items())[:MAX_ORTH_KEYS])},
        "consumers": {
            "docket_order": ("research/judge_coverage.py occupancy_stamp -> coverage_order: "
                             "_occ + _orth beside _keff inside each family stream"),
            "generation": "data/intelligence/occupancy_map/ (compiler intake), EMPTY targets"},
    }


# ------------------------------------------------------------------------------ the consumer
def load(path: Path | None = None, *, now: datetime | None = None) -> tuple[Any, str]:
    """(map, why): the published map when present and fresh, else (None, why)."""
    doc = _read(path or REPORT)
    if not isinstance(doc, dict):
        return None, "reports/OCCUPANCY_MAP.json is absent or unreadable"
    at = _ts(doc.get("at"))
    age_h = ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0 if at else None
    if age_h is None or age_h > MAX_AGE_H:
        shown = "undated" if age_h is None else f"{round(age_h, 1)}h old"
        return None, f"reports/OCCUPANCY_MAP.json is {shown} (fresh means <= {MAX_AGE_H}h)"
    return doc, f"map {round(age_h, 2)}h old"


def stamp(rows: list[dict[str, Any]], doc: Any = None, *, now: datetime | None = None
          ) -> dict[str, Any]:
    """Stamp `_occ` and `_orth` (ordering terms, effective-bet units) and the published
    `orthogonality` score on every docket row. REMOVES NOTHING; an absent or stale map stamps
    nothing, so every row ranks exactly as before (L1.28a)."""
    why = "map supplied by caller"
    if doc is None:
        doc, why = load(now=now)
    if not isinstance(doc, dict):
        return {"status": "UNMEASURED", "why": why, "rows": len(rows)}
    tmap = {str(t.get("key")): float(t.get("occupancy_priority") or 0.0)
            for t in doc.get("targets") or [] if isinstance(t, dict)}
    raw_o = doc.get("orthogonality")
    orth: dict[str, Any] = raw_o if isinstance(raw_o, dict) else {}
    raw_c = orth.get("cells")
    ocells: dict[str, Any] = raw_c if isinstance(raw_c, dict) else {}
    par = _num(orth.get("par"))
    n_occ = n_orth = 0
    for row in rows:
        k = cell_key(row_axes(row))
        pri = tmap.get(k, 0.0)
        row["_occ"] = round(OCC_WEIGHT * pri, 6)
        n_occ += 1 if pri > 0 else 0
        sym = str(row.get("symbol") or row.get("sym") or "").strip().upper()
        entry = ocells.get(f"{str(row.get('family') or '').strip()}|{sym}") or {}
        score = _num(entry.get("score"))
        row["orthogonality"] = score
        if score is not None and par is not None:
            row["_orth"] = round(ORTH_WEIGHT * (score - par), 6)
            n_orth += 1
        else:
            row["_orth"] = 0.0
    return {"status": "MEASURED", "why": why, "rows": len(rows), "rows_in_targets": n_occ,
            "rows_orthogonality_scored": n_orth, "orthogonality_par": par,
            "targets": len(tmap), "occ_weight": OCC_WEIGHT, "orth_weight": ORTH_WEIGHT,
            "rule": ("_occ = OCC_WEIGHT x normalised target priority; _orth = ORTH_WEIGHT x "
                     "(score - par); both are added to _keff inside each family stream. "
                     "Reorder only; no row removed"),
            "report": "desks/mt5/reports/OCCUPANCY_MAP.json"}


def head_census(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    """Target rows and mean orthogonality term in the first `n` rows -- the order's evidence."""
    head = rows[:max(int(n), 0)]
    orth = [float(r.get("_orth") or 0.0) for r in head]
    return {"rows": len(head),
            "target_rows": sum(1 for r in head if float(r.get("_occ") or 0.0) > 0),
            "orth_term_mean": round(sum(orth) / len(orth), 6) if orth else None}


# ------------------------------------------------------------------------------ writing
def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def write(doc: Mapping[str, Any], props: list[dict[str, Any]], *, report: Path | None = None,
          intake: Path | None = None) -> Path | None:
    _atomic(report or REPORT, doc)
    if not props:
        return None
    target = (intake or INTAKE) / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    _atomic(target, props)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="strategy-space occupancy map + orthogonality")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing")
    ap.add_argument("--max-proposals", type=int, default=MAX_PROPOSALS)
    a = ap.parse_args(argv)
    doc = build()
    props = proposals(doc["targets"], limit=min(int(a.max_proposals), MAX_PROPOSALS))
    doc["proposals"] = {"donated": len(props), "cells": [p["occupancy_cell"] for p in props]}
    t = doc["totals"]
    o = doc["orthogonality"]
    print(f"occupancy map: {t['cells_occupied']} cells ({t['cells_successful']} successful); "
          f"tried {t['tried']} judged {t['judged']} certified {t['certified']} forward "
          f"{t['forward_enrolled']} live {t['live']}")
    print(f"  targets {t['targets']} (empty {t['targets_empty']}, under-tried "
          f"{t['targets_under_tried']}); orthogonality {o['status']} on {o['measured']}/"
          f"{o['candidates']} candidates, par {o['par']}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    donated = write(doc, props)
    print(f"-> {REPORT}" + (f"; {len(props)} proposal(s) -> {donated}" if donated else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
