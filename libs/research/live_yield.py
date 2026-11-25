"""THE LIVE-EDGE YIELD -- expected promoted, fill-proven live edges per CPU-hour, for any arm.

THE METRIC (principal, 2026-11-25). An arm (a producer, a miner, a regional/source bandit arm, a
research department) is worth the edges it gets PROMOTED AND TRADING LIVE: non-exotic, passed
forward shadow, fill-proven, LIVE in data/sleeves.json. Live counts are near zero desk-wide, so
a raw count ranks nobody; the score is the EXPECTED live edges

    certs x p(cert -> forward-kept) x p(forward-kept -> live and fill-proven)

where each stage rate is the arm's OWN conversion at >= MIN_STAGE_N, else the empirical-Bayes
shrink (k + a * pooled) / (n + a) toward the desk-pooled rate (a = prior strength). The pooled
rates carry a +1/+2 (uniform-prior) smoothing so a desk with no live edge yet still ranks arms
by their certificates and forward keep-rate instead of scoring every one 0. An arm with REALISED
live edges is scored max(realised, expected): realised dominates once it exists.

ONE READER PER INPUT, resolved here so every caller reads them the same way:

    desks/mt5/data/certificate_provenance.json   certificate cell -> producer, birth time
    desks/mt5/reports/shadow/shadow_state.json   forward clocks (ACTIVE / PROMOTION CANDIDATE
                                                 kept; KILL / IDENTITY_BROKEN killed)
    desks/mt5/data/sleeves.json                  LIVE rows (the promoter's output)
    desks/mt5/data/fill_corpus.jsonl             fill proof (a row naming the sleeve with filled_at)
    desks/mt5/reports/PRODUCER_CONVERSION.json   candidates / judged / certificates per producer

    desks/mt5/data/decay_live.json               the decay detector: half-life, fading verdicts
    desks/mt5/data/live_ledger.jsonl             closed live trades, through
                                                 research.decay_monitor.sleeve_trades

THREE STAGES hand over (`blend_stages`): certs x the desk's odds, then expected live edges, then
REALISED live log-growth sum(w * log(1 + net_r * fraction)) per CPU-hour, each taking over at its
own minimum sample (STAGE_MIN) and blending by n / (n + k) before it. Live trades are weighted by
recency with the arm's measured edge half-life (decay detector), else DEFAULT_HALF_LIFE_D; a live
edge the detector marks decaying earns no persistence credit and is a failure signal for its arm
(it never removes the edge: retirement stays with the promoter).

An input that cannot be read is UNMEASURED (None here), never zero. Stdlib only; the exotic test
is `research.universe_policy.is_exotic_symbol` when importable, else the caller's callable.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[2] / "desks" / "mt5"
PROVENANCE = DESK / "data" / "certificate_provenance.json"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
SLEEVES = DESK / "data" / "sleeves.json"
FILLS = DESK / "data" / "fill_corpus.jsonl"
CONVERSION = DESK / "reports" / "PRODUCER_CONVERSION.json"
INPUTS = (PROVENANCE, SHADOW, SLEEVES, FILLS, CONVERSION)

UNMEASURED = "UNMEASURED"
MIN_STAGE_N = 10
PRIOR_STRENGTH = 10.0
KEPT_CLOCK = frozenset({"ACTIVE", "PROMOTION CANDIDATE"})
KILLED_CLOCK = frozenset({"KILL", "IDENTITY_BROKEN"})

Key = tuple[str, str]


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _exotic(symbol: str) -> bool:
    try:
        from research.universe_policy import is_exotic_symbol
        return bool(is_exotic_symbol(symbol))
    except Exception:
        return False


def symbol_of(cell: str) -> str:
    head = cell.rsplit(".", 2)[0] if cell.count(".") >= 2 else cell
    return head.split("@", 1)[0]


def family_of(cell: str) -> str:
    parts = cell.rsplit(".", 2)
    return parts[1] if len(parts) == 3 else ""


# ------------------------------------------------------------------------------------ readers

def read_certificates(doc: Any = None, path: Path | None = None) -> list[dict[str, Any]] | None:
    """Every certificate birth record ({cell, producer, at, ...}); None when unreadable."""
    doc = doc if doc is not None else _read(path or PROVENANCE)
    if not isinstance(doc, dict):
        return None
    recs = doc.get("records") or {}
    items = recs.values() if isinstance(recs, dict) else recs
    return [r for r in items if isinstance(r, dict) and r.get("cell")]


def read_forward(doc: Any = None, path: Path | None = None) -> dict[Key, str] | None:
    """(symbol, family) -> KEPT / KILLED from the forward clocks; None when unreadable."""
    doc = doc if doc is not None else _read(path or SHADOW)
    if not isinstance(doc, dict):
        return None
    out: dict[Key, str] = {}
    for key, v in doc.items():
        if not isinstance(v, dict) or "status" not in v or key.count(".") < 2:
            continue
        sym, fam = key.split(".", 2)[:2]
        st = str(v.get("status") or "")
        k = (sym.split("@", 1)[0], fam)
        if st in KEPT_CLOCK:
            out[k] = "KEPT"
        elif st in KILLED_CLOCK:
            out.setdefault(k, "KILLED")
    return out


def read_live(sleeves: Any = None, fills: Iterable[Mapping[str, Any]] | None = None, *,
              sleeves_path: Path | None = None, fills_path: Path | None = None,
              is_exotic: Callable[[str], bool] | None = None) -> set[Key] | None:
    """(symbol, family) of every LIVE, non-exotic, FILL-PROVEN sleeve; None when either input
    cannot be read."""
    rows = read_live_sleeves(sleeves, fills, sleeves_path=sleeves_path, fills_path=fills_path,
                             is_exotic=is_exotic)
    return None if rows is None else {(r["symbol"], r["family"]) for r in rows.values()}


def read_live_sleeves(sleeves: Any = None, fills: Iterable[Mapping[str, Any]] | None = None, *,
                      sleeves_path: Path | None = None, fills_path: Path | None = None,
                      is_exotic: Callable[[str], bool] | None = None
                      ) -> dict[str, dict[str, Any]] | None:
    """{sleeve name: {symbol, family, risk_frac}} for every LIVE, non-exotic, FILL-PROVEN sleeve;
    None when either input cannot be read."""
    doc = sleeves if sleeves is not None else _read(sleeves_path or SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return None
    if fills is None:
        try:
            fills = [json.loads(ln) for ln in (fills_path or FILLS).read_text("utf-8")
                     .splitlines() if ln.strip()]
        except (OSError, ValueError):
            return None
    ex = is_exotic or _exotic
    filled = {str(f.get("sleeve") or f.get("strategy_id") or "") for f in fills
              if isinstance(f, Mapping) and f.get("filled_at")}
    return {str(r["name"]): {"symbol": str(r.get("symbol") or ""),
                             "family": str(r.get("family") or ""),
                             "timeframe": str(r.get("timeframe") or ""),
                             "session": str(r.get("session") or ""),
                             "risk_frac": (float(r["risk_frac"])
                                           if isinstance(r.get("risk_frac"), int | float)
                                           else None)}
            for r in rows
            if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"
            and str(r.get("name") or "") in filled and not ex(str(r.get("symbol") or ""))}


#: The decay detector's published verdicts (research/decay_monitor -> data/decay_live.json).
DECAY = DESK / "data" / "decay_live.json"
#: The half-life used when the decay detector has none measured for an arm's edges.
DEFAULT_HALF_LIFE_D = 90.0
DECAYING_VERDICTS = frozenset({"FADE", "RETIRE", "DEMOTE"})


def read_decay(doc: Any = None, path: Path | None = None) -> dict[str, dict[str, Any]] | None:
    """{sleeve: {half_life_days, decaying}} from the decay detector; None when unreadable. An
    edge is DECAYING when the detector's verdict fades/retires it or its fitted model is decaying
    (decay_monitor.fit_half_life only fits a half-life to a decaying expectancy)."""
    doc = doc if doc is not None else _read(path or DECAY)
    v = doc.get("verdicts") if isinstance(doc, dict) else None
    if not isinstance(v, dict):
        return None
    out: dict[str, dict[str, Any]] = {}
    for name, r in v.items():
        if not isinstance(r, dict):
            continue
        hl = r.get("half_life_days")
        out[str(name)] = {"half_life_days": float(hl) if isinstance(hl, int | float) and hl > 0
                          else None,
                          "decaying": (str(r.get("verdict") or "").upper() in DECAYING_VERDICTS
                                       or (isinstance(hl, int | float) and hl > 0))}
    return out


def half_life(sleeves: Iterable[str], decay: Mapping[str, Mapping[str, Any]] | None
              ) -> tuple[float, str]:
    """(half-life days, "measured" | "default") for an arm: the median measured half-life of its
    live sleeves, else DEFAULT_HALF_LIFE_D."""
    hs = sorted(float(decay[s]["half_life_days"]) for s in sleeves
                if decay and isinstance((decay.get(s) or {}).get("half_life_days"), float))
    if hs:
        return hs[len(hs) // 2], "measured"
    return DEFAULT_HALF_LIFE_D, "default"


def realised_elog(sleeves: Mapping[str, Mapping[str, Any]], *, half_life_d: float,
                  now: Any = None,
                  trades_of: Callable[[str], list[dict[str, Any]]] | None = None
                  ) -> dict[str, Any]:
    """sum over the arm's live, fill-proven trades of w * log(1 + net_r * fraction), w the
    recency weight 0.5 ** (age / half-life). Trades come from the decay detector's own reader
    (research.decay_monitor.sleeve_trades: unreconstructible R skipped, never zero); net_r is the
    trade's R net of its commission and swap over the risk it put up; fraction the sleeve's
    allocator risk_frac. UNMEASURED when the reader or a fraction is missing."""
    import math
    from datetime import UTC, datetime
    if trades_of is None:
        try:
            from research.decay_monitor import sleeve_trades as trades_of
        except Exception as exc:
            return {"elog": UNMEASURED, "n_trades": 0,
                    "why": f"trade reader unavailable ({type(exc).__name__})"}
    now = now or datetime.now(UTC)
    total, n, wsum = 0.0, 0, 0.0
    for name, sl in sleeves.items():
        f = sl.get("risk_frac")
        if not isinstance(f, int | float):
            return {"elog": UNMEASURED, "n_trades": 0, "why": f"{name}: no allocator fraction"}
        for t in trades_of(name):
            r = t.get("r_multiple")
            if not isinstance(r, int | float):
                continue
            rq = t.get("risk_quote")
            cost = sum(float(t.get(k) or 0.0) for k in ("commission", "swap")
                       if isinstance(t.get(k), int | float))
            net = float(r) + (cost / abs(rq) if isinstance(rq, int | float) and rq else 0.0)
            try:
                ts = datetime.fromisoformat(str(t.get("time")).replace("Z", "+00:00"))
                ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
                age = max(0.0, (now - ts).total_seconds() / 86400)
            except ValueError:
                age = 0.0
            w = 0.5 ** (age / half_life_d) if half_life_d > 0 else 1.0
            total += w * math.log(max(1e-12, 1.0 + net * float(f)))
            wsum += w
            n += 1
    return {"elog": round(total, 10), "n_trades": n, "recency_weight_sum": round(wsum, 4)}


#: THE STAGED HAND-OVER: each later stage takes over once its own sample reaches its minimum,
#: and blends by n / (n + k) before that (k = the minimum).
STAGE_MIN = {"expected_live": MIN_STAGE_N, "realised_elog": 30}


def stage_weight(n: int, stage: str) -> float:
    m = STAGE_MIN[stage]
    return 1.0 if n >= m else n / (n + m)


def blend_stages(arms: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """{arm: {relative, alphas}} from per-arm {certs_odds, expected_live, realised_elog}
    (per CPU-hour, None when unmeasured) and samples {n_forward, n_live_trades}. Each stage is put
    on one scale by dividing by its median positive value across arms; stage 1 (certs x the desk's
    odds) is the base, stage 2 (expected live edges, own shrunk odds) blends in by the forward
    sample, stage 3 (realised live log-growth) by the live-trade sample. Two-sided: a negative
    realised log-growth pulls the relative score down (callers clip it at their floor)."""
    def med(key: str) -> float | None:
        pos = sorted(float(a[key]) for a in arms.values()
                     if isinstance(a.get(key), int | float) and a[key] > 0)
        return pos[len(pos) // 2] if pos else None

    meds = {k: med(k) for k in ("certs_odds", "expected_live", "realised_elog")}

    def rel(a: Mapping[str, Any], key: str) -> float | None:
        v = a.get(key)
        if not isinstance(v, int | float):
            return None
        m = meds[key]
        return v / m if m else (0.0 if v <= 0 else 1.0)

    out: dict[str, dict[str, Any]] = {}
    for arm, a in arms.items():
        r1, r2, r3 = rel(a, "certs_odds"), rel(a, "expected_live"), rel(a, "realised_elog")
        a2 = stage_weight(int(a.get("n_forward") or 0), "expected_live") if r2 is not None \
            else 0.0
        a3 = stage_weight(int(a.get("n_live_trades") or 0), "realised_elog") \
            if r3 is not None else 0.0
        base = r1 if r1 is not None else r2
        if base is None and r3 is None:
            out[arm] = {"relative": None, "alphas": {"expected_live": a2, "realised_elog": a3}}
            continue
        s12 = (1 - a2) * (base or 0.0) + a2 * (r2 if r2 is not None else base or 0.0)
        out[arm] = {"relative": (1 - a3) * s12 + a3 * (r3 or 0.0),
                    "alphas": {"expected_live": round(a2, 4), "realised_elog": round(a3, 4)}}
    return out


# ------------------------------------------------------------------------------------ the score

def shrink(k: int, n: int, pooled: float | None,
           prior_strength: float = PRIOR_STRENGTH) -> float | None:
    """Own rate at n >= MIN_STAGE_N, else (k + a * pooled) / (n + a); None when unmeasurable."""
    if n >= MIN_STAGE_N or pooled is None:
        return (k / n) if n else pooled
    return (k + prior_strength * pooled) / (n + prior_strength)


def stage_counts(arm_of: Callable[[Mapping[str, Any]], str | None], *,
                 certificates: list[dict[str, Any]] | str | None = UNMEASURED,
                 forward: dict[Key, str] | str | None = UNMEASURED,
                 live: set[Key] | str | None = UNMEASURED,
                 conversion: Iterable[Mapping[str, Any]] | None = None,
                 cpu_s: Mapping[str, float] | None = None,
                 is_exotic: Callable[[str], bool] | None = None) -> dict[str, dict[str, Any]]:
    """{arm: {candidates, judged, certs, forward_kept, forward_killed, live_fill_proven, cpu_s}}.

    `arm_of` maps a certificate record (and a conversion row) to its arm, or None to skip it.
    Inputs left at their default are read from the desk's files; pass None to say unreadable.
    A count whose input is unreadable is None (UNMEASURED)."""
    certs = read_certificates() if certificates == UNMEASURED else certificates
    fwd = read_forward() if forward == UNMEASURED else forward
    lv = read_live(is_exotic=is_exotic) if live == UNMEASURED else live
    ex = is_exotic or _exotic
    out: dict[str, dict[str, Any]] = {}

    def row(arm: str) -> dict[str, Any]:
        return out.setdefault(arm, {
            "candidates": None, "judged": None, "certs": 0 if certs is not None else None,
            "forward_kept": 0 if fwd is not None and certs is not None else None,
            "forward_killed": 0 if fwd is not None and certs is not None else None,
            "live_fill_proven": (0 if lv is not None and fwd is not None and certs is not None
                                 else None),
            "cpu_s": (cpu_s or {}).get(arm)})

    for r in conversion or []:
        arm = arm_of(r)
        if arm:
            x = row(arm)
            for k in ("candidates", "judged"):
                v = r.get(k)
                if isinstance(v, int) and not isinstance(v, bool):
                    x[k] = (x[k] or 0) + v
    for rec in certs or []:
        arm = arm_of(rec)
        if not arm:
            continue
        x = row(arm)
        cell = str(rec["cell"])
        sym, fam = symbol_of(cell), family_of(cell)
        x["certs"] += 1
        st = fwd.get((sym, fam)) if fwd is not None else None
        if fwd is not None:
            x["forward_kept"] += st == "KEPT"
            x["forward_killed"] += st == "KILLED"
        if lv is not None and fwd is not None and st == "KEPT" and (sym, fam) in lv \
                and not ex(sym):
            x["live_fill_proven"] += 1
    for arm in cpu_s or {}:
        row(arm)
    return out


def pooled(counts: Mapping[str, Mapping[str, Any]]) -> dict[str, float | None]:
    """The desk's smoothed stage priors: (kept+1)/(kept+killed+2), (live+1)/(kept+2)."""
    def tot(k: str) -> int | None:
        vals = [c.get(k) for c in counts.values()]
        return None if not vals or any(v is None for v in vals) else sum(vals)  # type: ignore
    kept, killed, live = tot("forward_kept"), tot("forward_killed"), tot("live_fill_proven")
    return {"p_cert_to_kept": (kept + 1) / (kept + killed + 2)
            if kept is not None and killed is not None else None,
            "p_kept_to_live": (live + 1) / (kept + 2)
            if live is not None and kept is not None else None}


