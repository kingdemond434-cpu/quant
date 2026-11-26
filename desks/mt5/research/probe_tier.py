"""THE PROBE TIER: every promising strategy trades live small, and the losers drop out fast.

zuck 2026-11-26 22:50Z: "make 13 of them live like planned n demote unprofitable ones asap
simple automated by box allocator", then 22:53Z: demotion is general, not gold-only, and "what
if its too strict n false demotes". This module is the decision; the promoter (main roster),
`prop/e8_book` (E8) and the prop allocator read its artifact. It never sends an order.

ADMISSION (`eligible`). A forward clock in `reports/shadow/shadow_state.json` that is ACTIVE or a
PROMOTION CANDIDATE, with n >= PROBE_MIN_N forward trades, a positive cumulative R, a forward t
at or above the self-tuned T_IN, a non-exotic and classified symbol, a fill-hour spread basis
(the record is priced at the hour it fills) and a family not banned. XAUUSD session brackets are
the armed gold book and `prop/e8_gold.session_probe`'s; they are left to those owners.

SIZE (`shrink`). n/(n+PROBE_SHRINK_N0) of the consuming lane's own ceiling, the rule Audit
accepted for #1370. The lane supplies the ceiling; this module only supplies the shrink, so no
lane's limit is restated here. A measured allocator answer, where there is one, still wins.

ONE BET PER CO-MOVE GROUP (`comove_groups`). Same symbol is not same bet (zuck 11-25): rows are
grouped only on MEASURED co-movement -- an identical forward record, or a Pearson correlation of
their daily forward R of at least COMOVE_RHO over at least COMOVE_MIN_OVERLAP common days. The
group trades once, through its representative (a member already live, else the best forward t).

DEMOTION (`sprt_llr`). A Gaussian sequential probability ratio test on the R the row produced
SINCE IT WENT LIVE, against its own expectation: H0 mean R = MU0_FRAC x exp_r at admission
(the row is still earning) vs H1 mean R = 0 (the edge is gone), sigma from the row's own sum of
squares. The sum is sufficient, so no per-trade replay is needed. LLR >= log((1-beta)/alpha)
demotes. A demoted row goes back to FORWARD ONLY -- its clock keeps running, nothing is retired
-- and is re-admitted once the R it produced since the demotion accepts H0
(LLR <= log(beta/(1-alpha)) over at least READMIT_MIN_N trades) AND it is eligible again: the
hysteresis.

FALSE AND LATE DEMOTES ARE BILLED (`score_outcomes`, `tune`). Every demote is logged with what
the row did next. A false demote's cost is the R it made after it was demoted (growth forgone); a
late demote's cost is the R it lost while live before the test tripped. The tuner moves alpha
toward whichever side cost less, and T_IN by what admitted rows actually did, inside declared
ranges, scored in missed growth. That is the Rule-1 proof the demotion owes (GROWTH_GOVERNANCE):
a risk reduction that keeps costing more than it saves loosens itself.

Revert: data/PROBE_TIER_OFF (the artifact then lists nothing live).
Artifacts: reports/PROBE_TIER.json, reports/probe_ledger.jsonl, data/PROBE_TIER_STATE.json.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
OUT = DESK / "reports" / "PROBE_TIER.json"
LEDGER = DESK / "reports" / "probe_ledger.jsonl"
STATE = DESK / "data" / "PROBE_TIER_STATE.json"
OFF = DESK / "data" / "PROBE_TIER_OFF"

PROBE_MIN_N = 10
PROBE_SHRINK_N0 = 50
T_IN_DEFAULT = 0.5
T_IN_RANGE = (0.3, 1.5)
ALPHA_DEFAULT = 0.05
ALPHA_RANGE = (0.01, 0.20)
BETA = 0.20
MU0_FRAC = 0.5
MU0_FLOOR = 0.02
SIGMA_FLOOR = 0.25
READMIT_MIN_N = 5
OUTCOME_N = 10
COMOVE_RHO = 0.7
COMOVE_MIN_OVERLAP = 8
TUNE_MIN_OUTCOMES = 3
TUNE_HISTORY = 60
#: An artifact older than this is not a probe decision any consumer may act on.
MAX_AGE_S = 3 * 3600

LIVE_CLOCK_STATUSES = ("ACTIVE", "PROMOTION CANDIDATE", "PROMOTION_CANDIDATE")


# ----------------------------------------------------------------------------- pure pieces
def shrink(n: float) -> float:
    """n/(n+N0): the probe share of a lane's ceiling. 0 for no trades."""
    return float(n) / (float(n) + PROBE_SHRINK_N0) if n and n > 0 else 0.0


