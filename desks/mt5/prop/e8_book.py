"""WHICH 24 SLEEVES THE E8 ACCOUNT TRADES, chosen from the certified survivors this venue lists.

Not a new hunt and not a new certificate. Every row here already holds a ten-gate universal
certificate; this file only decides which of them the E8 lane runs, and refuses the ones the
venue cannot fill.

THREE FILTERS, IN THIS ORDER, and the order is the point:

  1. THE VENUE MUST LIST IT. E8's catalogue is 46 instruments with no Scandi or EM crosses, so
     ten of the sixty-one certificates are unfillable here -- and they are the ten best by
     expected value, including `carry`'s only certificate (CHFNOK, ev 0.5929). An order on an
     instrument the venue does not list is not a small trade, it is a rejected one.
  2. DIVERSITY BEFORE EXPECTANCY. Taking the top 24 by ev would take 24 `discovered` rows,
     because `discovered` is 33 of the 51 survivors. The pass probability of this account is
     driven by how many INDEPENDENT bets it holds, not by the mean of their expectancies, so the
     selection round-robins across mechanisms and only then ranks within one.
  3. ONE ROW PER (mechanism, symbol). Two certificates on the same mechanism and the same
     instrument are one bet with two names -- exactly the breadth illusion `orthogonality.py`
     measures, bought on purpose.

SIZE IS NOT CHOSEN HERE. `RISK_FRAC` is the principal's decision recorded in docs/PROP_FIRM_E8.md
and re-derived under TAIL-implied correlation, and the executor reads it from this module so
there is one number in one place.

Artifact: desks/mt5/reports/E8_BOOK.json
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CERT_BOOK = DESK / "data" / "CERT_BOOK_LIVE.json"


def _private_lineage(val: Any) -> bool:
    """libs.ops.token_refresh.has_private_lineage: True when a survivor (its spec, gates or any
    nested source list) carries the private-use lineage `jquants_private` / `e8_ineligible`.
    An unreadable helper reads as private for any row that names the tag in its text, so a
    missing import can never let such a row through."""
    try:
        from libs.ops.token_refresh import has_private_lineage
        return bool(has_private_lineage(val))
    except Exception:
        text = json.dumps(val, default=str)
        return "jquants_private" in text or '"e8_ineligible": true' in text


def _family_banned(family: str) -> bool:
    """research/family_policy.family_banned, reached from this lane's own path; an unreadable
    policy reads as nothing banned, the same way the policy module itself reads it."""
    try:
        if str(DESK / "research") not in sys.path:
            sys.path.insert(0, str(DESK / "research"))
        from family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False
OUT = DESK / "reports" / "E8_BOOK.json"

#: The last catalogue the venue actually reported. Written whenever the live call succeeds, read
#: when it does not. A prop venue's instrument list changes on the order of months; a connection
#: fails on the order of minutes, and the desk must not lose rule 1 for the length of an outage.
CATALOGUE_CACHE = DESK / "data" / "e8_catalogue.json"


def _cache_catalogue(keys: set[str]) -> None:
    """Remember what the venue lists, so an outage costs freshness and not the rule."""
    try:
        CATALOGUE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CATALOGUE_CACHE.write_text(json.dumps({
            "measured_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "n": len(keys),
            "instruments": sorted(keys),
        }, indent=1), encoding="utf-8")
    except OSError:
        pass


def _cached_catalogue() -> set[str] | None:
    """The last measured catalogue, or None. None is 'I do not know', never 'no restriction'."""
    try:
        doc = json.loads(CATALOGUE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("instruments")
    if not isinstance(rows, list) or not rows:
        return None
    return {str(r) for r in rows}

#: HOW MANY SLEEVES, and it is a breadth decision rather than a taste one. Every certified sleeve
#: fires in the asia window, so the whole book lands at once into a 2.5% daily floor; widening the
#: book at a smaller per-sleeve size is what raises pass probability, and 24 x 0.05% keeps gross
#: simultaneous exposure at 1.2% -- under half the daily wall, before any stand-down.
MAX_SLEEVES = 24

#: RISK PER TRADE, as a fraction of the $100,000 initial balance. 0.15%, i.e. $150.
#:
#: RAISED FROM 0.05% ON 2026-09-14, on the principal's decision, against a measured sweep of the
#: real barrier -- `research/prop_barrier.py` over 4,000 paths per cell at the book actually
#: fielded (24 sleeves, rr 1.5, 0.64 trades per sleeve per day) and expectancy NET of cost at
#: +0.135R, which is the honest reading of the desk's +0.20 gross replay figure.
#:
#: WHAT 0.05% WAS COSTING, at tail-implied rho 0.58:
#:
#:     risk     P(pass)   median days   p90
#:     0.050%    99.6%         91       146
#:     0.075%   100.0%         61       106
#:     0.100%    99.9%         45        87
#:     0.125%    98.2%         37        74      <- here
#:     0.150%    88.3%         31        65
#:     0.200%    47.4%         20        37
#:
#: Fifty-four days bought one and a half points of pass probability. That is not a conservative
#: trade, it is an expensive one: E8 publishes no time limit on Pro, but every extra day is a day
#: of daily-floor exposure that the 2.5% rule can end, so a slower pass is not a monotonically
#: safer pass. The earlier 0.05% reading compared 0.05% against 0.07% only, where the difference
#: really was 96.3% against 84.0%; it never priced the speed being given up, because the sweep it
#: cited did not report days.
#:
#: WHY NOT FURTHER. Above 0.15% the curve falls off a cliff -- 47.4% at 0.20% -- because this
#: account truncates the right tail at +2% a day and leaves the left free to -2.5%. The pass-
#: optimal size is therefore well below the growth-optimal one, and 0.125% is the last point
#: where P(pass) is still near the ceiling while the median more than halves.
#:
#: This is an INCREASE in size and that is deliberate (growth governance Rule 2: a strong
#: opportunity must be allowed more capital when the evidence supports it). Nothing here lowers
#: any limit on the live MT5 book, which solves a different problem on a different venue --
#: `mt5desk/account_profile.py` is where that line is drawn.
#:
#: RAISED AGAIN TO 0.15% THE SAME NIGHT, once the venue's spreads were measured LIVE rather than
#: over a closed weekend. The first sample had every symbol frozen (min == max == median across
#: 11 draws); with the session open the same instruments quote EURUSD 0.431 bps and XAUUSD 1.175,
#: which on a 20-pip stop is a haircut of ~0.025R, not the ~0.065R the cost note assumed. Net
#: expectancy is therefore nearer +0.175 than +0.135 and the whole curve shifts.
#:
#: THE BINDING CONSTRAINT IS THE DAILY FLOOR, NOT THE STATIC ONE. At net +0.175, rho 0.58:
#:
#:     risk     P(pass)   median   p_fail_daily   worst_dd_p90
#:     0.125%    99.9%      35          0.1%          2.75%
#:     0.150%    98.3%      30          1.6%          3.30%     <- here
#:     0.175%    91.7%      26          8.0%          3.76%
#:     0.200%    78.0%      22         21.9%          3.90%
#:
#: Between 0.15% and 0.175% the daily-breach probability QUINTUPLES to buy four days. Worst
#: drawdown at p90 is 3.3% against a 10% static floor, so the $90,000 line is not what ends these
#: accounts -- the 2.5% daily one is.
#:
#: AND IT IS THE LAST SIZE THAT SURVIVES BEING WRONG. Across net +0.175 / +0.135 / +0.100:
#:     0.125%  ->  99.9 / 99.6 / 98.5
#:     0.150%  ->  98.3 / 97.1 / 93.6
#:     0.175%  ->  91.7 / 87.6 / 79.6
#: 0.175% collapses on the pessimistic leg; 0.15% does not. `rho` 0.58 is TAIL-IMPLIED and has
#: never been measured on live fills (`matched_fills` is still 0), and correlation error is what
#: larger size punishes hardest -- which is the whole reason the ceiling is here and not higher.
RISK_FRAC = 0.0015


def _load_survivors() -> list[dict[str, Any]]:
    doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key, val in (doc.get("survivors") or {}).items():
        spec = val.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or val.get("sym") or "").upper()
        fam = str(spec.get("family") or "")
        if not sym or not fam:
            continue
        # A BANNED FAMILY IS NOT IN THE E8 BOOK EITHER (2026-09-16): the same policy file the
        # MT5 roster reads; the executor closes what such a sleeve still holds.
        if _family_banned(fam):
            continue
        rows.append({
            "key": key, "symbol": sym, "family": fam,
            "selector": spec.get("selector") or "asia",
            "fingerprint": _spec_fingerprint(spec),
            "params": {k: v for k, v in spec.items()
                       if k not in ("symbol", "family", "selector", "is_universe", "hunt")},
            "ev": ((val.get("gates") or {}).get("expected_value") or {}).get("ev"),
            # THE COST-STRESSED EXPECTANCY IS WHAT THE GROWTH SCORE RANKS ON, not `ev`.
            # `stress_costs.exp_x3` is the same cell replayed at THREE TIMES the modelled cost,
            # and it is the gate that separates the yen crosses from each other: CADJPY falls
            # 0.1631 -> 0.0624 (a 62% haircut) where USDJPY falls 0.1586 -> 0.0798 (48%), so on
            # raw `ev` they are a dead heat and on cost robustness they are not close.
            "exp_x3": ((val.get("gates") or {}).get("stress_costs") or {}).get("exp_x3"),
            "lockbox": ((val.get("gates") or {}).get("lockbox") or {}).get("lockbox_sharpe"),
            "days": val.get("days"),
            "n_trials": ((val.get("gates") or {}).get("deflated_sharpe") or {}).get("n_trials"),
            "tier_s": _is_tier_s((val.get("gates") or {}).get("deflated_sharpe") or {}),
            # PRIVATE-USE LINEAGE IS NEVER IN THE E8 BOOK (coordinator ruling, 2026-10-07).
            # J-Quants is permitted for the registered individual's private use only; E8 trades
            # the prop firm's capital, so a cell derived from it is e8_ineligible. Fusion (the
            # individual's own account) is unaffected. `select` names the refusal.
            "private_lineage": _private_lineage(val),
        })
    return rows


def _spec_fingerprint(spec: dict[str, Any]) -> str:
    from admission_integrity import spec_fingerprint
    return spec_fingerprint(spec.get("symbol"), spec.get("family"),
                            spec.get("selector"), spec.get("side"), spec.get("params"))


#: ZEROS IN THE E8 PRINCIPAL BOOK THAT THE PRINCIPAL HAS SINCE LIFTED (zuck 2026-11-19 12:15Z: "all
#: the strategies [should] flow into [E8] ... because we want both accounts to pass with high
#: probability and speed"). They were written by the 2026-10-20 21:52Z order "trade only gold asia"
#: and its 17:02Z companion ("USDJPY, NZDJPY and AUDCHF stay at 0.0"), which the 11-19 order
#: replaces. CERT_BOOK_LIVE.json is box state (libs/ops/release.STATE_PREFIXES), so an origin edit
#: of its e8 block would be reverted by the box's next push; the lift is therefore read here, in
#: one place both readers use (this book and prop/e8_executor).
#: 2026-11-24 (principal 18:31Z "I removed the e8 gold only rule ages ago", 18:34Z "no blockers for
#: anything. Only exotics"): gold_london_am and gold_afternoon -- the gold-only order's own two
#: zeros -- and USDJPY_session_range_breakout_asia (its Reddit-lineage quarantine went with the
#: 2026-11-13 reddit_origin_lift) are lifted too. One set, in decision_core, read by every door.
from mt5desk.decision_core import SUPERSEDED_CERT_ZEROS  # noqa: E402

SUPERSEDED_E8_ZEROS: frozenset[str] = SUPERSEDED_CERT_ZEROS["e8"]
#: Principal exclusions the principal has since lifted (the box's CERT_BOOK_LIVE `excluded` still
#: names USDJPY's Reddit-lineage quarantine). Exotic exclusions need none: exotics are refused.
SUPERSEDED_EXCLUSIONS: frozenset[str] = frozenset({"USDJPY_session_range_breakout_asia"})


#: FAMILIES HELD AT ZERO UNTIL THEY HOLD UP FORWARD (Judge forward calibration 2026-11-19,
#: reports/judging/FORWARD_CALIBRATION_2026-11-19.md; coordinator 17:00Z; zuck 17:02Z "all of them
#: ... through allocator" = every PROMOTABLE strategy, certified AND holding forward). Over 798
#: certified clocks with 30+ days and 10+ forward trades, these families kept their edge on 14-41%
#: of clocks at a negative trade-weighted mean R (cross_asset_residual 24% / -0.237R,
#: macro_conditional 14% / -0.192R, carry 41% / -0.180R, pca_residual 33% / -0.086R), most likely
#: from look-ahead in their outside-data joins. The price-only families held 95-100%. A family
#: leaves this set when the Judge's point-in-time fix lands and its forward hit rate holds; the
#: refusal is billed by name in E8_BOOK.json. REVERT: empty this set.
FORWARD_FAILING_FAMILIES: frozenset[str] = frozenset({
    "cross_asset_residual", "macro_conditional", "carry", "pca_residual"})


#: FILL-PROVEN SLEEVES (Box read 2026-11-19 19:05Z, reports/hourly_pass/FILL_PROVEN_READ.md): the
#: sleeve's own forward trades, re-priced at the measured ask-bid for its symbol and entry hour,
#: outside the 00:00-01:59 broker rollover slice. Written box-side each pass as
#: {"sleeves": [{"sleeve": "SYM_family_selector", "n_out": int, "adjR_out": float}, ...]}
#: (research/fill_proven.py, hourly leg "fill_proven"; `sleeve` is the forward ledger's label).
#: A sleeve's OWN fill evidence outranks its family's average: a fill-proven sleeve of a
#: forward-failing family is admitted, and every admitted sleeve is sized by how much evidence
#: it has (`fill_shrink`). Absent or unreadable: no sleeve is fill-proven (fail closed).
FILL_PROVEN = DESK / "reports" / "FILL_PROVEN.json"
FILL_PROVEN_SCHEMA = "fill-proven/1"
#: STALE FAILS CLOSED (Audit HOLD 2026-11-19 19:41Z): the organ is an hourly leg, so a file
#: older than three missed passes means the organ stopped and its verdicts no longer describe
#: today's fills. Past this bound no sleeve is fill-proven. The wrong schema, a missing or
#: unparseable generated_at, or one in the future reads the same way.
FILL_PROVEN_MAX_AGE_H = 3.0
FILL_MIN_N = 10
#: Shrinkage prior, in trades: a sleeve with n fill-proven trades is sized at n / (n + N0) of
#: RISK_FRAC, so a 15-trade edge trades at ~23% of full size and a 500-trade one at ~91%.
FILL_SHRINK_N0 = 50


def load_fill_proven(path: Path | None = None,
                     now: datetime | None = None) -> dict[str, dict[str, float]]:
    """{sleeve: {"n": n_out, "adjR": adjR_out}} for sleeves positive after spread outside the
    rollover slice with at least FILL_MIN_N trades; {} when the artifact is absent, of another
    schema, undated, future-dated or older than FILL_PROVEN_MAX_AGE_H (fail closed)."""
    try:
        doc = json.loads((path or FILL_PROVEN).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("schema") != FILL_PROVEN_SCHEMA:
        return {}
    try:
        gen = datetime.fromisoformat(str(doc["generated_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return {}
    if gen.tzinfo is None:
        return {}
    age_h = ((now or datetime.now(UTC)) - gen).total_seconds() / 3600.0
    if not 0.0 <= age_h <= FILL_PROVEN_MAX_AGE_H:
        return {}
    return {k: v for k, v in _fill_records(doc).items() if v["adjR"] > 0}


def _fill_records(doc: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    rows = doc.get("sleeves") or []
    for r in rows if isinstance(rows, list) else []:
        try:
            n, adj = int(r["n_out"]), float(r["adjR_out"])
        except (KeyError, TypeError, ValueError):
            continue
        if n >= FILL_MIN_N:
            out[str(r["sleeve"])] = {"n": float(n), "adjR": adj}
    return out


def load_fill_losers(path: Path | None = None,
                     now: datetime | None = None) -> dict[str, dict[str, float]]:
    """The other half of FILL_PROVEN.json: sleeves with n >= FILL_MIN_N whose after-spread record
    is NOT positive. They are not refused (no blockers but exotics); `evidence_mult` sizes them
    at a quarter of the certificate prior so their own fills keep deciding. Same freshness
    fence as `load_fill_proven`; {} when it fails."""
    doc = _fresh_doc(path, now)
    return {k: v for k, v in _fill_records(doc).items() if v["adjR"] <= 0} if doc else {}


def _fresh_doc(path: Path | None, now: datetime | None) -> dict[str, Any] | None:
    try:
        doc = json.loads((path or FILL_PROVEN).read_text(encoding="utf-8-sig"))
        gen = datetime.fromisoformat(str(doc["generated_at"]).replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if not isinstance(doc, dict) or doc.get("schema") != FILL_PROVEN_SCHEMA or gen.tzinfo is None:
        return None
    age_h = ((now or datetime.now(UTC)) - gen).total_seconds() / 3600.0
    return doc if 0.0 <= age_h <= FILL_PROVEN_MAX_AGE_H else None


def fill_shrink(n: float) -> float:
    return n / (n + FILL_SHRINK_N0) if n > 0 else 0.0


#: NO BLOCKERS BUT EXOTICS (principal 2026-11-24 18:34Z: "make sure all promoted strategies get to
#: EA and FTMO, and the rule never intervenes or anything, no blockers for anything. Only exotics
#: are blocked"). What used to REFUSE a promoted sleeve now SIZES it: a sleeve with no fill record
#: yet trades at the size its certificate is worth as a prior of CERT_PRIOR_N trades (10/(10+50) =
#: 1/6 of RISK_FRAC), half that when its family fails forward, and a sleeve whose live rebuild did
#: not replicate, or that trades under a placebo alarm, is halved again rather than stood aside.
#: Its own fills then grow or shrink it through `fill_shrink` like every other sleeve. The firm's
#: rails (daily and maximum loss, the profit cap) and survival sizing are untouched and still bind
#: the whole book. Exotics stay refused (`is_exotic_pair`).
CERT_PRIOR_N = 10
DOUBT_MULT = 0.5
#: Structured doubt codes (Audit should-fix 4 on 9dc6bbfe4): a door that already priced a doubt
#: writes its code on the row (`doubt_codes`) and the next door never charges it twice.
DOUBT_PLACEBO, DOUBT_REPLICATION, DOUBT_TIER_S = "placebo_alarm", "replication", "tier_s_door"
#: The reopen judge (research/real_edge.py) lists the certificate and does not verify it: a doubt
#: that SIZES the sleeve, never refuses it (Audit MF2 on #1211; zuck 2026-11-24 18:34Z).
DOUBT_REAL_EDGE = "real_edge_unverified"
_MAJORS = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD"})


def is_exotic_pair(symbol: object) -> bool:
    """A six-letter FX pair with a leg outside the eight majors (mt5desk.live_policy.is_exotic,
    restated so the prop lanes refuse exotics even where that module is older). Metals, indices,
    energy and crypto are never exotic."""
    try:
        from mt5desk.live_policy import is_exotic
        return bool(is_exotic(symbol))
    except ImportError:
        s = str(symbol or "").upper()[:6]
        a, b = s[:3], s[3:6]
        return (len(s) == 6 and s.isalpha() and not s.startswith(("XAU", "XAG", "XPT", "XPD"))
                and not (a in _MAJORS and b in _MAJORS) and (a in _MAJORS or b in _MAJORS))


def evidence_mult(proven: Mapping[str, float] | None, family: str,
                  doubts: Sequence[str] = (),
                  losing: Mapping[str, float] | None = None) -> tuple[float, list[str]]:
    """(size multiplier on RISK_FRAC, why) for a promoted sleeve. Pure. Never zero."""
    notes: list[str] = []
    if proven:
        m = fill_shrink(float(proven["n"]))
    elif losing:
        m = fill_shrink(float(CERT_PRIOR_N)) * DOUBT_MULT * DOUBT_MULT
        notes.append(f"own fills not positive after costs (n={int(losing['n'])}, adjR="
                     f"{losing['adjR']:+.3f}): x{DOUBT_MULT * DOUBT_MULT} of the prior")
    else:
        m = fill_shrink(float(CERT_PRIOR_N))
        notes.append(f"no fill record yet: certificate prior of {CERT_PRIOR_N} trades")
        if family in FORWARD_FAILING_FAMILIES:
            m *= DOUBT_MULT
            notes.append(f"{family} fails forward as a family: x{DOUBT_MULT}")
    for d in doubts:
        m *= DOUBT_MULT
        notes.append(f"{d}: x{DOUBT_MULT}")
    return m, notes
#: THE ONE ALLOCATOR'S E8 BOOK (research/prop_challenge_allocator.py --venue e8, hourly).
E8_ALLOCATOR = DESK / "reports" / "E8_ALLOCATOR.json"
E8_ALLOCATOR_MAX_AGE_S = 2 * 3600


def _e8_ceiling() -> float:
    """E8's per-sleeve risk ceiling (mt5desk.decision_core.E8_CERT_CEILING, the executor's cap);
    0.006 if that module cannot be read, so the clip never loosens on an import failure."""
    try:
        from mt5desk.decision_core import E8_CERT_CEILING
        return float(min(E8_CERT_CEILING, 0.006))
    except Exception:
        return 0.006


def e8_solved_book(path: Path | None = None, now: datetime | None = None
                   ) -> tuple[dict[str, float], str]:
    """{column: equity fraction} for EVERY column E8's solve priced (0.0 where it chose not to
    fund), or ({}, why) when the solve is absent, stale, not deployable or malformed."""
    p = path or E8_ALLOCATOR
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}, f"{p.name} absent or unreadable: evidence rule"
    if not isinstance(doc, dict) or doc.get("venue") != "e8":
        return {}, f"{p.name} is not an E8 solve: evidence rule"
    if doc.get("deployable") is not True:
        return {}, f"{p.name} not deployable ({doc.get('status')}): evidence rule"
    try:
        at = datetime.fromisoformat(str(doc["generated_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return {}, f"{p.name} undated: evidence rule"
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = ((now or datetime.now(UTC)) - at).total_seconds()
    if not 0 <= age <= E8_ALLOCATOR_MAX_AGE_S:
        return {}, f"{p.name} is {age / 3600:.1f}h old: evidence rule"
    cols, ex = doc.get("solved_columns"), doc.get("executable")
    if not isinstance(cols, list) or not isinstance(ex, dict):
        return {}, f"{p.name} carries no solved_columns/executable: evidence rule"
    ceiling = _e8_ceiling()
    out: dict[str, float] = {}
    for c in cols:
        v = ex.get(c, 0.0)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out[str(c)] = float(min(max(v, 0.0), ceiling))
    return out, f"{p.name} {age:.0f}s old: {sum(1 for v in out.values() if v > 0)} funded"


def apply_solved(chosen: list[dict[str, Any]], solved: Mapping[str, float]
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Size each chosen row by the solve where it priced the row's column; drop the rows it
    zeroed (sovereignty: zero sends no order). Returns (kept rows, zeroed columns)."""
    ceiling = _e8_ceiling()
    zeroed: list[dict[str, Any]] = []
    for r in chosen:
        col = f"{r['symbol']}_{r['family']}_{r.get('selector') or 'asia'}"
        if col in solved and r.get("principal_funded"):
            # THE PRINCIPAL'S NUMBER STANDS (Audit MF-3 on eb3134ee2): a principal-funded key is
            # sized by the principal; the solve's view is journaled beside it, never applied.
            r["solve_risk_frac"] = round(float(solved[col]), 6)
            continue
        if col in solved:
            before = float(r.get("risk_frac") or 0.0)
            frac = min(float(solved[col]), ceiling)
            # THE DOUBTS STAY PRICED (Audit MF-2/MF-2b): the solve prices returns, not a placebo
            # alarm, a replication miss or thin fills. A row the admission door sized by
            # `evidence_mult` is capped at that multiple of E8's per-sleeve ceiling
            # (E8_CERT_CEILING, the executor's own cap), so the solve can never lift a doubted
            # sleeve to the full ceiling.
            if "evidence_mult" in r:
                cap = float(r["evidence_mult"]) * ceiling
                if frac > cap:
                    r["evidence_capped_from"] = round(frac, 6)
                    frac = cap
            r["risk_frac"] = round(frac, 6)
            r["risk_source"] = "one allocator (E8_ALLOCATOR.json)"
            if solved[col] <= 0:
                # A SOLVE ZERO IS SIZING, AND VISIBLE (Audit should-fix 1): the risk the evidence
                # rule would have carried is its missed-growth line.
                zeroed.append({"column": col, "missed_growth_risk_frac": round(before, 6),
                               "rail": "e8_one_allocator_zero"})
    return [r for r in chosen if r["risk_frac"] > 0], zeroed