def independence_credit(edges: Iterable[tuple[str, str, str]],
                        book: Iterable[tuple[str, str, str]]) -> dict[str, Any]:
    """The arm's MARGINAL contribution to the live book's number of independent bets:
    k_eff(book + edges) - k_eff(book), k_eff the desk's trial-ledger census (participation ratio
    of descriptor similarity) over (symbol, family, class). A near-duplicate of a book edge earns
    about 0. Returns are not read here, so the basis is the distinctness PROXY, and says so; when
    the census cannot be imported, distinct (symbol, family) pairs absent from the book."""
    mine = sorted(set(edges))
    base = sorted(set(book) - set(mine))
    if not mine:
        return {"credit": 0.0, "basis": "PROXY"}
    try:
        from libs.research import trial_ledger as tl

        def keff(xs: list[tuple[str, str, str]]) -> float:
            if not xs:
                return 0.0
            return float(tl.census([tl.Trial(f"{s}.{f}", f or "?", {"symbol": s, "class": k}, {})
                                    for s, f, k in xs]).n_effective)
        return {"credit": round(max(0.0, keff(base + mine) - keff(base)), 6),
                "basis": "PROXY: trial_ledger.census over (symbol, family, class)"}
    except Exception:
        have = {(s, f) for s, f, _ in base}
        return {"credit": float(sum(1 for s, f, _ in mine if (s, f) not in have)),
                "basis": "PROXY: distinct (symbol, family) not already in the book"}