def parse_key(key: str, ident: Mapping[str, Any] | None = None) -> dict[str, str]:
    """symbol / family / selector / timeframe of a clock key, from its identity when known."""
    head = str(key).split("#", 1)[0]
    parts = head.split(".")
    tf = "H1"
    if ident:
        sym = str(ident.get("symbol") or parts[0])
        fam = str(ident.get("family") or "")
        sel = str(ident.get("selector") or "")
        params = ident.get("params") or {}
        if isinstance(params, Mapping) and params.get("timeframe"):
            tf = str(params["timeframe"])
    else:
        sym = parts[0]
        if len(parts) >= 3:
            fam, sel = parts[1], parts[2]
        else:
            fam, sel = "session_range_breakout", parts[1] if len(parts) > 1 else ""
    if "@" in sel:
        sel, tf = sel.split("@", 1)
    elif "@" in head:
        tf = head.rsplit("@", 1)[1]
    return {"symbol": sym.upper(), "family": fam, "selector": sel or "asia", "timeframe": tf}


def column_of(meta: Mapping[str, str]) -> str:
    """The prop books' column for this row: SYMBOL_family_selector (prop/e8_book)."""
    return f"{meta['symbol']}_{meta['family']}_{meta['selector'] or 'asia'}"


def sigma_of(row: Mapping[str, Any]) -> float:
    """The row's own per-trade R standard deviation: from its sum of squares when the engine
    publishes one, else backed out of its forward t (t = mean/sd x sqrt n), floored."""
    n = float(row.get("n") or 0)
    s = float(row.get("cum_r") or 0.0)
    s2 = row.get("sum_r2")
    if n >= 2 and isinstance(s2, (int, float)) and not isinstance(s2, bool):
        var = (float(s2) - s * s / n) / (n - 1)
        if var > 0 and math.isfinite(var):
            return max(math.sqrt(var), SIGMA_FLOOR)
    t = row.get("forward_t")
    if n >= 2 and isinstance(t, (int, float)) and t and math.isfinite(float(t)):
        sd = abs((s / n) * math.sqrt(n) / float(t))
        if sd > 0 and math.isfinite(sd):
            return max(sd, SIGMA_FLOOR)
    return 1.0


def sprt_llr(post_n: float, post_sum: float, mu0: float, sigma: float) -> float:
    """log L(H1: mean 0) / L(H0: mean mu0) for post_n Gaussian draws summing to post_sum."""
    if post_n <= 0:
        return 0.0
    return (post_n * mu0 * mu0 - 2.0 * mu0 * post_sum) / (2.0 * sigma * sigma)


def bounds(alpha: float, beta: float = BETA) -> tuple[float, float]:
    """(demote bound A, re-admit bound B) of Wald's SPRT."""
    return math.log((1.0 - beta) / alpha), math.log(beta / (1.0 - alpha))


def _daily(tail: object) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(tail, list):
        return out
    for item in tail:
        try:
            ts, r = item[0], float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        day = str(ts)[:10]
        out[day] = out.get(day, 0.0) + r
    return out