#: TIER S IS A SIZE MULTIPLIER, NOT A GATE (zuck 2026-11-19 19:23Z: "ur bigger size one is the
#: right approach not block"). A certificate whose deflated Sharpe passed at or over DSR_BAR
#: carries the stronger statistical evidence, so its fill-proven size is raised by this factor;
#: the executor's E8_CERT_CEILING and the worst-day stress cap still bound the result.
TIER_S_DSR_BAR = 0.95
TIER_S_MULT = 1.5


def _is_tier_s(gate: Mapping[str, Any]) -> bool:
    dsr = gate.get("dsr")
    return gate.get("passed") is True and isinstance(dsr, (int, float)) and dsr >= TIER_S_DSR_BAR


def sleeve_risk(row: Mapping[str, Any]) -> float:
    """RISK_FRAC x n/(n+N0) for the sleeve's fill-proven depth, x TIER_S_MULT when Tier S. A
    sleeve admitted on a principal-funded key alone (no fill record) keeps RISK_FRAC."""
    fp = row.get("fill_proven")
    if "evidence_mult" in row:
        base = RISK_FRAC * float(row["evidence_mult"])
    else:
        base = RISK_FRAC * fill_shrink(float(fp["n"])) if fp else RISK_FRAC
    return round(base * (TIER_S_MULT if row.get("tier_s") else 1.0), 6)


