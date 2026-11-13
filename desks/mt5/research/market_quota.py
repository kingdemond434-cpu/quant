"""The judge's intake, split by MARKET GROUP and by FAMILY, adaptively by measured yield.

THE PRINCIPAL'S RULE (2026-11-13 19:46Z, refined 19:48Z): at least 90% of the judge's trials go
to non-exotic markets; within that the compute follows yield; exotics may EARN up to 10% by the
same yield measure and decay toward zero while they keep producing false edges; and an exotic
edge must survive TWICE its live spread and swap before it may be promoted (that second half is
`blind_reviewer.exotic_cost_bar`; this module is the intake half).

WHAT A "TRIAL" IS HERE. One cell the judge rules on. Trials are what the deflated-Sharpe charge
and the program-level SPA/PBO tests divide one family-wise error budget across, so trials -- not
cells mined, not cells warmed -- are the cost being allocated (`CLAUDE.md`, TWO LANES: "Trial
count is a shared cost").

WHAT "YIELD" IS HERE. Distinct (symbol, family) pairs that PASSED the gauntlet, per ruled trial,
by group. The gauntlet is post-cost, so a pass is an after-cost edge; counting distinct pairs
rather than passing rows is the cheap independence correction -- forty parameter siblings of one
pair that all pass are one edge, not forty. It is shrunk toward the pooled rate with
`PRIOR_TRIALS` pseudo-trials, so a group with no record starts at the house rate: neither
condemned nor privileged before it has evidence.

WHY THE FAMILY FLOOR LIVES HERE TOO (2026-11-13, the Auditor's finding). `JUDGE_COVERAGE.json`
showed 53 of 125 families with `judged_total` 0, among them families holding thousands of queued
cells (conditioning_model 1,311, cross_sectional_class_low_vol 1,684, usd_session_shock 2,833).
The cause is ORDER, not omission: the sealed `allocate_by_yield` keeps every family (`want >= 1`)
but appends its keep FAMILY BY FAMILY in first-appearance order, so a family whose cells sort late
(daily charts, no CEO tag) sits at the tail of the warmer's build list, and the gate-room cut and
the build budget end the round before reaching it, every round. This interleaves the intake so
every PREFIX of it is group-balanced and family-balanced: whatever length the round reaches, every
family with queued cells is in it at no less than its exploration share.

IT IS A PERMUTATION PLUS A HOLD, NEVER A DELETION. Cells beyond the exotic share are held for this
round only and keep their docket place; nothing is dropped, voided or re-scored, and no gate,
FDR or trial charge is touched. The order INSIDE each family is the incoming (sealed) order, so
the sealed sweep's never-judged-first, CEO-family and symbol-rotation preferences survive within
every family.

Published every round to `reports/MARKET_QUOTA.json` (shares, yields, targets, what the intake
held) and summarised by `judging_throughput` into `JUDGING_RATE.json["market_split"]` with the
REALISED split from the gate ledger.
"""
from __future__ import annotations

import contextlib
import heapq
import json
import os
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
QUOTA_OUT = REPORTS / "MARKET_QUOTA.json"
SCAN_STATE = BASE / "data" / "market_quota_scan.json"
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"

#: The principal's bounds. Non-exotic is a FLOOR, exotic a CEILING; the exotic share inside it is
#: earned by yield.
EXOTIC_CAP = 0.10
#: An exotic group producing nothing decays to this, never to zero: at zero it could never be
#: measured again and the rule "earned by yield" would be unable to re-earn anything.
EXOTIC_FLOOR = 0.005
#: Pseudo-trials of house rate each group's yield is shrunk toward.
PRIOR_TRIALS = 200.0
#: Yield vs uniform blend, for groups and for families alike. The uniform half IS the per-family
#: minimum exploration share: a family's share never falls below (1 - YIELD_STRENGTH) / n_families
#: of its group, whatever its record, so no family with a queue starves.
YIELD_STRENGTH = float(os.environ.get("MARKET_QUOTA_YIELD_STRENGTH", "0.5"))
#: Breadth gaps the principal named (gold, indices) get this weight on top of their yield.
GAP_BOOST = {"gold": 1.5, "indices": 1.5}
#: Days of ledger kept in the day buckets, and the window yields are read over.
WINDOW_DAYS = 30
REALISED_HOURS = 24