def _rho(a: Mapping[str, float], b: Mapping[str, float]) -> float | None:
    days = sorted(set(a) & set(b))
    if len(days) < COMOVE_MIN_OVERLAP:
        return None
    xa = [a[d] for d in days]
    xb = [b[d] for d in days]
    ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
    va = sum((x - ma) ** 2 for x in xa)
    vb = sum((x - mb) ** 2 for x in xb)
    if va <= 0 or vb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(xa, xb, strict=True)) / math.sqrt(va * vb)


def fingerprint(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (int(row.get("n") or 0), round(float(row.get("cum_r") or 0.0), 4),
            str(row.get("first_entry")), str(row.get("last_entry")))


def comove_groups(rows: Mapping[str, Mapping[str, Any]]) -> list[list[str]]:
    """Groups of keys that measured as one bet. Pure."""
    keys = sorted(rows)
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_fp: dict[tuple[Any, ...], str] = {}
    for k in keys:
        fp = fingerprint(rows[k])
        if fp in by_fp:
            union(by_fp[fp], k)
        else:
            by_fp[fp] = k
    daily = {k: _daily(rows[k].get("r_tail")) for k in keys}
    with_tail = [k for k in keys if len(daily[k]) >= COMOVE_MIN_OVERLAP]
    for i, a in enumerate(with_tail):
        for b in with_tail[i + 1:]:
            if find(a) == find(b):
                continue
            rho = _rho(daily[a], daily[b])
            if rho is not None and rho >= COMOVE_RHO:
                union(a, b)
    groups: dict[str, list[str]] = {}
    for k in keys:
        groups.setdefault(find(k), []).append(k)
    return sorted(groups.values())


def _num(v: object, default: float = 0.0) -> float:
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
        return float(v)
    return default


def _class_refusal(symbol: str) -> str | None:
    try:
        from universe_policy import live_class_refusal
    except Exception:
        try:
            from research.universe_policy import live_class_refusal
        except Exception as exc:                     # fail closed: no registry, no live probe
            return f"class registry unavailable ({type(exc).__name__})"
    return live_class_refusal(symbol)


def _banned(family: str) -> str | None:
    try:
        from family_policy import ban_reason, family_banned
    except Exception:
        try:
            from research.family_policy import ban_reason, family_banned
        except Exception:
            return None
    return ban_reason(family) if family_banned(family) else None


def _fill_hour(basis: object) -> bool:
    b = str(basis or "")
    if b == "fill_hour":
        return True
    tail = b[len("fill_hour_"):] if b.startswith("fill_hour_") else ""
    return len(tail) == 2 and tail.isdigit() and 0 <= int(tail) <= 23


def eligible(key: str, row: Mapping[str, Any], meta: Mapping[str, str], t_in: float
             ) -> str | None:
    """None when the clock may enter the probe tier now, else why not."""
    st = str(row.get("status") or "").upper()
    if st not in LIVE_CLOCK_STATUSES:
        return f"clock status {row.get('status')!r}"
    n = _num(row.get("n"))
    if n < PROBE_MIN_N:
        return f"n={int(n)} < {PROBE_MIN_N}"
    if _num(row.get("cum_r")) <= 0:
        return "cumulative forward R is not positive"
    t = _num(row.get("forward_t"), float("nan"))
    if not math.isfinite(t) or t < t_in:
        return f"forward t {row.get('forward_t')} < T_IN {t_in:.2f}"
    if meta["symbol"] == "XAUUSD" and meta["family"] == "session_range_breakout":
        return "XAUUSD session bracket: the armed gold book and e8_gold.session_probe own it"
    cls = _class_refusal(meta["symbol"])
    if cls:
        return cls
    if not _fill_hour(row.get("spread_basis")):
        return (f"spread_basis {row.get('spread_basis')!r} is not the fill-hour spread: the "
                f"record is not priced at the hour it fills")
    ban = _banned(meta["family"])
    if ban:
        return f"banned family: {ban}"
    return None


# ----------------------------------------------------------------------------- tuning
def tune(tuning: Mapping[str, Any], history: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """New {t_in, alpha, why} from the scored outcomes. Pure. Each knob moves one step at a time
    inside its declared range, toward whichever error cost the book more growth."""
    t_in = min(max(_num(tuning.get("t_in"), T_IN_DEFAULT), T_IN_RANGE[0]), T_IN_RANGE[1])
    alpha = min(max(_num(tuning.get("alpha"), ALPHA_DEFAULT), ALPHA_RANGE[0]), ALPHA_RANGE[1])
    rows = list(history)[-TUNE_HISTORY:]
    why: list[str] = []
    dem = [h for h in rows if h.get("kind") == "demote"]
    if len(dem) >= TUNE_MIN_OUTCOMES:
        false_cost = sum(max(0.0, _num(h.get("forgone_r"))) for h in dem)
        late_cost = sum(max(0.0, _num(h.get("late_r"))) for h in dem)
        if false_cost > 1.2 * late_cost:
            alpha = max(ALPHA_RANGE[0], alpha * 0.8)
            why.append(f"false demotes forwent {false_cost:.2f}R > late demotes lost "
                       f"{late_cost:.2f}R: alpha down to {alpha:.4f} (demote less readily)")
        elif late_cost > 1.2 * false_cost:
            alpha = min(ALPHA_RANGE[1], alpha * 1.25)
            why.append(f"late demotes lost {late_cost:.2f}R > false demotes forwent "
                       f"{false_cost:.2f}R: alpha up to {alpha:.4f} (demote sooner)")
    adm = [h for h in rows if h.get("kind") == "admit"]
    if len(adm) >= TUNE_MIN_OUTCOMES:
        marginal = [h for h in adm if _num(h.get("t_at_admit")) < t_in + 0.5]
        if len(marginal) >= TUNE_MIN_OUTCOMES:
            post = sum(_num(h.get("post_r")) for h in marginal)
            if post < 0:
                t_in = min(T_IN_RANGE[1], t_in + 0.1)
                why.append(f"marginal admits lost {post:.2f}R after admission: T_IN up to "
                           f"{t_in:.2f}")
            elif post > 0:
                t_in = max(T_IN_RANGE[0], t_in - 0.05)
                why.append(f"marginal admits earned {post:.2f}R after admission: T_IN down to "
                           f"{t_in:.2f} (admit more)")
    return {"t_in": round(t_in, 4), "alpha": round(alpha, 6),
            "why": "; ".join(why) or "no knob moved (too few scored outcomes or balanced)"}


# ----------------------------------------------------------------------------- the pass
def step(shadow: Mapping[str, Any], state: Mapping[str, Any], *, now: datetime,
         identities: Mapping[str, Mapping[str, Any]] | None = None,
         off: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """(artifact, new state, ledger events) for one pass. Pure."""
    stamp = now.astimezone(UTC).isoformat(timespec="seconds")
    prev_rows: dict[str, dict[str, Any]] = {
        str(k): dict(v) for k, v in (state.get("rows") or {}).items() if isinstance(v, Mapping)}
    history = [dict(h) for h in (state.get("history") or []) if isinstance(h, Mapping)]
    tuning = tune(state.get("tuning") or {}, history)
    a_bound, b_bound = bounds(tuning["alpha"])
    events: list[dict[str, Any]] = []
    ids = identities or {}
    rows_out: dict[str, dict[str, Any]] = {}

    clocks = {str(k): v for k, v in shadow.items() if isinstance(v, Mapping)}
    metas = {k: parse_key(k, ids.get(k)) for k in clocks}
    verdict = {k: eligible(k, clocks[k], metas[k], tuning["t_in"]) for k in clocks}
    if off:
        verdict = dict.fromkeys(clocks, "PROBE_TIER_OFF present")

    # 1. HELD ROWS FIRST: a live row is judged by its own test; a demoted row by its re-admit test.
    for key, prev in prev_rows.items():
        row = clocks.get(key)
        rec = dict(prev)
        if row is None:
            if rec.get("status") == "LIVE":
                rec.update(status="DEMOTED", demoted_at=stamp, demote_why="clock vanished",
                           nd=0, cumd=0.0)
                events.append({"at": stamp, "event": "demote", "key": key,
                               "why": "clock vanished from shadow_state"})
            rows_out[key] = rec
            continue
        n, s = _num(row.get("n")), _num(row.get("cum_r"))
        if rec.get("status") == "LIVE":
            post_n, post_s = n - _num(rec.get("n0")), s - _num(rec.get("cum0"))
            if post_n < 0:        # the engine replayed a shorter record: re-anchor, never credit
                rec.update(n0=n, cum0=s)
                post_n, post_s = 0.0, 0.0
            llr = sprt_llr(post_n, post_s, _num(rec.get("mu0"), MU0_FLOOR),
                           _num(rec.get("sigma"), 1.0))
            rec.update(post_n=int(post_n), post_r=round(post_s, 4), llr=round(llr, 4))
            hard = None
            st = str(row.get("status") or "").upper()
            if off:
                hard = "PROBE_TIER_OFF present"
            elif st not in LIVE_CLOCK_STATUSES:
                hard = f"clock status {row.get('status')!r}"
            else:
                cls = _class_refusal(metas[key]["symbol"])
                if cls:
                    hard = cls
            if hard or llr >= a_bound:
                why = hard or (f"SPRT: LLR {llr:.2f} >= {a_bound:.2f} on {int(post_n)} live "
                               f"trades summing {post_s:+.2f}R vs H0 mean "
                               f"{_num(rec.get('mu0')):.3f}R")
                rec.update(status="DEMOTED", demoted_at=stamp, demote_why=why, nd=n, cumd=s,
                           late_r=round(max(0.0, -post_s), 4),
                           demotes=int(_num(rec.get("demotes"))) + 1, outcome_open=True)
                events.append({"at": stamp, "event": "demote", "key": key, "why": why,
                               "post_n": int(post_n), "post_r": round(post_s, 4),
                               "statistical": hard is None})
        elif rec.get("status") == "DEMOTED":
            dn, ds = n - _num(rec.get("nd")), s - _num(rec.get("cumd"))
            if dn < 0:
                rec.update(nd=n, cumd=s)
                dn, ds = 0.0, 0.0
            rec.update(since_demote_n=int(dn), since_demote_r=round(ds, 4))
            if rec.get("outcome_open") and dn >= OUTCOME_N:
                out = {"kind": "demote", "key": key, "at": stamp,
                       "forgone_r": round(ds, 4), "late_r": _num(rec.get("late_r")),
                       "false_demote": ds > 0}
                history.append(out)
                events.append({"at": stamp, "event": "outcome", **out})
                rec["outcome_open"] = False
            llr_d = sprt_llr(dn, ds, _num(rec.get("mu0"), MU0_FLOOR), _num(rec.get("sigma"), 1.0))
            rec["llr_since_demote"] = round(llr_d, 4)
            if dn >= READMIT_MIN_N and llr_d <= b_bound and verdict.get(key) is None:
                rec.update(status="READMIT_PENDING")
        if rec.get("status") == "LIVE" and rec.get("admit_outcome_open"):
            if _num(rec.get("post_n")) >= OUTCOME_N:
                out = {"kind": "admit", "key": key, "at": stamp,
                       "t_at_admit": _num(rec.get("t_at_admit")),
                       "post_r": _num(rec.get("post_r"))}
                history.append(out)
                events.append({"at": stamp, "event": "outcome", **out})
                rec["admit_outcome_open"] = False
        rows_out[key] = rec

    # 2. ONE BET PER MEASURED CO-MOVE GROUP, over the rows that are live or may become live.
    def _held(k: str) -> str:
        return str((rows_out.get(k) or {}).get("status") or "")

    pool = {k: clocks[k] for k in clocks
            if _held(k) in ("LIVE", "READMIT_PENDING")
            or (verdict.get(k) is None and _held(k) != "DEMOTED")}
    aliases: dict[str, str] = {}
    for grp in comove_groups(pool):
        live_members = [k for k in grp if (rows_out.get(k) or {}).get("status") == "LIVE"]
        if live_members:
            rep = sorted(live_members)[0]
        else:
            rep = max(grp, key=lambda k: (_num(clocks[k].get("forward_t")),
                                          _num(clocks[k].get("n")), k))
        for k in grp:
            if k != rep:
                aliases[k] = rep

    # A LIVE row that now measures as the same bet as another live row stops trading: the
    # group trades once. Not a statistical demote, so it is never scored as a false one.
    for key, rep in aliases.items():
        rec = rows_out.get(key) or {}
        if rec.get("status") == "LIVE":
            row = clocks[key]
            why = f"co-moves with live {rep}: one bet, traded once"
            rec.update(status="DEMOTED", demoted_at=stamp, demote_why=why,
                       nd=_num(row.get("n")), cumd=_num(row.get("cum_r")),
                       outcome_open=False, admit_outcome_open=False)
            events.append({"at": stamp, "event": "demote", "key": key, "why": why,
                           "statistical": False})

    # 3. ADMIT / RE-ADMIT the representatives.
    for key in sorted(pool):
        rec = rows_out.get(key) or {}
        if rec.get("status") == "LIVE" or key in aliases or verdict.get(key) is not None:
            if rec.get("status") == "READMIT_PENDING" and (key in aliases
                                                           or verdict.get(key) is not None):
                rec["status"] = "DEMOTED"
            continue
        if rec.get("status") == "DEMOTED":
            continue
        row = clocks[key]
        readmit = rec.get("status") == "READMIT_PENDING"
        n, s = _num(row.get("n")), _num(row.get("cum_r"))
        exp0 = _num(row.get("exp_r"), s / n if n else 0.0)
        rec.update(status="LIVE", admitted_at=stamp, n0=n, cum0=s, exp0=round(exp0, 6),
                   mu0=round(max(MU0_FRAC * exp0, MU0_FLOOR), 6),
                   sigma=round(sigma_of(row), 6),
                   t_at_admit=_num(row.get("forward_t")), post_n=0, post_r=0.0, llr=0.0,
                   admit_outcome_open=True, admits=int(_num(rec.get("admits"))) + 1)
        rows_out[key] = rec
        events.append({"at": stamp, "event": "readmit" if readmit else "admit", "key": key,
                       "n": int(n), "cum_r": round(s, 4),
                       "forward_t": row.get("forward_t"), "mu0": rec["mu0"],
                       "sigma": rec["sigma"]})
    for rec in rows_out.values():
        if rec.get("status") == "READMIT_PENDING":
            rec["status"] = "DEMOTED"

    live: dict[str, dict[str, Any]] = {}
    demoted: dict[str, dict[str, Any]] = {}
    for key, rec in sorted(rows_out.items()):
        row = clocks.get(key) or {}
        meta = metas.get(key) or parse_key(key)
        n = _num(row.get("n"))
        ident = ids.get(key) or {}
        view = {**meta, "column": column_of(meta), "n": int(n),
                "params": dict(ident.get("params") or {}) if ident else None,
                "side": str(ident.get("side") or "") or None,
                "forward_t": row.get("forward_t"), "exp_r": row.get("exp_r"),
                "shrink": round(shrink(n), 6), "admitted_at": rec.get("admitted_at"),
                "post_n": rec.get("post_n"), "post_r": rec.get("post_r"), "llr": rec.get("llr"),
                "aliases": sorted(k for k, r in aliases.items() if r == key)}
        if rec.get("status") == "LIVE":
            live[key] = view
        elif rec.get("status") == "DEMOTED":
            demoted[key] = {**view, "demoted_at": rec.get("demoted_at"),
                            "why": rec.get("demote_why"),
                            "since_demote_n": rec.get("since_demote_n"),
                            "since_demote_r": rec.get("since_demote_r")}
    refused: dict[str, int] = {}
    for k, why in verdict.items():
        if why and k not in rows_out:
            head = why.split(":")[0].split(" ")[0] if why else ""
            refused[head] = refused.get(head, 0) + 1
    artifact = {
        "generated_at": stamp, "off": bool(off),
        "rule": ("probe = lane ceiling x n/(n+%d); SPRT H0 mean %.2f x exp_r at admission vs "
                 "H1 mean 0; demote -> forward only; re-admit on H0 accepted since demotion"
                 % (PROBE_SHRINK_N0, MU0_FRAC)),
        "tuning": {**tuning, "beta": BETA, "demote_llr": round(a_bound, 4),
                   "readmit_llr": round(b_bound, 4)},
        "n_live": len(live), "n_demoted": len(demoted), "n_aliases": len(aliases),
        "live": live, "demoted": demoted, "aliases": aliases, "refused": refused,
        "missed_growth": {k: {"rail": "probe_shrink", "shrink": v["shrink"],
                              "forgone_share_of_ceiling": round(1.0 - v["shrink"], 6)}
                          for k, v in live.items()},
    }
    new_state = {"updated_at": stamp, "tuning": {"t_in": tuning["t_in"],
                                                 "alpha": tuning["alpha"]},
                 "rows": rows_out, "history": history[-TUNE_HISTORY * 4:]}
    if tuning["why"].startswith(("false", "late", "marginal")):
        events.append({"at": stamp, "event": "tune", **tuning})
    return artifact, new_state, events


# ----------------------------------------------------------------------------- I/O
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def run(shadow: Mapping[str, Any] | None = None, *, now: datetime | None = None,
        identities: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """One pass: read, step, write the artifact, the state and the ledger. Returns the artifact.
    An unreadable state starts a fresh one (nothing is live until admitted again); an unreadable
    shadow file admits nothing and demotes nothing (UNMEASURED)."""
    now = now or datetime.now(UTC)
    if shadow is None:
        shadow = _read_json(SHADOW)
    if not isinstance(shadow, Mapping):
        doc = {"generated_at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
               "why": f"{SHADOW.name} unreadable", "live": {}, "demoted": {}}
        _atomic(OUT, doc)
        return doc
    state = _read_json(STATE)
    artifact, new_state, events = step(shadow, state if isinstance(state, Mapping) else {},
                                       now=now, identities=identities, off=OFF.exists())
    _atomic(STATE, new_state)
    _atomic(OUT, artifact)
    if events:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e, default=str) + "\n")
    return artifact


def load_live(path: Path | None = None, now: datetime | None = None
              ) -> tuple[dict[str, dict[str, Any]], str]:
    """({key: live view}, why) from a FRESH artifact, else ({}, why). For the prop books."""
    p = path or OUT
    doc = _read_json(p)
    if not isinstance(doc, Mapping):
        return {}, f"{p.name} absent or unreadable"
    try:
        at = datetime.fromisoformat(str(doc["generated_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return {}, f"{p.name} undated"
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = ((now or datetime.now(UTC)) - at).total_seconds()
    if not -60 <= age <= MAX_AGE_S:
        return {}, f"{p.name} is {age / 3600:.1f}h old"
    live = doc.get("live")
    if not isinstance(live, Mapping):
        return {}, f"{p.name} carries no live block"
    return {str(k): dict(v) for k, v in live.items() if isinstance(v, Mapping)}, \
        f"{p.name} {age:.0f}s old: {len(live)} live probe(s)"


def main() -> int:
    doc = run()
    print(json.dumps({k: doc.get(k) for k in ("generated_at", "n_live", "n_demoted",
                                              "n_aliases", "tuning", "refused")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