#: THE ROLLOVER ENTRY GATE (coordinator + hourly pass 2026-11-19 19:24Z, zuck "fix all so all is
#: ready to reach live"). A fill-proven sleeve's evidence EXCLUDES broker 00:00-01:59 -- the slice
#: where spreads run 10-1000x and the bid-only record was flattering it -- so the sleeve may not
#: enter there: its edge was never shown in that slice. A principal-funded key with no fill record
#: is the principal's and is not gated here. The executor bills each refusal as missed growth.
ROLLOVER_BROKER_HOURS = frozenset({0, 1})


def rollover_block(row: Mapping[str, Any], now_utc: datetime) -> str | None:
    """The reason this sleeve may not enter now, or None. Broker hour = UTC + E8 server offset."""
    if not row.get("fill_proven"):
        return None
    from prop.e8_guard import server_offset_hours
    hour = (now_utc.astimezone(UTC).hour + server_offset_hours(now_utc)) % 24
    if hour in ROLLOVER_BROKER_HOURS:
        return (f"broker hour {hour:02d} is in the rollover slice its fill evidence excludes "
                "(reports/FILL_PROVEN.json, outside 00:00-01:59 only)")
    return None


#: The allocator's rollover-artefact rule (research/pf_allocator.rollover_artefact, Audit CLEAR
#: 83be0b74b3) restated for the E8 fallback, which must not depend on that module loading: a
#: row whose recorded `entry_hours` ({broker hour: count}, read as broker hours only when
#: `entry_hours_venue` names an MT5 feed) put >= ROLLOVER_SHARE of >= ROLLOVER_MIN_N entries in
#: broker 00:00-01:59 is a bid-bar rollover artefact. Absent or foreign data is UNMEASURED and
#: charges nothing.
ROLLOVER_SHARE = 0.80
ROLLOVER_MIN_N = 5