#: Currencies whose pairs are exotic even where a registry row lacks the class. The registry's
#: own "Forex Exotics" class wins where it exists.
EXOTIC_CCY = frozenset({"NOK", "SEK", "ZAR", "MXN", "TRY", "PLN", "HUF", "CZK", "HKD", "SGD",
                        "CNH", "DKK", "ILS", "THB", "RUB", "BRL", "IDR", "INR", "KRW", "CLP",
                        "COP", "TWD", "PHP", "MYR"})
_FX = re.compile(r"^[A-Z]{6}$")
_INDEX_HINT = ("US30", "US500", "NAS100", "US2000", "GER", "DE40", "UK100", "FRA40", "EU50",
               "JP225", "AUS200", "HK50", "ESP35", "STOXX", "SPX", "NDX", "DJ30", "CHINA50")
_CLASS_GROUP = (("exotic", "exotic"), ("forex", "fx"), ("fx", "fx"), ("ind", "indices"),
                ("energy", "energy"), ("soft", "softs"), ("bond", "bonds"),
                ("crypto", "crypto"), ("equit", "equities"), ("share", "equities"),
                ("stock", "equities"), ("commod", "metals"), ("metal", "metals"))


def _asset_class(symbol: str) -> str:
    try:
        from research.universe_policy import asset_class_of
    except Exception:
        try:
            from universe_policy import asset_class_of  # type: ignore[no-redef]
        except Exception:
            return ""
    try:
        return str(asset_class_of(symbol) or "").lower()
    except Exception:
        return ""


_GROUP_MEMO: dict[str, str] = {}


def group_of(symbol: str, asset_class: str | None = None) -> str:
    """The market group a symbol's trials are charged to.

    exotic | fx | gold | metals | indices | energy | softs | bonds | crypto | equities | other.
    Gold is split from the other metals because it is a named breadth gap and the desk's largest
    book. The exotic test is the registry's class first, then the currency list, so a pair the
    registry has not classified yet is still caught by what it is.
    """
    s = str(symbol or "").strip().upper()
    if asset_class is None and s in _GROUP_MEMO:
        return _GROUP_MEMO[s]
    cls = (asset_class if asset_class is not None else _asset_class(s)).lower()
    if s.startswith("XAU") or s in {"GOLD", "XAUUSD"}:
        g = "gold"
    elif "exotic" in cls or (_FX.match(s) and (s[:3] in EXOTIC_CCY or s[3:] in EXOTIC_CCY)):
        g = "exotic"
    elif s[:3] in {"XAG", "XPT", "XPD", "XCU"} or s in {"SILVER", "COPPER"}:
        g = "metals"
    else:
        g = next((grp for key, grp in _CLASS_GROUP if key in cls), "")
        if not g:
            if _FX.match(s):
                g = "fx"
            elif any(h in s for h in _INDEX_HINT):
                g = "indices"
            else:
                g = "other"
    if asset_class is None:
        _GROUP_MEMO[s] = g
    return g


def is_exotic(symbol: str) -> bool:
    return group_of(symbol) == "exotic"


def symbol_family_of_cell(cell: str) -> tuple[str, str]:
    """The judge's cell id (`frontier_identity.cell_id`) -> (SYMBOL, family).

    The id is `SYMBOL[@TF].family.p=<digest>` or `SYMBOL[@TF].family.rr=<x>_wb=<y>`. Symbols may
    hold a dot (`US30.cash`), families do not, so the family is the segment before the trailing
    `key=value` one. The `@TF` chart suffix is stripped from the symbol: `GBPAUD@M15` is GBPAUD,
    and without the strip every non-H1 cell would be grouped as "other".
    """
    parts = str(cell or "").split(".")
    if len(parts) >= 3 and "=" in parts[-1]:
        sym, fam = ".".join(parts[:-2]), parts[-2]
    elif len(parts) >= 2:
        sym, fam = parts[0], parts[1]
    else:
        sym, fam = str(cell or ""), "?"
    return sym.split("@", 1)[0], fam