def expected_one(certs_eff: float | None, kept: int | None, killed: int | None,
                 live: int | None, prior: Mapping[str, float | None],
                 prior_strength: float = PRIOR_STRENGTH,
                 live_credit: float | None = None) -> dict[str, Any]:
    """One arm's score from its counts; `certs_eff` may be raw certificates or k_eff edges, and
    `live_credit` the realised live edges' independence credit (default: the count)."""
    unm: list[str] = []
    p1 = (shrink(int(kept), int(kept) + int(killed), prior.get("p_cert_to_kept"),
                 prior_strength) if kept is not None and killed is not None else None)
    p2 = (shrink(int(live), int(kept), prior.get("p_kept_to_live"), prior_strength)
          if live is not None and kept is not None else None)
    for name, v in (("certificates", certs_eff), ("forward_clocks", p1),
                    ("live_fill_proof", p2)):
        if v is None:
            unm.append(name)
    real = float(live_credit if live_credit is not None else (live or 0))
    exp = (max(real, float(certs_eff) * p1 * p2)  # type: ignore[operator]
           if not unm else None)
    return {"realised_live": live if live is not None else UNMEASURED,
            "expected_live": round(exp, 8) if exp is not None else UNMEASURED,
            "stage_rates": {"p_cert_to_kept": round(p1, 8) if p1 is not None else UNMEASURED,
                            "p_kept_to_live": round(p2, 8) if p2 is not None else UNMEASURED},
            "unmeasured": unm}


def expected_live_edges(counts: Mapping[str, Mapping[str, Any]],
                        prior: Mapping[str, float | None] | None = None,
                        prior_strength: float = PRIOR_STRENGTH,
                        certs_effective: Mapping[str, float] | None = None
                        ) -> dict[str, dict[str, Any]]:
    """{arm: {realised_live, expected_live, per_cpu_hour, stage_rates, unmeasured}}."""
    pr = prior if prior is not None else pooled(counts)
    out: dict[str, dict[str, Any]] = {}
    for arm, c in counts.items():
        ce = (certs_effective or {}).get(arm, c.get("certs"))
        x = expected_one(ce, c.get("forward_kept"), c.get("forward_killed"),
                         c.get("live_fill_proven"), pr, prior_strength)
        cpu = c.get("cpu_s")
        if isinstance(cpu, int | float) and cpu > 0 and isinstance(x["expected_live"], float):
            x["per_cpu_hour"] = round(x["expected_live"] / (cpu / 3600.0), 8)
        else:
            x["per_cpu_hour"] = UNMEASURED
            if not (isinstance(cpu, int | float) and cpu > 0):
                x["unmeasured"].append("cpu")
        out[arm] = x
    return out