def fallback_rollover_artefact(row: Mapping[str, Any]) -> str | None:
    """Why this row is a rollover artefact, or None (including when unmeasured). Never raises."""
    try:
        venue = str(row.get("entry_hours_venue") or "").strip().lower()
        hours = row.get("entry_hours")
        if not venue.startswith("mt5:") or not isinstance(hours, Mapping):
            return None
        counts = {int(h): int(n) for h, n in hours.items() if int(n) > 0}
        total = sum(counts.values())
        roll = sum(n for h, n in counts.items() if h in ROLLOVER_BROKER_HOURS)
    except (TypeError, ValueError):
        return None
    if total < ROLLOVER_MIN_N or roll < ROLLOVER_SHARE * total:
        return None
    return (f"{roll} of {total} recorded entries at broker 00:00-01:59: a rollover artefact "
            f"(no deployable solve to price it)")


def fallback_filter(chosen: list[dict[str, Any]]
                    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(kept, dropped) for the evidence-rule fallback (no deployable solve): only fill-proven or
    principal-funded rows, and no fill-proven row that is a rollover artefact. Each drop carries
    its missed-growth line. Pure."""
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for r in chosen:
        col = f"{r['symbol']}_{r['family']}_{r.get('selector') or 'asia'}"
        why = None
        if not (r.get("fill_proven") or r.get("principal_funded")):
            why = "no deployable solve, and no fill record or principal funding"
        elif not r.get("principal_funded"):
            why = fallback_rollover_artefact(r)
        if why:
            dropped.append({"column": col, "why": why,
                            "missed_growth_risk_frac": float(r.get("risk_frac") or 0.0),
                            "rail": "e8_fallback_unproven"})
            continue
        kept.append(r)
    return kept, dropped


def principal_e8_book(raw: Mapping[str, Any] | None) -> dict[str, float]:
    """The E8 principal book as it stands today: the cert block, less the zeros the principal
    lifted. A positive value sizes its key; an explicit zero is the principal's pause; a key the
    block does not name is sized by the book's RISK_FRAC."""
    out: dict[str, float] = {}
    for k, v in (raw or {}).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if k in SUPERSEDED_E8_ZEROS and not v > 0:
            continue
        out[str(k)] = float(v)
    return out


def live_admissible(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Apply the existing replication and principal exclusion doors before ranking E8 risk."""
    from admission_integrity import IntegrityGate, REPLICATED
    from kelly_survival import terms_fenced_cells

    config = json.loads(CERT_BOOK.read_text(encoding="utf-8"))
    excluded = config.get("excluded") if isinstance(config, dict) else None
    if not isinstance(excluded, dict):
        raise ValueError("CERT_BOOK_LIVE.json has no principal exclusion map")
    from mt5desk.kelly_sizing import load_cert_book
    from mt5desk.live_policy import exit_parity_refusal
    principal_book = principal_e8_book(load_cert_book(CERT_BOOK, "e8"))
    proven = load_fill_proven()
    losers = load_fill_losers()
    fenced, source = terms_fenced_cells()
    gate = IntegrityGate.load()
    # THE REOPEN JUDGE (research/real_edge.py) PRICES, IT NEVER REFUSES: a certificate it lists
    # unverified carries doubt code DOUBT_REAL_EDGE and is sized x DOUBT_MULT; a verified one is
    # marked `real_edge_verified`. A verdict that cannot be read changes nothing.
    import real_edge
    edges, _edges_status = real_edge.load()
    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for row in rows:
        key = str(row["key"])
        sym, fam, selector = str(row["symbol"]), str(row["family"]), str(row["selector"])
        book_key = f"{sym}_{fam}_{selector}"
        reason = ""
        doubts: list[str] = []
        codes: list[str] = []
        # EVERY PROMOTED SLEEVE FLOWS INTO E8 AND FTMO; ONLY EXOTICS ARE BLOCKED (zuck 2026-11-19
        # 12:15Z, 2026-11-24 18:34Z). An explicit zero the principal wrote in the book and his
        # named exclusions still stand (his own words, per sleeve); the terms fence stands (the
        # data's own licence). Fill evidence, forward-failing families, replication and the
        # placebo alarm SIZE the sleeve (`evidence_mult`) and never refuse it.
        # EXIT-POLICY LIVE PARITY (Audit HOLD MF1 on #628): a certificate earned with an exit the
        # live executors cannot run is a research trial, never an E8 sleeve. Named, never silent.
        parity = exit_parity_refusal(row)
        if is_exotic_pair(sym):
            reason = "exotic FX pair: exotics are banned (principal 2026-11-24 18:04Z)"
        elif parity:
            reason = parity
        elif book_key in principal_book and not principal_book[book_key] > 0:
            reason = "principal zero in the E8 principal book"
        elif book_key in excluded and book_key not in SUPERSEDED_EXCLUSIONS:
            reason = f"principal exclusion: {excluded[book_key]}"
        elif f"{sym}.{fam}" in fenced:
            reason = f"terms-fenced input data ({source})"
        else:
            if gate.alarm.get("blocks"):
                doubts.append(f"placebo alarm ({gate.alarm.get('why') or 'placebo gate'})")
                codes.append(DOUBT_PLACEBO)
            verdict, why = gate.replication(key, str(row.get("fingerprint") or ""))
            if verdict != REPLICATED:
                doubts.append(f"replication {verdict}: {why}")
                codes.append(DOUBT_REPLICATION)
            edge_doubt = real_edge.doubt(key, edges)
            if edge_doubt:
                doubts.append(edge_doubt)
                codes.append(DOUBT_REAL_EDGE)
            elif real_edge.verified(key, edges):
                row = {**row, "real_edge_verified": True}
        if reason:
            blocked.append({"certificate": key, "why": reason})
        else:
            if book_key in proven:
                row = {**row, "fill_proven": proven[book_key]}
            if codes:
                row = {**row, "doubt_codes": codes}
            if principal_book.get(book_key, 0) > 0:
                # The principal's own number sizes it; a doubt is journaled, never applied.
                row = {**row, "principal_funded": True}
                if doubts:
                    row = {**row, "evidence_notes": [f"{d} (journaled; principal-funded)"
                                                     for d in doubts]}
            else:
                mult, notes = evidence_mult(proven.get(book_key), fam, doubts,
                                             losers.get(book_key))
                row = {**row, "evidence_mult": round(mult, 6), "evidence_notes": notes}
            accepted.append(row)
    return accepted, blocked


#: Instruments that share a leg move together, so they are one bet wearing several names.
#: MEASURED (principal, 2026-09-24): EURJPY against GBPJPY is +0.891, and the four yen crosses
#: together are worth barely two independent bets; XAUUSD against the same block is -0.117, which
#: is why gold plus ONE yen cross is diversification and gold plus four is not.
#:
#: ONLY THE YEN BLOCK IS LISTED, AND THAT IS THE POINT. The book also holds three CHF crosses on
#: `overnight_gap_decay` (GBPCHF, AUDCHF, CADCHF) which are very likely the same story -- but the
#: desk has MEASURED the yen correlation and has not measured that one, and a block cut on an
#: assumed correlation would be exactly the un-evidenced shrink Growth Governance Rule 1 refuses.
#: It is published in the report as `unmeasured_blocks` instead, so it is visible rather than
#: quietly acted on. Add a block here when its correlation is measured, never before.
CORRELATED_BLOCKS: dict[str, str] = {"JPY": "JPY"}


def block_of(symbol: str) -> str | None:
    """The correlation block `symbol` belongs to, or None when it is in no MEASURED block."""
    sym = symbol.upper()
    for leg, name in CORRELATED_BLOCKS.items():
        # The leg must be one of the two sides of a 6-character FX pair, not a substring of a
        # longer instrument name, or an index whose ticker happens to contain the letters would
        # be swept into a currency block it has nothing to do with.
        if len(sym) == 6 and leg in (sym[:3], sym[3:]):
            return name
    return None


#: Per-cell measured distribution: n, win_rate, exp_r, profit_factor, max_dd_r for every
#: (symbol, family, params) the external backtest ran. ~2,100 trades per cell.
BACKTEST = DESK / "data" / "hypotheses" / "external_backtest_results.json"


def _measured() -> dict[tuple[str, str, float, float], dict[str, Any]]:
    """(symbol, family, rr, wait_bars) -> the backtest's measured summary for that cell."""
    try:
        doc = json.loads(BACKTEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(doc, dict):
        doc = doc.get("results") or doc.get("rows") or list(doc.values())
    out: dict[tuple[str, str, float, float], dict[str, Any]] = {}
    for r in doc if isinstance(doc, list) else []:
        if not isinstance(r, dict):
            continue
        prm = r.get("params") or {}
        rr, wb = prm.get("rr"), prm.get("wait_bars")
        if rr is None or wb is None:
            continue
        try:
            k = (str(r.get("symbol") or "").upper(), str(r.get("family") or ""),
                 float(rr), float(wb))
        except (TypeError, ValueError):
            continue
        out[k] = r
    return out


def growth_score(row: Mapping[str, Any], risk_frac: float = 0.0) -> float | None:
    """E[log W] per trade for this certificate at `risk_frac`, or None if it cannot be derived.

    WHY NOT `ev` (principal, 2026-09-24): "add best MAXIMUM GROWTH yen one". Mean R and log-wealth
    growth rank differently, because log punishes a drawdown harder than it rewards the same-sized
    gain -- so a cell can carry the better mean R and compound more slowly.

    THE PAYOFF IS MEASURED, NOT ASSUMED, AND THE FIRST VERSION OF THIS FUNCTION ASSUMED IT WRONG.
    It modelled a `session_range_breakout` position as resolving at its rr target or its -1R stop
    and backed the win rate out as (e + 1) / (rr + 1), which put USDJPY rr=2.0 at 36.0%. The
    shadow ledgers refute that: every row exits on `reason: "ttl"`, at whatever R the clock finds,
    and the measured win rate is 53.7%. So the distribution is fitted to THREE measured moments
    from `external_backtest_results.json` -- win_rate, exp_r and profit_factor -- which determines
    a two-point payoff exactly:

        (1-p) * mean_loss = exp_r / (PF - 1)        p * mean_win = PF * exp_r / (PF - 1)

    then scaled to the cell's 3x-cost-stressed expectancy, because the cost charged against these
    cells has been corrected repeatedly and the stressed number is the one that survives being
    wrong again. Growth is  p*ln(1 + f*mean_win) + (1-p)*ln(1 - f*mean_loss).

    Returns None rather than a guess whenever any input is missing: absence is never scored as
    zero, which would silently rank an unmeasured cell last instead of leaving it unjudged.
    """
    f = risk_frac or RISK_FRAC
    prm = (row.get("params") or {}).get("params") or {}
    rr, wb = prm.get("rr"), prm.get("wait_bars")
    e3, ev = row.get("exp_x3"), row.get("ev")
    if rr is None or wb is None or e3 is None or not ev or not (0.0 < f < 1.0):
        return None
    try:
        m = _measured().get((str(row.get("symbol") or "").upper(), str(row.get("family") or ""),
                             float(rr), float(wb)))
    except (TypeError, ValueError):
        return None
    if not m:
        return None
    p, exp_r, pf = m.get("win_rate"), m.get("exp_r"), m.get("profit_factor")
    if p is None or exp_r is None or pf is None:
        return None
    p, exp_r, pf = float(p), float(exp_r), float(pf)
    if not (0.0 < p < 1.0) or pf <= 1.0 or exp_r <= 0:
        return None
    mean_loss = (exp_r / (pf - 1.0)) / (1.0 - p)
    mean_win = (pf * exp_r / (pf - 1.0)) / p
    # Charge the cost stress to the win side: a cost is paid on every trade, so a heavier cost
    # shows up as a smaller average win against an unchanged stop.
    mean_win -= (1.0 - float(e3) / float(ev)) * exp_r / p
    if mean_win <= 0 or f * mean_loss >= 1.0:
        return None
    return p * math.log(1.0 + f * mean_win) + (1.0 - p) * math.log(1.0 - f * mean_loss)


def select(tradeable: set[str] | None = None, max_sleeves: int = MAX_SLEEVES,
           rows: list[dict[str, Any]] | None = None,
           days: tuple[list[str], Any] | None = None) -> dict[str, Any]:
    """The book, plus everything refused and why. An absence here is always named (L1.28a)."""
    rows = _load_survivors() if rows is None else rows
    blocked = []
    private_refused = []
    live = []
    for r in rows:
        if r.get("private_lineage"):
            private_refused.append({"key": r["key"], "symbol": r["symbol"],
                                    "family": r["family"],
                                    "why": "private-use lineage (jquants_private): e8_ineligible, "
                                           "the prop firm's capital is not the registered "
                                           "individual's own money"})
        elif tradeable is not None and r["symbol"] not in tradeable:
            blocked.append({**r, "why": "not listed by the venue"})
        else:
            live.append(r)

    # one row per (mechanism, symbol): the best ev wins, the rest are named as duplicates
    # THE CHART IS PART OF THE IDENTITY (fixed 2026-09-14).
    #
    # This keyed on (mechanism, symbol) alone, so a session_range_breakout on M15 and its H1
    # sibling were ONE row and the later one was discarded as a duplicate. That was correct while
    # H1 was the only chart the desk collected -- two certificates differing in nothing but a
    # parameter hash really are one bet with two names -- and it becomes wrong the moment the
    # collector writes M30/M15/M5/M1: an M15 breakout reads different bars, sets a different stop
    # and fills at different times from the H1 one.
    #
    # IT WOULD HAVE CANCELLED THE DIVERSITY IT WAS MEANT TO ENFORCE, silently. The measured case
    # for collecting intraday at all is that rho falls from 0.58 toward ~0.29 as charts are added,
    # which on the barrier is worth four days AND takes daily-breach risk from 1.8% to 1.1%.
    # Collapsing the charts back into one row would have kept the book at 20 H1 sleeves while the
    # report cheerfully counted the rest as duplicates.
    #
    # A DIFFERENT CHART IS NOT A FULLY INDEPENDENT BET and this does not pretend otherwise: the
    # round-robin below still spreads across MECHANISMS first, so charts of one family can only
    # fill slots the other mechanisms have not claimed. The chart widens the identity; it does not
    # promote a family.
    def _tf(row: dict[str, Any]) -> str:
        return str((row.get("params") or {}).get("timeframe") or "H1").upper()

    # WITHIN A (mechanism, symbol, chart), GROWTH PICKS THE SURVIVOR, not `ev`.
    #
    # THIS ORDERING IS LOAD-BEARING AND IT SILENTLY PICKED THE WRONG CELL WHEN IT RANKED ON `ev`.
    # USDJPY's highest-`ev` certificate is the UNSUFFIXED `external.USDJPY.session_range_breakout`
    # (0.1641), which records no rr and no wait_bars -- so it cannot be scored for growth at all,
    # and it is a weaker identity besides (the gateway's own note: "PARAMS ARE PART OF THE
    # IDENTITY. Without them the spec says only 'XAUUSD asia'"). Taking it here left USDJPY
    # unscorable, so the correlation rule below could not rank it, and the JPY slot went to
    # EURJPY -- the third-best cross by growth -- while the best one was discarded as a duplicate.
    # Ranking on growth makes the parameterised rr=2.5 cell the survivor and the order comes out
    # right. `ev` remains the tiebreak so a family with no measured distribution is still ordered.
    def _rank(r: dict[str, Any]) -> tuple[float, float]:
        g = growth_score(r)
        return (-9.0 if g is None else g, r["ev"] or -9)

    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    dupes = []
    for r in sorted(live, key=lambda x: (-_rank(x)[0], -_rank(x)[1])):
        k = (r["family"], r["symbol"], _tf(r))
        if k in best:
            dupes.append({**r, "why": f"duplicate of {best[k]['key']} "
                                      "on the same mechanism+symbol+chart"})
            continue
        best[k] = r

    # ONE ROW PER (mechanism, CORRELATION BLOCK), and the survivor is chosen on GROWTH.
    #
    # Rule 3 above ("one row per mechanism+symbol") catches two certificates on the same
    # instrument. It does not catch four DIFFERENT instruments that are the same bet: measured
    # 2026-09-24, this book held USDJPY, CADJPY, EURJPY and GBPJPY on `session_range_breakout`
    # at once, and EURJPY against GBPJPY is +0.891. That is four of eight slots spent on about
    # two independent bets, on an account whose pass probability is driven by how many
    # INDEPENDENT bets it holds -- the exact failure `orthogonality.py` measures and the reason
    # the principal's order was "add ONE yen cross, not all four".
    #
    # IT DOES SHRINK NOMINAL GROSS, AND THAT IS REPORTED RATHER THAN DRESSED UP. The round-robin
    # below is CERTIFICATE-limited, not slot-limited -- the book fills 6-8 of its 24 slots because
    # that is how many distinct certificates the venue lists, so dropping three rows frees three
    # slots that nothing refills. Measured here: n_selected 8 -> 6 and gross 1.20% -> 0.90%.
    #
    # WHAT IS NOT LOST IS THE PART THAT WAS DOING WORK. At the measured rho of 0.891,
    # `libs/validation/effective_sample.cross_dependence_deflator(4, 0.891) = 0.273`, so the four
    # yen rows were carrying about 1.09 independent bets between them; one row carries 1.00. The
    # book gives up 25% of its NOMINAL exposure to give up 8% of its EFFECTIVE breadth.
    #
    # THIS IS THE PRINCIPAL'S OWN INSTRUCTION ("add ONE yen cross, not all four", 2026-09-24),
    # the same class of act as the `discovered` family ban -- not a session lowering risk by fiat,
    # which the standing order forbids. Redeploying the freed 0.30% is a change to `RISK_FRAC`,
    # which is the principal's decision recorded in docs/PROP_FIRM_E8.md and is NOT touched here.
    blocked_by_corr = []
    per_block: dict[tuple[str, str], dict[str, Any]] = {}
    survivors: list[dict[str, Any]] = []
    for r in best.values():
        blk = block_of(r["symbol"])
        if blk is None:
            survivors.append(r)
            continue
        k2 = (r["family"], blk)
        held = per_block.get(k2)
        if held is None:
            per_block[k2] = r
            continue
        # Growth decides, and a cell that cannot be scored never displaces one that can.
        g_new, g_held = growth_score(r), growth_score(held)
        if g_new is not None and (g_held is None or g_new > g_held):
            per_block[k2] = r
            blocked_by_corr.append({**held, "why": f"{blk} block already represented on "
                                                   f"{r['family']} by {r['key']} (higher growth)"})
        else:
            blocked_by_corr.append({**r, "why": f"{blk} block already represented on "
                                                f"{r['family']} by {held['key']} (higher growth)"})
    survivors.extend(per_block.values())

    # round-robin across mechanisms, best-first within each
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for r in survivors:
        by_fam.setdefault(r["family"], []).append(r)
    for fam in by_fam:
        by_fam[fam].sort(key=lambda x: -(x["ev"] or -9))
    chosen: list[dict[str, Any]] = []
    i = 0
    while len(chosen) < max_sleeves:
        took = False
        for fam in sorted(by_fam, key=lambda f: -len(by_fam[f])):
            if i < len(by_fam[fam]) and len(chosen) < max_sleeves:
                chosen.append(by_fam[fam][i])
                took = True
        if not took:
            break
        i += 1

    # THE WORST HISTORICAL DAY, WITH CORRELATIONS, UNDER 60% OF THE 2.5% DAILY LIMIT
    # (prop/stress.py;
    # CIO review 2026-11-19 move #1). E8's gold lane trades on the same account, so its size is
    # counted on every day and never cut; the sleeve book gives way, weakest-of-the-worst-family
    # first, and every cut is a missed-growth line.
    from prop import stress
    from prop.e8_guard import DAILY_DRAWDOWN
    if days is None:
        days = stress.load_days()
    try:
        from mt5desk.kelly_sizing import load_cert_book
        gold = principal_e8_book(load_cert_book(CERT_BOOK, "e8")).get("gold_asia", 0.0)
    except Exception:
        gold = 0.0
    # SIZE BY EVIDENCE (`sleeve_risk`): fill-proven depth, then Tier S as a multiplier.
    for r in chosen:
        r["risk_frac"] = sleeve_risk(r)
        r["risk_source"] = "evidence rule (sleeve_risk)"
    # THEN BY THE ONE ALLOCATOR (one-pipe step 1): where E8's own solve priced the sleeve, its
    # fraction IS the size -- larger or smaller than the evidence rule, and zero sends no order
    # (ALLOCATOR SOVEREIGNTY). A sleeve the solve did not price keeps the evidence rule; a stale,
    # undeployable or unreadable solve changes nothing. The stress cap below still binds.
    solved, solved_why = e8_solved_book()
    chosen, zeroed = apply_solved(chosen, solved)
    # THE FALLBACK ADMITS ONLY WHAT IS PROVEN (Audit gate (b), 2026-11-26). With no deployable
    # solve, a survivors row with no fill record used to carry the full evidence-rule size, and
    # the allocator's rollover zero vanished with the solve. Now only a fill-proven or a
    # principal-funded row trades in fallback, and a row whose recorded entries sit >= 80% in
    # broker 00:00-01:59 is a recorded zero (fallback_rollover_artefact). Each drop is billed.
    fallback_dropped: list[dict[str, Any]] = []
    if not solved:
        chosen, fallback_dropped = fallback_filter(chosen)
    stressed = stress.cap_book(
        chosen, risk_of=lambda r: r["risk_frac"], family_of=lambda r: r["family"],
        daily_limit=DAILY_DRAWDOWN, days=days,
        col_of=lambda r: f"{r['symbol']}_{r['family']}_{r.get('selector') or 'asia'}",
        fixed={"gold_asia": gold},
        set_risk=lambda r, v: r.update(risk_frac=float(v), risk_source=(
            f"{r.get('risk_source')}; scaled by the stress cap")))
    chosen = stressed.pop("kept")

    fams: dict[str, int] = {}
    for r in chosen:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    evs = [r["ev"] for r in chosen if r["ev"] is not None]
    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "risk_frac": RISK_FRAC,
        "max_sleeves": max_sleeves,
        "n_certified": len(rows),
        "n_tradeable": len(live),
        "n_blocked_by_venue": len(blocked),
        "n_refused_private_lineage": len(private_refused),
        "refused_private_lineage": private_refused,
        "n_duplicate_mechanism_symbol": len(dupes),
        "n_blocked_by_correlation": len(blocked_by_corr),
        "blocked_by_correlation": blocked_by_corr,
        #: Concentrations this rule can SEE but has not measured, so has not acted on (L1.28a:
        #: unmeasured is a verdict, not a zero). Published so the next correlation measurement
        #: has a named target rather than being rediscovered.
        "unmeasured_blocks": sorted({
            f"{fam}:{leg}" for fam, leg in {
                (r["family"], r["symbol"][3:]) for r in chosen if len(r["symbol"]) == 6}
            if block_of("XXX" + leg) is None
            and sum(1 for x in chosen
                    if x["family"] == fam and len(x["symbol"]) == 6 and x["symbol"][3:] == leg) > 1
        }),
        "by_chart": {tf: sum(1 for x in chosen if str((x.get("params") or {}).get(
            "timeframe") or "H1").upper() == tf)
            for tf in sorted({str((x.get("params") or {}).get("timeframe") or "H1").upper()
                              for x in chosen})},
        "n_selected": len(chosen),
        "gross_exposure_if_all_fire": round(len(chosen) * RISK_FRAC, 5),
        "by_mechanism": fams,
        "stress": stressed,
        "allocator": {"source": solved_why, "n_priced": len(solved),
                      "zeroed_by_allocator": zeroed,
                      "fallback_dropped": fallback_dropped},
        "mean_ev": None if not evs else round(sum(evs) / len(evs), 4),
        "sleeves": chosen,
        "blocked_by_venue": sorted({r["symbol"] for r in blocked}),
        "rule": ("venue-listed first, then diversity across mechanisms, then expectancy within "
                 "one; one row per (mechanism, symbol) because two certificates on the same "
                 "mechanism and instrument are one bet with two names"),
    }


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-live-venue", action="store_true",
                    help="do NOT ask the venue what it lists. The book is then written only if a "
                         "previously measured catalogue is on disk; with neither, nothing is "
                         "written, because an unfiltered book is not a safer book.")
    args = ap.parse_args(argv)

    # RULE 1 OF THIS FILE WAS OPTIONAL, AND OFF BY DEFAULT (fixed 2026-09-14).
    #
    # The docstring's first selection rule is THE VENUE MUST LIST IT. The implementation asked
    # for the catalogue only under `--live-venue`, and the scheduled task runs
    # `python e8_book.py` with no arguments -- so `tradeable` was None, `select()` reads None as
    # "apply no filter", and the rule that leads the file was never applied on any scheduled
    # pass. `n_blocked_by_venue` then published 0, which is not "nothing was blocked" but "I did
    # not look".
    #
    # MEASURED ON THE LIVE $100k ACCOUNT TONIGHT: of the 24 sleeves in the book, EIGHT were Scandi
    # and EM crosses -- EURNOK, CHFNOK, GBPMXN and siblings -- that E8's 46-instrument catalogue
    # does not carry. The executor caught every one and refused it as NOT_LISTED, so no bad order
    # was sent; the cost was worse than an error. A third of the book's slots were spent on
    # instruments that cannot trade, on an account whose pass probability is a function of how
    # many INDEPENDENT mechanisms are actually running, with a five-day hard speed floor and a
    # right tail that is confiscated at 2% a day. Those eight slots were unavailable to the
    # certified sleeves that E8 does list.
    #
    # ABSENCE IS NOT PERMISSION (LAWS). `None` meaning "no filter" is that violation in one
    # sentinel: the failure to measure and the decision not to restrict were the same value.
    # They are now different values and the failure fails CLOSED.
    tradeable: set[str] | None = None
    source = ""
    if not args.no_live_venue:
        try:
            from prop.tradelocker_venue import TradeLockerVenue
            tradeable = set(TradeLockerVenue().connect()._by_key)
            source = f"live venue ({len(tradeable)} instruments)"
            _cache_catalogue(tradeable)
        except Exception as exc:
            print(f"live venue UNREACHABLE ({type(exc).__name__}: {exc}); falling back to the "
                  f"last measured catalogue")
    if tradeable is None:
        cached = _cached_catalogue()
        if cached:
            tradeable, source = cached, f"cached catalogue ({len(cached)} instruments)"

    if tradeable is None:
        # NOT AN ERROR TO SWALLOW. Writing an unfiltered book here would republish the exact
        # defect this fix removes, and silently: the artifact would look complete. Keeping the
        # last good book is the conservative act -- it was written when the catalogue WAS known.
        print("REFUSING to write the book: the venue's catalogue is unknown and no cached one "
              "exists, so rule 1 (the venue must list it) cannot be applied. The previous book "
              "stands.")
        return 1

    try:
        eligible, integrity_blocked = live_admissible(_load_survivors())
    except (OSError, ValueError, ImportError) as exc:
        print(f"REFUSING to write E8 book: integrity authority unavailable ({type(exc).__name__}: {exc})")
        return 1
    doc = select(tradeable, rows=eligible)
    doc["blocked_by_integrity"] = integrity_blocked
    doc["n_blocked_by_integrity"] = len(integrity_blocked)
    from kelly_survival import terms_fence_state
    doc["terms_fence"] = terms_fence_state()
    doc["catalogue_source"] = source
    write(doc)
    print(f"E8 book: {doc['n_selected']} sleeve(s) at {RISK_FRAC:.2%} "
          f"= {doc['gross_exposure_if_all_fire']:.2%} gross if every one fires")
    print(f"  catalogue: {source}")
    print(f"  by mechanism: {doc['by_mechanism']}")
    print(f"  mean ev {doc['mean_ev']} | {doc['n_blocked_by_venue']} blocked by the venue, "
          f"{doc['n_duplicate_mechanism_symbol']} duplicate (mechanism, symbol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