#: Wrapper families whose cells are minted for a BASE family and must be counted under it. Only
#: these: `base_family` is also a parameter of regime_split, exit_operated and others, which are
#: families in their own right and keep their own counts.
ATTRIBUTE_TO_BASE = frozenset({"hunt16_cell"})
BASE_MAP = BASE / "data" / "market_quota_base_family.json"
FAMILY_STATUS = BASE / "data" / "family_status.json"
#: Statuses that take a family out of the "never judged" count and out of the exploration share,
#: each reported by name with its missed-growth line. Absent or ACTIVE means live.
NOT_LIVE_STATUSES = frozenset({"BLOCKED_ON_TERMS", "RETIRED", "BLOCKED_ON_DATA"})


def attributed_family(sp: dict[str, Any]) -> str:
    """The family a spec's trials are COUNTED under: its own, or its base for a wrapper family
    (`hunt16_cell` with `params.base_family = dav_bb_meanrev` counts as dav_bb_meanrev)."""
    fam = str(sp.get("family") or "?")
    if fam in ATTRIBUTE_TO_BASE:
        p = sp.get("params") if isinstance(sp.get("params"), dict) else {}
        base = str((p or {}).get("base_family") or sp.get("base_family") or "").strip()
        if base:
            return base
    return fam


def family_status(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """{family: row} from `data/family_status.json` for families that are NOT live, with why.

    Unreadable or absent reads as NOTHING BLOCKED: a missing file must never silence a family.
    """
    try:
        doc = json.loads((path or FAMILY_STATUS).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("families") if isinstance(doc, dict) else None
    return {str(f): dict(r) for f, r in (rows or {}).items()
            if isinstance(r, dict) and str(r.get("status") or "").upper() in NOT_LIVE_STATUSES}


def _cell_id_of(sp: dict[str, Any]) -> str | None:
    try:
        from research.frontier_identity import cell_id
    except Exception:
        try:
            from frontier_identity import cell_id  # type: ignore[no-redef]
        except Exception:
            return None
    try:
        return str(cell_id({"sym": _sym(sp), "family": sp.get("family"),
                            "params": dict(sp.get("params") or {})}))
    except Exception:
        return None


def remember_bases(specs: Iterable[dict[str, Any]], path: Path | None = None,
                   cap: int = 500_000) -> int:
    """Record judge cell id -> base family for every wrapper-family spec in the intake, so the
    LEDGER side (whose cell id names only `hunt16_cell`) can attribute its trials too."""
    p = path or BASE_MAP
    try:
        cur = json.loads(p.read_text("utf-8"))
        if not isinstance(cur, dict):
            cur = {}
    except (OSError, ValueError):
        cur = {}
    n0 = len(cur)
    for sp in specs:
        if str(sp.get("family") or "") not in ATTRIBUTE_TO_BASE:
            continue
        base = attributed_family(sp)
        if base == sp.get("family"):
            continue
        cid = _cell_id_of(sp)
        if cid and cid not in cur and len(cur) < cap:
            cur[cid] = base
    if len(cur) != n0:
        with contextlib.suppress(OSError):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(cur, separators=(",", ":")), encoding="utf-8")
    return len(cur) - n0


def _base_map(path: Path | None = None) -> dict[str, str]:
    try:
        cur = json.loads((path or BASE_MAP).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return cur if isinstance(cur, dict) else {}


# ------------------------------------------------------------------------- the ledger scan

_AT = re.compile(r'"at"\s*:\s*"([^"]+)"')


def _ruled(row: dict[str, Any]) -> bool:
    try:
        from research.judging_burndown import classify
    except Exception:
        try:
            from judging_burndown import classify  # type: ignore[no-redef]
        except Exception:
            gate = str(row.get("terminal_gate") or "")
            return row.get("passed") is True or bool(gate and gate != "UNKNOWN")
    return classify(row) == "ruled"


def _empty_state() -> dict[str, Any]:
    return {"schema": "market-quota-scan/1", "offset": 0, "size": 0, "days": {},
            "hours": {}, "families_ever": {}}


def scan_ledger(path: Path | None = None, state_path: Path | None = None, *,
                now: datetime | None = None, write: bool = True,
                deadline_s: float | None = 90.0,
                base_map: Path | None = None) -> dict[str, Any]:
    """Incremental scan of the gate ledger into day buckets of ruled trials and passes.

    The ledger is append-only and runs past a million rows, so this keeps a byte offset and adds
    only what was appended since. A ledger SHORTER than the offset was rewritten (a repair): it is
    rescanned whole. Day buckets older than WINDOW_DAYS are dropped; `families_ever` (ruled trials
    per family, all time) is kept, because "never judged" is an all-time statement.
    """
    p = GATE_LEDGER if path is None else path
    sp = SCAN_STATE if state_path is None else state_path
    now = now or datetime.now(UTC)
    try:
        st = json.loads(sp.read_text("utf-8"))
        if not isinstance(st, dict) or st.get("schema") != "market-quota-scan/1":
            st = _empty_state()
    except (OSError, ValueError):
        st = _empty_state()
    if not p.exists():
        st["status"] = "UNMEASURED"
        st["why"] = f"{p.name} absent: realised trials by group are UNMEASURED"
        return st
    size = p.stat().st_size
    if size < int(st.get("offset") or 0):
        st = _empty_state()
    days: dict[str, Any] = st["days"]
    hours: dict[str, Any] = st["hours"]
    ever: dict[str, int] = st["families_ever"]
    import time as _time
    bases: dict[str, str] | None = None
    stop_at = None if deadline_s is None else _time.monotonic() + float(deadline_s)
    caught_up = True
    with p.open("rb") as fh:
        fh.seek(int(st.get("offset") or 0))
        n_read = 0
        while True:
            n_read += 1
            if stop_at is not None and n_read % 5000 == 0 and _time.monotonic() > stop_at:
                # BOUNDED, AND RESUMED: the first scan of a million-row ledger outlasts one pass.
                # Progress is saved at the offset reached and the next pass continues from it;
                # until it catches up the realised split is UNMEASURED, never a prefix's count.
                caught_up = False
                break
            raw = fh.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                break                       # a row still being written: read it next pass
            st["offset"] = int(st.get("offset") or 0) + len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or not _ruled(row):
                continue
            at = str(row.get("at") or "")
            day, hour = at[:10], at[:13]
            if len(day) != 10:
                continue
            cell_name = str(row.get("cell") or "")
            sym, fam = symbol_family_of_cell(cell_name)
            if fam in ATTRIBUTE_TO_BASE:
                if bases is None:
                    bases = _base_map(base_map)
                fam = bases.get(cell_name, fam)
            grp = group_of(sym)
            ever[fam] = int(ever.get(fam, 0)) + 1
            b = days.setdefault(day, {"groups": {}, "families": {}})
            for key, name in (("groups", grp), ("families", fam)):
                cell = b[key].setdefault(name, {"trials": 0, "passed": 0, "edges": []})
                cell["trials"] += 1
                if row.get("passed") is True:
                    cell["passed"] += 1
                    pair = f"{sym}|{fam}"
                    if pair not in cell["edges"]:
                        cell["edges"].append(pair)
            h = hours.setdefault(hour, {})
            h[grp] = int(h.get(grp, 0)) + 1
    st["size"] = size
    keep_day = (now - timedelta(days=WINDOW_DAYS)).date().isoformat()
    for d in [d for d in days if d < keep_day]:
        del days[d]
    keep_hour = (now - timedelta(hours=REALISED_HOURS + 1)).isoformat()[:13]
    for h in [h for h in hours if h < keep_hour]:
        del hours[h]
    st["status"] = "MEASURED" if caught_up else "CATCHING_UP"
    if not caught_up:
        st["why"] = (f"ledger scan resumed at byte {st['offset']:,} of {size:,}: realised split "
                     "UNMEASURED until it catches up")
    else:
        st.pop("why", None)
    st["scanned_at"] = now.isoformat(timespec="seconds")
    if write:
        try:
            sp.parent.mkdir(parents=True, exist_ok=True)
            tmp = sp.with_suffix(".tmp")
            tmp.write_text(json.dumps(st), encoding="utf-8")
            try:
                os.replace(tmp, sp)
            except OSError:
                sp.write_text(tmp.read_text("utf-8"), encoding="utf-8")
        except OSError:
            pass
    return st


def _roll(st: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for b in (st.get("days") or {}).values():
        for name, c in (b.get(key) or {}).items():
            o = out.setdefault(name, {"trials": 0, "passed": 0, "edges": set()})
            o["trials"] += int(c.get("trials") or 0)
            o["passed"] += int(c.get("passed") or 0)
            o["edges"].update(c.get("edges") or [])
    return out


def yields(st: dict[str, Any], key: str = "groups") -> dict[str, dict[str, Any]]:
    """{name: {trials, passed, edges, yield}} with yield = distinct passing pairs per ruled trial,
    shrunk toward the pooled rate by PRIOR_TRIALS."""
    raw = _roll(st, key)
    tot_t = sum(v["trials"] for v in raw.values())
    tot_e = sum(len(v["edges"]) for v in raw.values())
    pooled = (tot_e / tot_t) if tot_t else 0.0
    out: dict[str, dict[str, Any]] = {}
    for name, v in raw.items():
        e = len(v["edges"])
        out[name] = {"trials": v["trials"], "passed": v["passed"], "edges": e,
                     "yield": (e + PRIOR_TRIALS * pooled) / (v["trials"] + PRIOR_TRIALS)}
    out["_pooled"] = {"trials": tot_t, "edges": tot_e, "yield": pooled}
    return out


# --------------------------------------------------------------------------- the shares

def shares(groups_present: Iterable[str], ylds: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Target trial share per group present in this intake.

    exotic = EXOTIC_CAP x min(1, exotic yield / non-exotic yield), floored at EXOTIC_FLOOR; the
    rest is split over the non-exotic groups by yield blended with uniform at YIELD_STRENGTH and
    weighted by GAP_BOOST. A group absent from the intake gets nothing and its share flows to the
    present ones.
    """
    present = sorted(set(groups_present))
    pooled = float((ylds.get("_pooled") or {}).get("yield") or 0.0)

    def y(g: str) -> float:
        return float((ylds.get(g) or {}).get("yield", pooled) or 0.0)

    non = [g for g in present if g != "exotic"]
    out: dict[str, float] = {}
    why: dict[str, str] = {}
    ex_share = 0.0
    if "exotic" in present:
        nt = sum(int((ylds.get(g) or {}).get("trials") or 0) for g in non)
        ne = sum(int((ylds.get(g) or {}).get("edges") or 0) for g in non)
        y_non = (ne + PRIOR_TRIALS * pooled) / (nt + PRIOR_TRIALS) if (nt or pooled) else 0.0
        ratio = (y("exotic") / y_non) if y_non > 0 else 1.0
        ex_share = EXOTIC_CAP if not non else max(EXOTIC_FLOOR, EXOTIC_CAP * min(1.0, ratio))
        out["exotic"] = ex_share
        why["exotic"] = (f"earned {ratio:.2f}x the non-exotic yield -> "
                         f"{ex_share:.1%} (cap {EXOTIC_CAP:.0%}, floor {EXOTIC_FLOOR:.1%})")
    if non:
        top = max((y(g) for g in non), default=0.0) or 1.0
        w = {g: (YIELD_STRENGTH * (y(g) / top) + (1.0 - YIELD_STRENGTH)) * GAP_BOOST.get(g, 1.0)
             for g in non}
        tot = sum(w.values()) or 1.0
        rest = 1.0 - ex_share
        for g in non:
            out[g] = rest * w[g] / tot
            why[g] = (f"yield {y(g):.2e}" + (f", breadth gap x{GAP_BOOST[g]:g}"
                                              if g in GAP_BOOST else ""))
    return {"shares": out, "why": why, "exotic_share": ex_share,
            "non_exotic_share": 1.0 - ex_share}


def family_weights(families: Iterable[str], fylds: dict[str, dict[str, Any]],
                   blocked: dict[str, Any] | None = None) -> dict[str, float]:
    """Within a group: yield blended with uniform, so every family keeps at least
    (1 - YIELD_STRENGTH) / n of the group's turns -- the exploration floor."""
    fams = sorted(set(families))
    if not fams:
        return {}
    pooled = float((fylds.get("_pooled") or {}).get("yield") or 0.0)
    ys = {f: float((fylds.get(f) or {}).get("yield", pooled) or 0.0) for f in fams}
    n = len(fams)
    tot = sum(ys.values())
    if tot <= 0:
        w = dict.fromkeys(fams, 1.0 / n)
    else:
        w = {f: YIELD_STRENGTH * ys[f] / tot + (1.0 - YIELD_STRENGTH) / n for f in fams}
    # A family the registry marks not live (blocked on terms, retired) keeps its cells in the
    # docket but is given no exploration share: it is reached only after every live family.
    for f in set(fams) & set(blocked if blocked is not None else family_status()):
        w[f] = 1e-9
    return w


def _deficit_interleave(buckets: dict[str, list[Any]], weights: dict[str, float]) -> list[Any]:
    """Merge buckets so every prefix holds each bucket as close to its weight as the counts allow.

    Smallest (taken + 1) / weight first -- the stride scheduler. Each bucket's own order is kept.
    An exhausted bucket leaves and the rest share its turns in proportion.
    """
    heap: list[tuple[float, int, str]] = []
    pos: dict[str, int] = {}
    for i, (k, rows) in enumerate(sorted(buckets.items())):
        if rows:
            w = max(float(weights.get(k) or 0.0), 1e-12)
            heap.append((1.0 / w, i, k))
            pos[k] = 0
    heapq.heapify(heap)
    out: list[Any] = []
    while heap:
        _, i, k = heapq.heappop(heap)
        rows = buckets[k]
        out.append(rows[pos[k]])
        pos[k] += 1
        if pos[k] < len(rows):
            w = max(float(weights.get(k) or 0.0), 1e-12)
            heapq.heappush(heap, ((pos[k] + 1) / w, i, k))
    return out


def _sym(sp: dict[str, Any]) -> str:
    return str(sp.get("sym") or sp.get("symbol") or "")


def _fam(sp: dict[str, Any]) -> str:
    return attributed_family(sp)


def order_tier(specs: Sequence[dict[str, Any]], plan: dict[str, Any],
               fylds: dict[str, dict[str, Any]], allow: int
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(ordered, held) for one tier. Families interleave inside each group by `family_weights`;
    groups interleave by `plan['shares']`; exotic cells past `allow` are held."""
    by_group: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for sp in specs:
        by_group.setdefault(group_of(_sym(sp)), {}).setdefault(_fam(sp), []).append(sp)
    merged: dict[str, list[dict[str, Any]]] = {}
    for g, fams in by_group.items():
        merged[g] = _deficit_interleave(fams, family_weights(fams, fylds))
    ex = merged.pop("exotic", [])
    allow = max(0, int(allow))
    held, ex = ex[allow:], ex[:allow]
    non = _deficit_interleave(merged, plan["shares"])
    # EXOTICS ARE PLACED BY THEIR SHARE OF THE WHOLE PREFIX, not by weight among the groups still
    # holding cells: when gold runs out a weight split would hand its turns to exotics in
    # proportion, and the tail of a round would run far past the 10% the principal set.
    share = float(plan["shares"].get("exotic") or 0.0)
    out: list[dict[str, Any]] = []
    k = 0
    for sp in non:
        out.append(sp)
        while k < len(ex) and (k + 1) <= share * (len(out) + 1):
            out.append(ex[k])
            k += 1
    held = ex[k:] + held
    return out, held


def exotic_allowance(n_non_exotic: int, exotic_share: float) -> int:
    """Exotic cells allowed beside `n_non_exotic` others so exotics are at most `exotic_share`
    of the trials sent. With nothing else sent the allowance is zero: the rule is a share of
    trials, and an exotic-only round would spend 100% of them on exotics."""
    if n_non_exotic <= 0 or exotic_share <= 0:
        return 0
    return int(exotic_share / max(1e-9, 1.0 - exotic_share) * n_non_exotic)


def apply_quota(specs: Sequence[dict[str, Any]], *, st: dict[str, Any] | None = None,
                write: bool = True, now: datetime | None = None,
                out_path: Path | None = None) -> tuple[list[dict[str, Any]],
                                                       list[dict[str, Any]], dict[str, Any]]:
    """(ordered, held, report) for the warmer's build list.

    Never-judged cells stay ahead of re-judges (the sealed sweep's primary key and the warmer's
    `backlog_first`); the quota interleaves inside each tier. `held` are exotic cells over the
    exotic share, kept in the docket for a later round.
    """
    now = now or datetime.now(UTC)
    st = st if st is not None else scan_ledger(now=now)
    gy, fy = yields(st, "groups"), yields(st, "families")
    groups = {group_of(_sym(sp)) for sp in specs}
    plan = shares(groups, gy)
    new = [sp for sp in specs if sp.get("_never_judged", True)]
    old = [sp for sp in specs if not sp.get("_never_judged", True)]
    n_non = sum(1 for sp in specs if group_of(_sym(sp)) != "exotic")
    allow = exotic_allowance(n_non, float(plan["shares"].get("exotic") or 0.0))
    n_ex_new = sum(1 for sp in new if group_of(_sym(sp)) == "exotic")
    o_new, h_new = order_tier(new, plan, fy, min(allow, n_ex_new))
    o_old, h_old = order_tier(old, plan, fy, allow - min(allow, n_ex_new))
    ordered, held = o_new + o_old, h_new + h_old
    intake: dict[str, dict[str, int]] = {}
    for sp in specs:
        g = intake.setdefault(group_of(_sym(sp)), {"intake": 0, "sent": 0, "held": 0})
        g["intake"] += 1
    for sp in ordered:
        intake[group_of(_sym(sp))]["sent"] += 1
    for sp in held:
        intake[group_of(_sym(sp))]["held"] += 1
    fam_intake: dict[str, int] = {}
    for sp in ordered:
        fam_intake[_fam(sp)] = fam_intake.get(_fam(sp), 0) + 1
    report = {
        "at": now.isoformat(timespec="seconds"),
        "rule": ("non-exotic trials are a FLOOR of 90%; exotics earn up to 10% by yield (distinct "
                 "passing symbol-family pairs per ruled trial, shrunk to the pooled rate) and "
                 "decay "
                 f"to {EXOTIC_FLOOR:.1%}; non-exotic groups split by yield blended with uniform at "
                 f"{YIELD_STRENGTH:g}, gold and indices weighted x1.5 as breadth gaps; inside each "
                 "group every family keeps at least its uniform exploration share; never-judged "
                 "cells first; every prefix balanced; nothing dropped"),
        "ledger": {k: st.get(k) for k in ("status", "why", "scanned_at", "offset")},
        "target_shares": {g: round(v, 4) for g, v in plan["shares"].items()},
        "why": plan["why"],
        "exotic_target_share": round(plan["exotic_share"], 4),
        "group_yields": {g: {k: (round(v, 8) if isinstance(v, float) else v)
                             for k, v in d.items()} for g, d in gy.items()},
        "intake_by_group": intake,
        "intake_exotic_share": (round(intake.get("exotic", {}).get("sent", 0) / len(ordered), 4)
                                if ordered else None),
        "held_exotic": len(held),
        "families_in_intake": len(fam_intake),
        "family_cells_sent": dict(sorted(fam_intake.items(), key=lambda kv: -kv[1])),
    }
    if write:
        with contextlib.suppress(Exception):
            report["base_family_cells_recorded"] = remember_bases(specs)
        p = QUOTA_OUT if out_path is None else out_path
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        except OSError:
            pass
    return ordered, held, report


def family_funnel(stages: dict[str, Sequence[dict[str, Any]]]) -> dict[str, Any]:
    """Cells per family at each named stage, and for every family that reaches the docket but
    not the build list, the first stage it vanished at."""
    names = list(stages)
    counts: dict[str, dict[str, int]] = {n: {} for n in names}
    for n, rows in stages.items():
        c = counts[n]
        for sp in rows:
            c[_fam(sp)] = c.get(_fam(sp), 0) + 1
    fams = sorted(set().union(*[set(c) for c in counts.values()])) if counts else []
    lost: dict[str, str] = {}
    last = names[-1] if names else ""
    for f in fams:
        if counts.get(last, {}).get(f):
            continue
        prev = None
        for n in names:
            if n == "held_deferred":
                continue
            if not counts[n].get(f):
                lost[f] = (f"{counts.get(prev, {}).get(f, 0)} at {prev}, 0 at {n}"
                           if prev else f"absent from {n}")
                break
            prev = n
    return {"stages": names,
            "by_family": {f: [counts[n].get(f, 0) for n in names] for f in fams},
            "not_built_this_round": lost}


def head_report(report: dict[str, Any], sent: Sequence[dict[str, Any]],
                out_path: Path | None = None,
                funnel: dict[str, Sequence[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """After the gate-room cut: what the round will ACTUALLY build, by group and family."""
    if funnel:
        report["family_funnel"] = family_funnel(funnel)
    by_g: dict[str, int] = {}
    by_f: dict[str, int] = {}
    for sp in sent:
        g = group_of(_sym(sp))
        by_g[g] = by_g.get(g, 0) + 1
        by_f[_fam(sp)] = by_f.get(_fam(sp), 0) + 1
    report["built_this_round"] = {
        "cells": len(sent), "by_group": by_g,
        "exotic_share": round(by_g.get("exotic", 0) / len(sent), 4) if sent else None,
        "families": len(by_f),
    }
    p = QUOTA_OUT if out_path is None else out_path
    with contextlib.suppress(OSError):
        p.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


def realised_split(st: dict[str, Any] | None = None, *, now: datetime | None = None,
                   live_families: Iterable[str] | None = None,
                   status_path: Path | None = None) -> dict[str, Any]:
    """The REALISED split for JUDGING_RATE.json: ruled trials by group in the last 24h, the
    exotic share against its target, and the families with no ruled trial ever."""
    now = now or datetime.now(UTC)
    if st is None:
        st = scan_ledger(now=now)
    if st.get("status") != "MEASURED":
        return {"status": "UNMEASURED", "why": st.get("why") or "ledger scan unavailable"}
    cut = (now - timedelta(hours=REALISED_HOURS)).isoformat()[:13]
    by_g: dict[str, int] = {}
    for h, gs in (st.get("hours") or {}).items():
        if h >= cut:
            for g, n in gs.items():
                by_g[g] = by_g.get(g, 0) + int(n)
    tot = sum(by_g.values())
    ex = by_g.get("exotic", 0)
    target = None
    with contextlib.suppress(OSError, ValueError, AttributeError):
        target = json.loads(QUOTA_OUT.read_text("utf-8")).get("exotic_target_share")
    share = (ex / tot) if tot else None
    status = ("UNMEASURED" if share is None else
              ("OK" if share <= EXOTIC_CAP + 1e-9 else "BREACH"))
    ever = st.get("families_ever") or {}
    blocked = family_status(status_path)
    zero = sorted(set(live_families or ()) - {f for f, n in ever.items() if n} - set(blocked))
    return {"status": status, "window_h": REALISED_HOURS, "ruled_trials": tot,
            "by_group": dict(sorted(by_g.items(), key=lambda kv: -kv[1])),
            "exotic_share": round(share, 4) if share is not None else None,
            "exotic_cap": EXOTIC_CAP, "exotic_target_share": target,
            "non_exotic_share": round(1 - share, 4) if share is not None else None,
            "families_ruled_ever": sum(1 for n in ever.values() if n),
            "families_never_ruled": zero,
            # NOT ZERO, NOT LIVE: each with the reason and the growth it costs, by name.
            "families_not_live": {f: {k: r.get(k) for k in ("status", "why", "missed_growth",
                                                           "reopen_when", "since")}
                                  for f, r in sorted(blocked.items())},
            "rule": ("BREACH when exotics took more than 10% of the last 24h's ruled trials; the "
                     "intake holds exotics over their share, so a BREACH means cells reached the "
                     "judge by another door (already warm, or the sealed sweep's own builds)")}
