"""LIVE DECAY MONITOR -- the demotion half of the one pipeline (principal 2026-08-26:
"add a decay monitor for live strats; if it decays way too much it gets replaced").

WHAT EXISTED BEFORE THIS FILE, AND WHY IT WAS NOT A MONITOR. meta_desk item 11 computes
RETIRE/FADE/OK flags into decay_state.json -- scheduled NOWHERE on either box, read by NOTHING.
A RETIRE flag that no organ consumes changes nothing on the book; under III.16 that is a decay
OPINION, not a decay monitor. It also needs 120 days of per-sleeve history, which a book whose
oldest live clock is days old cannot supply for years. This file is the wired organ: it reads the
live ledger the gateway already writes (every closed deal tagged with its sleeve), issues verdicts
under the SAME canonical thresholds promotion uses, and ACTS on them by editing data/sleeves.json
-- the exact file the gateway trades from.

ONE PIPELINE, MIRRORED (RESEARCH §6d/§6e). Promotion demands days >= 14 AND (n >= 50, or n >= 20
with forward t >= +2.5). Demotion uses the same arithmetic with the sign flipped:

  FADE   (risk halved)   n >= 20 and trailing t <= 0        -- the edge is statistically absent
                                                                at the same n the desk trusts for
                                                                promotion; half risk while the
                                                                question resolves.
  RETIRE (slot freed)    n >= 20 and trailing t <= -2.5     -- as much evidence of HARM as
                                                                promotion required of good.
         (hard rail)     trailing maxDD <= -25R, any n      -- the same DD bar every forward
                                                                verdict already applies; harm this
                                                                large does not wait for a t-test.

Below n=20 live trades there is NO statistical verdict either way (a verdict on a handful of
trades is a coin flip wearing a certificate) -- only the DD hard rail applies from trade one.

REPLACEMENT IS THE PIPELINE'S OWN JOB. A retired sleeve frees its slot; the daily promoter fills
slots from matured forward candidates the same day (same-day law, back half). Re-entry for the
retired sleeve is ONLY through a fresh forward window -- its certificate stands unless revoked,
so shadow re-enrols it automatically and it must re-earn live risk the same way it earned it
first. No instant re-arm, no bespoke second door back onto the book.

Wired into daily_cycle STEPS (shadow -> promoter -> markout -> decay -> export), so the decision
uses today's promoter output and today's closed trades. Artifact: data/decay_live.json every run;
actions append-only to data/decay_actions.jsonl. Absence of live sleeves is reported as the
number zero, never as silence (L1.28a).

THE MODEL HALF (audit P7 / P16, 2026-09-08). The demotion half above is lit and correct; what it
lacked was a MODEL: no per-sleeve half-life, no time-to-fade, and the allocator charging every
sleeve one blanket 30% decay probability (robust_elog.py:129). Replacement was reactive by
design -- a slot was refilled only AFTER a retirement, so the lead time was exactly zero.

  `fit_half_life`   a log-linear fit of each sleeve's trailing ROLLING expectancy against
                    calendar days: e(t) = e0 * exp(-lambda t). Published per sleeve as
                    `half_life_days` (ln 2 / lambda) and `t_to_fade_days` (days until the fitted
                    expectancy reaches FADE_FLOOR_R, the desk's own weak-edge bar). A series too
                    short, too brief, or without a positive expectancy to decay from is
                    UNMEASURED with its n -- never a number about noise.
  `successor_tasks` for every LIVE sleeve whose fitted half-life is under 2x the forward window
                    a successor still has to clear (FORWARD_BAR_DAYS), one `successor_hunt` task
                    keyed on the mechanism and symbol goes into the deepening queue, the way
                    alpha_breadth writes empty clusters. The search starts while the incumbent
                    still earns.

NEITHER MOVES A VERDICT. The FADE / RETIRE rules above are untouched and read nothing from the
model; the model is published for the allocator wave to consume as a per-sleeve decay_prob_i, so
a sleeve with a long fitted half-life can stop paying the blanket haircut. Nothing here retires,
fades, resizes or delays anything.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
SLEEVES_FILE = BASE / "data" / "sleeves.json"
from libs.ops.live_ledger_view import ledger_path as _audited_ledger_path
LEDGER = _audited_ledger_path(BASE / "data" / "live_ledger.jsonl")
OUT = BASE / "data" / "decay_live.json"
ACTIONS = BASE / "data" / "decay_actions.jsonl"
#: Names the gateway must close out on its next pass: a sleeve that leaves the roster leaves the
#: book (gateway.close_retired_positions reads and drains this).
CLOSE_QUEUE = BASE / "data" / "RETIRED_CLOSE_QUEUE.json"
#: THE DECAY ZERO FOR KEYS THAT TRADE OUTSIDE THE LIVE ROSTER (zuck 2026-10-29: "if a strat
#: starts decaying losing etc does our allocators notice n replace it"). Every live order since
#: the gold-only order of 2026-09-16 has gone out through a BOOK key (the principal's cert book,
#: the Fusion min-lot book, the gold windows), whose roster row is STANDBY or RETIRED -- so the
#: LIVE-only verdict loop below judged nothing, and the promoter's own retirement never touches
#: a RETIRED row. Measured: usdnok_carry_asia_p_ff35bb7, RETIRED on the roster since September,
#: closed 23 live trades in October for -9.36R and kept sending until a principal zero (#425).
#: This file names every key that TRADED in the trailing window and now fails the promoter's own
#: retirement bars on its live record; `decision_core.decay_zero` reads it and the gateway sends
#: nothing for a named key, with a missed-growth line. Rebuilt in full every pass.
DECAY_ZERO = BASE / "data" / "DECAY_ZERO.json"
#: promoter.RETIRE_MIN_N / RETIRE_MAX_DD / RETIRE_MIN_EXP and its roll-20 window, mirrored (the
#: promoter imports the terminal bindings; this organ runs without them). Pinned equal by
#: test_decay_traded_keys.py, so the two retirement doors can never disagree.
BOOK_RETIRE_MIN_N = 10
BOOK_RETIRE_MAX_DD = -25.0
BOOK_RETIRE_MIN_EXP = 0.05
BOOK_RETIRE_ROLL = 20
#: The forward clocks' own ledgers, the model's fallback series while the live ledger is thin:
#: a promoted sleeve's shadow clock keeps running (promoter.py never stops it), so its forward
#: rows are the longest untouched expectancy series the desk holds for that sleeve.
SHADOW_LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")

#: The promotion bar, mirrored. Change gate_spec.yaml, not this file, if the bar ever moves.
T_PROMOTE = 2.5
N_MIN_VERDICT = 20
#: The early-fade bar: trades before which no early verdict is read, and the per-trade loss that
#: reads as "doing bad" once it is reached.
EARLY_FADE_N = 5
EARLY_FADE_R = 0.25
#: The sleeve-name stem the ledger can carry: `gateway.COMMENT_MAX` (29, measured on the venue)
#: minus the "DW" tag. Mirrored, not imported: this organ runs without the terminal bindings.
LEDGER_NAME_MAX = 27
DD_HARD_R = -25.0
#: Trailing window: judge the sleeve the market currently sees, not its lifetime average.
TRAIL_DAYS = 45
TRAIL_MAX_TRADES = 60
FADE_FACTOR = 0.5
#: THE POOLED VERDICT (2026-09-16). A family is judged on ALL its live sleeves' trades together,
#: by asset class: pooled n at or above this and pooled t at or below the bar reads FADE for
#: every sleeve in the pool; it lifts only when the pooled t is back above zero (a band, so the
#: verdict does not flip hourly). Measured the day it was written: the `discovered` forex family
#: had 70 live closes at mean -0.16R, t about -2, spread over eleven sleeves with 3-8 trades each
#: -- every one of them below the per-sleeve bar, so the family bled at full size for a week
#: while each sleeve individually "had no statistical verdict either way".
POOL_FADE_N = 20
POOL_FADE_T = -1.5
#: THE POOLED RETIREMENT, on the same bar a sleeve retires on (t <= -T_PROMOTE at n >= 20):
#: as much evidence of harm as promotion required of good, read across the family. Measured
#: 2026-09-16: the `discovered` forex family stood at n=76, mean -0.23R, t=-4.5 -- past the bar
#: three times over -- while no single sleeve had the twenty trades to say so. Every live sleeve
#: of the pool leaves the roster (certificates stand; live risk is re-earned through a fresh
#: pre-registered forward window) and its open positions are queued for the gateway to close.
POOL_RETIRE_N = 20
POOL_RETIRE_T = -2.5

#: THE MODEL HALF's floors. Each is a refusal threshold for publishing a NUMBER, not a rule that
#: moves capital: below any of them the half-life is UNMEASURED with its n.
FIT_WINDOW = 5            # trades per rolling-expectancy point
MIN_FIT_TRADES = 10       # trailing trades before an expectancy series exists to fit
MIN_FIT_POINTS = 3        # positive rolling points a log-linear fit needs
MIN_FIT_SPAN_DAYS = 1.0   # calendar span those points must cover to fit a RATE against
#: The level `t_to_fade_days` is measured to: promoter.RETIRE_MIN_EXP, the desk's own weak-edge
#: bar (n >= 50 and exp < 0.05R retires). Mirrored, not imported: promoter imports the terminal
#: bindings and this organ must run without them. Pinned equal by test_decay_half_life.py.
FADE_FLOOR_R = 0.05
#: The forward window a successor still has to clear: shadow_forward.VERDICT_MIN_DAYS (14 days,
#: with the 50-trade bar beside it). A successor cannot carry capital sooner, so an incumbent
#: whose edge halves inside twice that window needs its successor search started NOW.
FORWARD_BAR_DAYS = 14
SUCCESSOR_HALF_LIFE_MULT = 2.0
#: Keys the trade timestamp may sit under, by ledger: the live ledger stamps `time`, the forward
#: ledgers `exit_time`/`entry_time`, the scalp lane `closed_at`/`opened_at`. The close is
#: preferred because the R is realised there.
_TIME_KEYS = ("time", "close_time", "exit_time", "closed_at", "entry_time", "opened_at")
_R_KEYS = ("r_multiple", "r", "R")


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(p: Path, doc: Any) -> None:
    """Write `doc` as JSON through a temp file and `os.replace`, so the gateway never reads a
    torn file (a torn DECAY_ZERO reads as no zeros, which is the pre-existing behaviour)."""
    import os
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=2), "utf-8")
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()


def sleeve_trades(name: str) -> list[dict]:
    """Trailing closed deals for one sleeve, oldest first."""
    if not LEDGER.exists():
        return []
    cutoff = datetime.now(tz=UTC) - timedelta(days=TRAIL_DAYS)
    rows = []
    for line in LEDGER.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        # THE LEDGER NAMES A SLEEVE BY ITS ORDER COMMENT, which the venue truncates to 29 chars
        # ("DW" + 27): a roster name longer than that never joined and was judged on zero trades
        # (L0346, join by derived identity). Match the roster name and its 27-char stem.
        if r.get("sleeve") not in (name, name[:LEDGER_NAME_MAX]) or "r_multiple" not in r:
            continue
        if not isinstance(r.get("r_multiple"), (int, float)):
            continue                                       # unreconstructible R: not a zero
        # THE GATEWAY WRITES AN UNMEASURED R AS THE NUMBER 0.0 (2026-09-30). Without an entry
        # and a stop, `decision_core.closed_trade_r` returns (0.0, 0.0) and `record_trades` stamps
        # the row `r_unreconstructible` -- so the isinstance check above let every such row in as
        # a real scratch trade. Rows written before the 2026-09-16 side fix carry the same
        # signature with no flag: `risk_quote` 0 beside `r_multiple` 0.0. Either way the trade's
        # R was never measured, and a run of them is the "constant +0.000" series that got
        # gold_asia's retirement voided as a computation defect. Unmeasured is skipped, not zero.
        if r.get("r_unreconstructible") is True:
            continue
        _rq = r.get("risk_quote")
        if isinstance(_rq, (int, float)) and _rq <= 0:
            continue
        try:
            ts = datetime.fromisoformat(str(r.get("time", "")).replace("Z", "+00:00"))
        except ValueError:
            ts = None
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts is None or ts >= cutoff:
            rows.append(r)
    return rows[-TRAIL_MAX_TRADES:]


def stats(rs: list[float]) -> dict:
    n = len(rs)
    out = {"n": n, "exp_r": 0.0, "t": 0.0, "max_dd_r": 0.0, "cum_r": 0.0, "wins": 0}
    if not n:
        return out
    cum, peak, dd = 0.0, 0.0, 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    mean = sum(rs) / n
    out.update({"exp_r": round(mean, 4), "cum_r": round(cum, 3), "max_dd_r": round(dd, 3),
                "wins": sum(1 for r in rs if r > 0)})
    if n >= 2:
        var = sum((x - mean) ** 2 for x in rs) / (n - 1)
        if var > 0:
            out["t"] = round(mean / ((var / n) ** 0.5), 3)
        elif mean != 0.0:
            # zero variance with a nonzero mean is the DEGENERATE certainty, not insignificance:
            # 25 identical losses is as significant as evidence gets, and t=0 here turned a
            # uniform loser into a FADE instead of a RETIRE in the ladder's own unit test.
            out["t"] = 99.0 if mean > 0 else -99.0
    return out


def verdict(s: dict) -> tuple[str, str]:
    if s["max_dd_r"] <= DD_HARD_R:
        return "RETIRE", (f"trailing maxDD {s['max_dd_r']}R breaches the {DD_HARD_R}R hard rail "
                          f"-- the same bar every forward verdict applies; harm this large does "
                          f"not wait for a t-test")
    # EARLY FADE (principal, 2026-09-16: "fade all the sleeves doing bad"). A sleeve that has not
    # won once in its first EARLY_FADE_N live trades (0-for-5: p = 0.6^5 = 8% under a 40%-win
    # edge), or is losing EARLY_FADE_R or more per
    # trade after that many, runs at half risk until its trailing record says otherwise. The
    # same FADE rail at an earlier bar, not a new rail: two-sided (the next HEALTHY reading
    # UNFADEs it), billed by missed_growth, and nothing retires here -- retirement keeps its
    # n and its t. Measured the day it was written: five EURCHF sleeves 0-for-27 between them
    # and an AUDCAD sleeve 0-for-8, every one sized at full risk because n < 20.
    if EARLY_FADE_N <= s["n"] < N_MIN_VERDICT and (
            int(s.get("wins", 0)) == 0 or s["exp_r"] <= -EARLY_FADE_R):
        return "FADE", (f"early fade: {s.get('wins', 0)} win(s) and exp={s['exp_r']}R over "
                        f"n={s['n']} (bar: n>={EARLY_FADE_N}, no wins or exp<=-{EARLY_FADE_R}R); "
                        f"half risk until the trailing record turns")
    if s["n"] < N_MIN_VERDICT:
        return "HEALTHY", f"{s['n']} trailing trade(s) < {N_MIN_VERDICT}: no statistical verdict either way; DD rail armed"
    if s["t"] <= -T_PROMOTE:
        return "RETIRE", (f"trailing t={s['t']} <= -{T_PROMOTE} over n={s['n']}: as much evidence "
                          f"of harm as promotion required of good")
    if s["t"] <= 0.0 or s["exp_r"] < 0.0:
        return "FADE", (f"trailing t={s['t']}, exp={s['exp_r']}R over n={s['n']}: the edge is "
                        f"statistically absent at the n the desk trusts for promotion; half risk "
                        f"while the question resolves")
    return "HEALTHY", f"trailing t={s['t']}, exp={s['exp_r']}R over n={s['n']}"


def pool_key(row: dict) -> str:
    """The pool a live sleeve is judged in with its siblings: family x asset class."""
    fam = str(row.get("family") or "?")
    sym = str(row.get("symbol") or "").upper()
    cls = "XAU" if sym.startswith("XAU") else "FX"
    return f"{fam}/{cls}"


def pooled_verdicts(live: dict[str, dict], trades: Any = None) -> dict[str, dict]:
    """Per pool: the pooled trailing stats, a verdict and the sleeves it applies to.

    FADE at n >= POOL_FADE_N and t <= POOL_FADE_T with a negative expectancy; HEALTHY once t is
    back above zero with a non-negative expectancy; HOLD in between (fades stand); UNMEASURED
    below the n. Never a RETIRE: a pool mixes sleeves, and retirement stays a per-sleeve verdict
    on a per-sleeve record.
    """
    fetch = trades or sleeve_trades
    groups: dict[str, list[str]] = {}
    for name, row in live.items():
        groups.setdefault(pool_key(row), []).append(name)
    out: dict[str, dict] = {}
    for key, names in sorted(groups.items()):
        rs: list[float] = []
        for n in names:
            rs.extend(float(t["r_multiple"]) for t in fetch(n))
        s = stats(rs)
        if s["n"] < POOL_FADE_N:
            v, why = "UNMEASURED", (f"pooled {key}: {s['n']} trailing trade(s) < {POOL_FADE_N} "
                                    f"across {len(names)} sleeve(s)")
        elif s["n"] >= POOL_RETIRE_N and s["t"] <= POOL_RETIRE_T and s["exp_r"] < 0.0:
            v, why = "RETIRE", (f"pooled {key}: t={s['t']} <= {POOL_RETIRE_T}, exp={s['exp_r']}R "
                                f"over n={s['n']} across {len(names)} sleeve(s): as much "
                                f"evidence of harm as promotion required of good; every live "
                                f"sleeve of the pool leaves the roster and its positions are "
                                f"closed; certificates stand and live risk is re-earned through "
                                f"a fresh pre-registered forward window")
        elif s["t"] <= POOL_FADE_T and s["exp_r"] < 0.0:
            v, why = "FADE", (f"pooled {key}: t={s['t']}, exp={s['exp_r']}R over n={s['n']} "
                              f"across {len(names)} sleeve(s): the family is losing where no "
                              f"single sleeve has the trades to say so; half risk on all of "
                              f"them until the pooled record turns (t > 0)")
        elif s["t"] > 0.0 and s["exp_r"] >= 0.0:
            v, why = "HEALTHY", f"pooled {key}: t={s['t']}, exp={s['exp_r']}R over n={s['n']}"
        else:
            v, why = "HOLD", (f"pooled {key}: t={s['t']}, exp={s['exp_r']}R over n={s['n']}: "
                              f"inside the band; fades stand as they are")
        out[key] = {**s, "verdict": v, "why": why, "sleeves": sorted(names)}
    return out


def unattributed(sleeve: str) -> bool:
    """A ledger `sleeve` that is the BROKER'S rewrite of the order comment ("[sl 4300.69]",
    "[tp ...]", "#222731812 by #222705155"), not a sleeve: it names no key a zero could reach."""
    return sleeve.startswith(("[", "#"))


def traded_names() -> list[str]:
    """Every sleeve name the live ledger holds a closed deal for inside the trailing window."""
    if not LEDGER.exists():
        return []
    cutoff = datetime.now(tz=UTC) - timedelta(days=TRAIL_DAYS)
    seen: dict[str, None] = {}
    for line in LEDGER.read_text("utf-8").splitlines():
        try:
            r = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if not isinstance(r, dict) or not r.get("sleeve") or unattributed(str(r["sleeve"])):
            continue
        try:
            ts = datetime.fromisoformat(str(r.get("time", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if (ts if ts.tzinfo else ts.replace(tzinfo=UTC)) >= cutoff:
            seen[str(r["sleeve"])] = None
    return list(seen)


def degenerate(rs: list[float]) -> str:
    """`promoter.degenerate_evidence` on a bare series (mirrored; pinned equal by
    test_decay_traded_keys): why the series cannot support a retirement, or "".

    A constant or near-constant r-series is the signature of a broken r_multiple computation
    (gold_asia was retired twice on one in September), so no door below fires on it."""
    if len(rs) < 2:
        return ""
    if len({round(x, 9) for x in rs}) == 1:
        return (f"every one of {len(rs)} r_multiples is exactly {rs[0]:+.3f} -- a constant series "
                f"is a computation defect, not performance; refusing to retire on it")
    if all(x == 0.0 for x in rs):
        return f"all {len(rs)} r_multiples are 0.0 -- risk_per_lot was unmeasurable on every fill"
    counts: dict[float, int] = {}
    for x in rs:
        counts[round(x, 9)] = counts.get(round(x, 9), 0) + 1
    value, hits = max(counts.items(), key=lambda kv: kv[1])
    if hits / len(rs) >= 0.80:
        return (f"{hits} of {len(rs)} r_multiples are exactly {value:+.3f} "
                f"({100 * hits / len(rs):.0f}%) -- a near-constant series is a computation "
                f"defect, not performance; a real "
                f"sleeve's losses differ in size. Refusing to retire on it")
    return ""


def _promoter_dd(rs: list[float]) -> float:
    """The drawdown exactly as `promoter.sleeve_forward_stats` measures it: the peak starts at the
    first cumulative value, not at zero."""
    cum, out, peak = 0.0, 0.0, None
    for r in rs:
        cum += r
        peak = cum if peak is None else max(peak, cum)
        out = min(out, cum - peak)
    return round(out, 3)


def book_key_verdict(rs: list[float]) -> tuple[str, str, dict]:
    """The PROMOTER'S retirement bars on a key's trailing live record: ZERO, HEALTHY or
    UNMEASURED (no measurable trade, or a degenerate series the promoter would refuse).

    The same guard and the same three doors `promoter.run` applies to a LIVE or STANDBY row, in
    the same order: `degenerate_evidence` first; then the roll-20 expectancy at or below 0R once
    10 trades exist; a drawdown past -25R at any n (measured as the promoter measures it); a
    50-trade expectancy under 0.05R. No new threshold is introduced.

    GROWTH GOVERNANCE, RULE 1. A key that trips a door has a measured live expectancy at or below
    zero (or a drawdown the forward verdicts already call ruinous), so every unit of risk it is
    given lowers E[log W] in expectation: the zero raises robust forward growth rather than
    trading it away. The forgone risk is still billed as a missed-growth line by the gateway.
    """
    n = len(rs)
    s = stats(rs)
    s["max_dd_r"] = _promoter_dd(rs)
    roll = rs[-BOOK_RETIRE_ROLL:]
    roll_exp = sum(roll) / len(roll) if roll else 0.0
    facts = {**s, "roll20_exp": round(roll_exp, 4)}
    if n == 0:
        return "UNMEASURED", "no trade with a measurable R in the window", facts
    bad = degenerate(rs)
    if bad:
        return "UNMEASURED", bad, facts
    if n >= BOOK_RETIRE_MIN_N and roll_exp <= 0.0:
        return "ZERO", f"roll20 exp {roll_exp:.3f}R <= 0 over n={n}", facts
    if s["max_dd_r"] < BOOK_RETIRE_MAX_DD:
        return "ZERO", f"live maxDD {s['max_dd_r']:.1f}R < {BOOK_RETIRE_MAX_DD}R", facts
    if n >= 50 and s["exp_r"] < BOOK_RETIRE_MIN_EXP:
        return "ZERO", f"n={n} exp {s['exp_r']:.3f}R < {BOOK_RETIRE_MIN_EXP}R", facts
    return "HEALTHY", f"n={n}, roll20 exp {roll_exp:.3f}R, maxDD {s['max_dd_r']}R", facts


#: THE ONLY FLAG-INSTEAD-OF-ZERO KEYS (zuck 2026-10-29 15:55Z: "zeroing is allowed pin is only fr
#: gold Asia one temporarily only"). A key here that trips the bars is FLAGGED to the principal
#: while no LIVE (promoted) row on its symbol exists; once one does, the exemption ends and the
#: key is zeroed like any other. Every other key, principal-pinned book or not, is zeroed.
TEMPORARY_EXEMPT: frozenset[str] = frozenset({"gold_asia"})


def _stem(name: object) -> str:
    """A key as the ledger knows it: lowercased, `_v<n>` dropped, cut to the 27-char stem."""
    import re
    return re.sub(r"_v\d+$", "", str(name or "").strip()).lower()[:LEDGER_NAME_MAX]


def replacement_for(name: str, symbol: str, roster: dict[str, dict],
                    statuses: tuple[str, ...] = ("LIVE", "STANDBY")) -> str | None:
    """A certified roster row that could take `name`'s place: another row on the same symbol
    under a different book name, in one of `statuses`. None when there is none. Recorded on
    every zero; for a TEMPORARY_EXEMPT key only a LIVE (promoted) row ends the exemption."""
    me = _stem(name)
    for k, row in roster.items():
        if _stem(k) == me or not isinstance(row, dict):
            continue
        if str(row.get("status") or "").upper() in statuses \
                and str(row.get("symbol") or "").upper() == str(symbol or "").upper():
            return str(k)
    return None


def _cert_of(name: str, roster: dict[str, dict]) -> str | None:
    """The certificate the roster row for `name` (matched by stem) carries, or None."""
    me = _stem(name)
    for k, row in roster.items():
        if _stem(k) == me and isinstance(row, dict):
            c = row.get("certificate") or row.get("cert")
            if c:
                return str(c)
    return None


def decay_zero_doc(live: dict[str, dict], now: str, roster: dict[str, dict] | None = None,
                   prev: dict | None = None) -> dict:
    """DECAY_ZERO.json: every key that traded in the window outside the LIVE roster rows the loop
    in `main` already judges, the keys the promoter's bars ZERO, and the keys they would zero
    but are FLAGGED to the principal instead.

    ZUCK'S RULES (2026-10-29 15:21Z):
      * A ZERO IS ONE-WAY. It never re-arms because losses age out of the window; it lifts only
        when the key's roster row carries a DIFFERENT certificate than when it was zeroed (a
        fresh re-cert), exactly like the promoter's one-way retirement.
      * ZEROING IS ALLOWED ON EVERY KEY (15:55Z ruling), principal-pinned books included, except
        the TEMPORARY_EXEMPT keys (gold_asia only): those are FLAGGED while no promoted
        replacement exists on their symbol, and zeroed once one does.
    Only live-account rows count (a demo fill is not live evidence); an UNMEASURED key (no
    measurable R, or a degenerate series) is listed apart and moves nothing.
    """
    roster = roster or {}
    prev_zeros = dict((prev or {}).get("zeros") or {})
    exempt = {_stem(k) for k in TEMPORARY_EXEMPT}
    judged: dict[str, dict] = {}
    unmeasured: dict[str, dict] = {}
    zeros: dict[str, dict] = {}
    flags: dict[str, dict] = {}
    lifted: dict[str, dict] = {}
    live_stems = {str(k)[:LEDGER_NAME_MAX] for k in live}
    for name in traded_names():
        if name in live or name in live_stems:
            continue                                  # the LIVE loop judges it, on its own bars
        trades = [t for t in sleeve_trades(name)
                  if str(t.get("account_kind") or "live").lower() == "live"]
        rs = [float(t["r_multiple"]) for t in trades]
        v, why, facts = book_key_verdict(rs)
        row = {**facts, "verdict": v, "why": why}
        if v == "UNMEASURED":
            unmeasured[name] = row
            continue
        judged[name] = row
        if v != "ZERO":
            continue
        symbol = next((str(t.get("symbol")) for t in reversed(trades) if t.get("symbol")), "")
        repl = replacement_for(name, symbol, roster)
        stem_rows = sorted(k for k in roster if _stem(k) == _stem(name))
        entry = {"why": why, "n": facts["n"], "exp_r": facts["exp_r"],
                 "roll20_exp": facts["roll20_exp"], "max_dd_r": facts["max_dd_r"],
                 "symbol": symbol, "roster_rows": stem_rows, "since": now,
                 "certificate": _cert_of(name, roster)}
        if _stem(name) in exempt and replacement_for(name, symbol, roster, ("LIVE",)) is None:
            flags[name] = {**entry, "replacement": repl,
                           "flag": (f"temporary exemption (zuck 2026-10-29): no promoted "
                                    f"replacement on {symbol} yet; the principal decides")}
        else:
            zeros[name] = {**entry, "replacement": repl}
    # ONE-WAY: every earlier zero stands unless its row's certificate changed since.
    for k, z in prev_zeros.items():
        if not isinstance(z, dict):
            continue
        cert_now = _cert_of(k, roster)
        if z.get("certificate") and cert_now and cert_now != z.get("certificate"):
            lifted[k] = {**z, "lifted": now, "why_lifted": f"re-certified ({cert_now})"}
            continue
        zeros.setdefault(k, z)
        if isinstance(zeros[k], dict):
            zeros[k]["since"] = z.get("since") or now
        flags.pop(k, None)
    return {"checked_at": now, "trail_days": TRAIL_DAYS, "zeros": zeros, "flags": flags,
            "lifted": lifted, "judged": judged, "unmeasured": unmeasured,
            "zeroed_heat_redeployed": False,
            "rule": (f"a key that closed a live trade in the last {TRAIL_DAYS} days and is not a "
                     f"LIVE roster row is judged on the promoter's retirement bars "
                     f"(degenerate series refused; roll{BOOK_RETIRE_ROLL} exp <= 0R at n >= "
                     f"{BOOK_RETIRE_MIN_N}; maxDD < {BOOK_RETIRE_MAX_DD}R; n >= 50 and exp < "
                     f"{BOOK_RETIRE_MIN_EXP}R). A tripped key is ZEROED; only "
                     f"{sorted(TEMPORARY_EXEMPT)} "
                     f"is FLAGGED instead while no promoted replacement exists. A zero "
                     f"is one-way and lifts only on a new certificate. The zeroed key's heat is "
                     f"not redeployed by this file; the allocator's next solve decides it")}


def queue_close(names: list[str], path: Path | None = None) -> None:
    """Add retired sleeve names to the gateway's close queue (merged, never duplicated)."""
    # Beside whatever roster this run judges: a test that redirects SLEEVES_FILE to tmp_path
    # must never queue a close into the desk's real data directory.
    p = path or (SLEEVES_FILE.parent / CLOSE_QUEUE.name)
    have: list[str] = []
    try:
        have = [str(x) for x in (json.loads(p.read_text("utf-8")).get("names") or [])]
    except (OSError, ValueError):
        have = []
    merged = list(dict.fromkeys(have + [str(n) for n in names if n]))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"names": merged,
                             "at": datetime.now(tz=UTC).isoformat(timespec="seconds")},
                            indent=1), "utf-8")


def source_state() -> tuple[str, str]:
    """Which of the THREE states the roster is in -- they are not one answer.

    `_read_json` returns `{}` for a file that is absent, a file that is empty, and a file that is
    corrupt or unreadable, so `live_sleeves: 0` was published with the note "a measured zero, not
    a silence" in all three cases. Measured 2026-08-27: `data/sleeves.json` does not exist on this
    box (the promoter, its only writer, has promoted nothing), and the artifact asserted a measured
    zero anyway. Today that zero is right by luck. The state this collapse is dangerous in is the
    unreadable one: a live book whose roster went unreadable would be certified HEALTHY forever by
    an organ whose whole job is to notice harm, and nothing in the artifact would say otherwise.
    UNMEASURED is a real answer (L1.28a) and absence is never a clean verdict.
    """
    if not SLEEVES_FILE.exists():
        return "NO_ROSTER", (f"{SLEEVES_FILE.name} does not exist -- its only writer is "
                             f"research/promoter.py, so nothing has ever been promoted to live "
                             f"risk. Zero live sleeves is CORRECT here and no verdict is owed.")
    try:
        json.loads(SLEEVES_FILE.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return "UNMEASURED", (f"{SLEEVES_FILE.name} exists but could not be read "
                              f"({type(exc).__name__}: {exc}) -- the live roster is UNKNOWN, not "
                              f"empty. Every verdict below is absent, not healthy.")
    return "READ", f"{SLEEVES_FILE.name} read cleanly"


# ------------------------------------------------------------------------------ THE MODEL HALF
def roster_rows(doc) -> dict[str, dict]:
    """Every roster row by name, whichever shape the file has.

    MEASURED 2026-09-08: `promoter.save_sleeves` writes `{"sleeves": [row, ...]}` (a LIST, each
    row carrying `name`), and `decision_core.load_sleeves` reads that list. The verdict loop in
    `main` reads a DICT keyed by name, so on a promoter-written roster it judges no row at all.
    That loop is NOT changed here (this wave may not arm a demotion path); the model half reads
    both shapes so a half-life is published for every row the promoter actually wrote, and the
    artifact names the mismatch so it cannot stay invisible.
    """
    if not isinstance(doc, dict):
        return {}
    sl = doc.get("sleeves")
    if isinstance(sl, list):
        return {str(r["name"]): r for r in sl if isinstance(r, dict) and r.get("name")}
    if isinstance(sl, dict):
        return {str(k): v for k, v in sl.items() if isinstance(v, dict)}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


def _row_time(row: dict) -> datetime | None:
    for k in _TIME_KEYS:
        v = row.get(k)
        if not isinstance(v, str) or not v.strip():
            continue
        try:
            ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            continue
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return None


def _row_r(row: dict) -> float | None:
    for k in _R_KEYS:
        v = row.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _shadow_ledger_rows(name: str) -> list[dict]:
    """The sleeve's forward-clock ledger rows, from the first directory that holds the file.
    Ledgers are named by the clock key with dots as underscores (`ledger_CADJPY_asia.json`)."""
    stem = str(name).replace(".", "_")
    for d in SHADOW_LEDGER_DIRS:
        f = d / f"ledger_{stem}.json"
        if not f.exists():
            continue
        rows = _read_json(f, None)
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    return []


def sleeve_series(name: str, now: datetime | None = None
                  ) -> tuple[list[tuple[float, float]], str, int]:
    """(points, basis, n): the trailing (days_since_first_trade, R) series to fit, oldest first.

    THE LIVE LEDGER FIRST, THE CLOCK SECOND. Live fills are the evidence the demotion half
    judges on; when they are fewer than MIN_FIT_TRADES the sleeve's own forward clock supplies
    the series (forward-phase rows when there are enough, every row otherwise), inside the same
    trailing window and cap the verdicts use. The basis is part of the answer: a half-life fitted
    on a clock is a half-life of the SIMULATED edge, and the artifact says so.
    """
    now = now or datetime.now(tz=UTC)
    cutoff = now - timedelta(days=TRAIL_DAYS)

    def _pairs(rows: list[dict]) -> list[tuple[datetime, float]]:
        out = []
        for r in rows:
            ts, rv = _row_time(r), _row_r(r)
            if ts is None or rv is None or ts < cutoff:
                continue
            out.append((ts, rv))
        out.sort(key=lambda p: p[0])
        return out[-TRAIL_MAX_TRADES:]

    live = _pairs(sleeve_trades(name))
    best, basis = live, "live_ledger"
    if len(live) < MIN_FIT_TRADES:
        shadow = _shadow_ledger_rows(name)
        fwd = _pairs([r for r in shadow if str(r.get("phase") or "") == "forward"])
        alls = _pairs(shadow)
        if len(fwd) >= MIN_FIT_TRADES:
            best, basis = fwd, "shadow_forward"
        elif len(alls) > len(live):
            best, basis = alls, "shadow_all"
    if not best:
        return [], "none", 0
    t0 = best[0][0]
    return [((ts - t0).total_seconds() / 86400.0, r) for ts, r in best], basis, len(best)


def fit_half_life(points: list[tuple[float, float]], basis: str = "") -> dict:
    """The exponential the trailing expectancy series is decaying along, or why there is none.

        e(t) = e0 * exp(-lambda t),  fitted as  ln e_k = a - lambda t_k

    over the ROLLING expectancy (mean R of the last FIT_WINDOW trades) at each trade's time.
    Only points with a positive rolling expectancy enter the fit -- a log of a losing window is
    undefined, and a sleeve with nothing positive to decay from has no half-life, it has no edge
    over the window, which the demotion half already judges. `half_life_days` is ln 2 / lambda;
    `t_to_fade_days` is the time until the fitted expectancy, continued from its last point,
    reaches FADE_FLOOR_R. A rising or flat series is MEASURED with no finite half-life, which is
    the reading the allocator wants (a long or infinite half-life earns back the blanket haircut).

    UNMEASURED, with the n, whenever: fewer than MIN_FIT_TRADES trades; fewer than MIN_FIT_POINTS
    positive rolling points; or the positive points span under MIN_FIT_SPAN_DAYS of calendar
    time, because a rate cannot be fitted against no time. No threshold here moves capital.
    """
    n = len(points)
    out: dict = {"status": "UNMEASURED", "n": n, "basis": basis or "none",
                 "half_life_days": None, "t_to_fade_days": None, "lambda_per_day": None,
                 "expectancy_now_r": None, "fade_floor_r": FADE_FLOOR_R, "direction": None,
                 "fit_window": FIT_WINDOW, "fit_points": 0, "fit_r2": None, "span_days": 0.0,
                 "why": ""}
    if n < MIN_FIT_TRADES:
        out["why"] = (f"{n} trailing trade(s) < {MIN_FIT_TRADES}: no expectancy series to fit; "
                      f"half-life UNMEASURED at this n")
        return out
    pts = sorted(points, key=lambda p: p[0])
    rolling = [(pts[k][0], sum(r for _, r in pts[k - FIT_WINDOW + 1:k + 1]) / FIT_WINDOW)
               for k in range(FIT_WINDOW - 1, n)]
    pos = [(t, math.log(e)) for t, e in rolling if e > 0.0]
    span = (max(t for t, _ in pos) - min(t for t, _ in pos)) if pos else 0.0
    out.update({"fit_points": len(pos), "span_days": round(span, 3)})
    if len(pos) < MIN_FIT_POINTS:
        out["why"] = (f"{len(pos)} positive rolling-expectancy point(s) of {len(rolling)} "
                      f"(window {FIT_WINDOW}); an exponential decay needs {MIN_FIT_POINTS}. The "
                      f"edge is absent over this window, which is not the same as decaying -- "
                      f"the demotion half judges absence, this half measures the rate")
        return out
    if span < MIN_FIT_SPAN_DAYS:
        out["why"] = (f"the positive points span {span:.2f} day(s) < {MIN_FIT_SPAN_DAYS}: no "
                      f"calendar time to fit a rate against")
        return out
    ts = [t for t, _ in pos]
    ys = [y for _, y in pos]
    mt, my = sum(ts) / len(ts), sum(ys) / len(ys)
    sxx = sum((t - mt) ** 2 for t in ts)
    sxy = sum((t - mt) * (y - my) for t, y in zip(ts, ys, strict=True))
    slope = sxy / sxx
    a = my - slope * mt
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + slope * t)) ** 2 for t, y in zip(ts, ys, strict=True))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    lam = -slope
    e_now = math.exp(a + slope * max(ts))
    out.update({"status": "MEASURED", "lambda_per_day": round(lam, 6),
                "fit_r2": round(r2, 4), "expectancy_now_r": round(e_now, 4)})
    if lam > 1e-9:
        hl = math.log(2.0) / lam
        ttf = max(0.0, math.log(e_now / FADE_FLOOR_R) / lam) if e_now > FADE_FLOOR_R else 0.0
        out.update({"direction": "decaying", "half_life_days": round(hl, 2),
                    "t_to_fade_days": round(ttf, 2),
                    "why": (f"log-linear fit over {len(pos)} rolling-expectancy points spanning "
                            f"{span:.1f} day(s) ({basis}, r2={r2:.2f}): the expectancy halves "
                            f"every {hl:.1f} day(s) and, continued at that rate from "
                            f"{e_now:.3f}R, reaches the {FADE_FLOOR_R}R floor in {ttf:.1f} "
                            f"day(s)")})
    else:
        out.update({"direction": "rising" if lam < -1e-9 else "flat",
                    "why": (f"no decay measured over {len(pos)} points spanning {span:.1f} "
                            f"day(s) ({basis}, r2={r2:.2f}): the fitted expectancy is not "
                            f"falling (lambda={lam:+.4f}/day), so the half-life is not finite")})
    return out


def successor_tasks(models: dict[str, dict], rows: dict[str, dict], now: str) -> list[dict]:
    """One `successor_hunt` per LIVE sleeve whose fitted half-life is under 2x the forward window
    a successor still has to clear. Keyed on mechanism and symbol; the queue contract is
    alpha_breadth's (source, kind, title, description, status None, consumer). Titles carry no
    number, so a rerun keys the same task and the worker bills it once."""
    lead = SUCCESSOR_HALF_LIFE_MULT * FORWARD_BAR_DAYS
    tasks: list[dict] = []
    for name, m in sorted(models.items()):
        row = rows.get(name) or {}
        if str(row.get("status") or "LIVE").upper() != "LIVE":
            continue
        hl = m.get("half_life_days")
        if m.get("status") != "MEASURED" or not isinstance(hl, (int, float)) or hl >= lead:
            continue
        sym = str(row.get("symbol") or "")
        fam = str(row.get("family") or "")
        sel = str(row.get("selector") or row.get("window") or "")
        tasks.append({
            "source": "decay_monitor", "kind": "successor_hunt",
            "title": (f"Successor hunt: {fam or 'unknown mechanism'} on {sym or '?'} "
                      f"(incumbent {name})"),
            "description": (
                f"{name} is LIVE and its trailing expectancy is decaying: fitted half-life "
                f"{hl:.1f} day(s) ({m.get('basis')}, {m.get('fit_points')} points), reaching the "
                f"{FADE_FLOOR_R}R floor in about {m.get('t_to_fade_days')} day(s). A successor "
                f"needs the forward bar ({FORWARD_BAR_DAYS} days / 50 trades) before it can carry "
                f"capital, so the search starts now, while the incumbent still earns. What to "
                f"hunt: a mechanism on {sym or 'the same instrument'} in the {sel or 'same'} "
                f"selector that is NOT a re-parameterisation of {fam or 'the incumbent'} -- the "
                f"payer the incumbent monetised is drying up, so name a different payer on the "
                f"MT5/Fusion universe. Nothing retires: the incumbent keeps every unit of its "
                f"capital and the promoter refills the slot only if it fails the unchanged "
                f"retire rules."),
            "sleeve": name, "symbol": sym, "family": fam, "mechanism": fam, "selector": sel,
            "state": row.get("state"), "half_life_days": hl,
            "t_to_fade_days": m.get("t_to_fade_days"), "basis": m.get("basis"),
            "remaining_forward_window_days": FORWARD_BAR_DAYS,
            "successor_lead_days": lead, "issued_at": now, "status": None,
            "consumer": "deepening_worker / proposers / research brains",
        })
    return tasks


def _write_queue(tasks: list[dict]) -> tuple[bool, str]:
    """Replace this source's rows in the deepening queue, through the one shared writer."""
    try:
        try:
            from research.regime_coverage import _merge_into_queue
        except ImportError:
            from regime_coverage import _merge_into_queue
        _merge_into_queue(tasks, source="decay_monitor")
        return True, f"{len(tasks)} successor_hunt task(s) written under source decay_monitor"
    except Exception as exc:
        return False, f"queue write failed: {type(exc).__name__}: {exc}"


def decay_models(doc, now: datetime | None = None) -> dict[str, dict]:
    """The half-life model for every non-retired roster row, whichever shape the roster has."""
    models: dict[str, dict] = {}
    for name, row in roster_rows(doc).items():
        if str(row.get("status") or "").upper() == "RETIRED":
            continue
        pts, basis, _n = sleeve_series(name, now)
        m = fit_half_life(pts, basis)
        m["roster_status"] = row.get("status") or None
        m["symbol"] = row.get("symbol")
        m["family"] = row.get("family")
        models[name] = m
    return models


def main(write_queue: bool = True) -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    source, source_why = source_state()
    doc = _read_json(SLEEVES_FILE, {})
    # THE VERDICT LOOP READS THE ROSTER IN THE SHAPE THE PROMOTER WRITES (2026-09-16). It read a
    # DICT keyed by name; `promoter.save_sleeves` writes `{"sleeves": [row, ...]}`, a LIST. On
    # every promoter-written roster the loop therefore judged NO row -- `roster_rows` had named
    # the mismatch in the artifact since 2026-09-08 and the demotion path stayed unarmed. Measured
    # 2026-09-16 on the trading box: "decay monitor: 0 live sleeve(s) [READ], 0 flagged" while
    # `xau_m15_anti_breakout` sat at 21 live trades, 31% wins and -39 EUR on the day, and five
    # EURCHF sleeves were 0-for-27. `roster_rows` reads both shapes; the rows it returns are the
    # roster's own dict objects, so a FADE flag written here lands in the file, and a RETIRE
    # removes the row from whichever container holds it.
    sleeves = roster_rows(doc)
    report, actions, changed = {}, [], False

    live = {k: v for k, v in sleeves.items()
            if isinstance(v, dict) and str(v.get("status") or "LIVE").upper() == "LIVE"}
    for name, row in live.items():
        s = stats([float(t["r_multiple"]) for t in sleeve_trades(name)])
        v, why = verdict(s)
        report[name] = {**s, "verdict": v, "why": why,
                        "risk_frac": row.get("risk_frac")}
        # THE FLAG IS THE FADE (gap-fixer 2026-08-29). This block used to HALVE `risk_frac`
        # in the row as well. `mt5desk.sizing.clamp_risk_frac` floors at BASE_RISK_FRAC=0.03,
        # so 0.03 -> 0.015 was read straight back up to 0.03 and the gateway sized a FADED
        # sleeve at 3.0 lots -- identical to a healthy one, measured on the real functions.
        # The halving was not merely useless, it was WRONG in the one case it survived: a
        # dynamic-up sleeve at 0.06 written to 0.03 and then multiplied by the fade would be
        # cut 4x where the law orders 2x. `promoted_lot` now applies `decay_factor(decay_faded)`
        # outside the clamp, so the flag alone carries the fade -- and UNFADE becomes exact,
        # since deleting a flag is lossless where dividing by 0.5 is not.
        if v == "FADE" and not row.get("decay_faded"):
            eff = float(row.get("risk_frac") or 0.03)
            row["decay_faded"] = now
            row["decay_fade_basis"] = "own"
            actions.append({"at": now, "sleeve": name, "action": "FADE",
                            "risk_frac": [eff, round(eff * FADE_FACTOR, 4)], "why": why})
            changed = True
        elif (v == "HEALTHY" and row.get("decay_faded")
              and not str(row.get("decay_fade_basis") or "").startswith("pool:")):
            # recovery from a fade is automatic -- the fade was a hedge on uncertainty, not a
            # sentence. RETIRE recovery is NOT automatic: that runs back through the forward window.
            # A sleeve faded by its POOL is lifted by its pool, never by its own thin record.
            eff = float(row.get("risk_frac") or 0.03)
            del row["decay_faded"]
            row.pop("decay_fade_basis", None)
            actions.append({"at": now, "sleeve": name, "action": "UNFADE",
                            "risk_frac": [round(eff * FADE_FACTOR, 4), eff], "why": why})
            changed = True
        elif v == "RETIRE":
            actions.append({"at": now, "sleeve": name, "action": "RETIRE", "why": why,
                            "reentry": "certificate stands; re-earn live risk through a fresh "
                                       "pre-registered forward window (RESEARCH 6d) -- the "
                                       "promoter refills the freed slot from matured candidates "
                                       "on its next daily pass"})
            sleeves.pop(name, None)
            queue_close([name])
            changed = True

    # THE POOLED VERDICT, AFTER THE PER-SLEEVE ONE: a pool that is losing fades every live sleeve
    # in it; a pool past the retirement bar retires every live sleeve in it; a pool that has
    # turned lifts only the sleeves it faded itself.
    pools = pooled_verdicts({k: v for k, v in live.items() if k in sleeves})
    for key, pv in pools.items():
        for name in pv["sleeves"]:
            row = sleeves.get(name)
            if not isinstance(row, dict):
                continue
            basis = str(row.get("decay_fade_basis") or "")
            if pv["verdict"] == "RETIRE":
                actions.append({"at": now, "sleeve": name, "action": "RETIRE", "pool": key,
                                "why": pv["why"],
                                "reentry": "certificate stands; re-earn live risk through a "
                                           "fresh pre-registered forward window (RESEARCH 6d)"})
                if name in report:
                    report[name].update({"pool": key, "pool_verdict": "RETIRE"})
                sleeves.pop(name, None)
                queue_close([name])
                changed = True
                continue
            if pv["verdict"] == "FADE" and not row.get("decay_faded"):
                eff = float(row.get("risk_frac") or 0.03)
                row["decay_faded"] = now
                row["decay_fade_basis"] = f"pool:{key}"
                actions.append({"at": now, "sleeve": name, "action": "FADE", "pool": key,
                                "risk_frac": [eff, round(eff * FADE_FACTOR, 4)],
                                "why": pv["why"]})
                changed = True
            elif (pv["verdict"] == "HEALTHY" and row.get("decay_faded")
                  and basis == f"pool:{key}"):
                eff = float(row.get("risk_frac") or 0.03)
                del row["decay_faded"]
                row.pop("decay_fade_basis", None)
                actions.append({"at": now, "sleeve": name, "action": "UNFADE", "pool": key,
                                "risk_frac": [round(eff * FADE_FACTOR, 4), eff],
                                "why": pv["why"]})
                changed = True
            if name in report:
                report[name]["pool"] = key
                report[name]["pool_verdict"] = pv["verdict"]

    if changed:
        # Write back in the file's OWN shape: the list the promoter writes keeps every row that
        # was not retired (edited rows are the same objects, so FADE flags are already on them);
        # a dict-shaped roster is rebuilt from the surviving rows.
        if isinstance(doc, dict) and isinstance(doc.get("sleeves"), list):
            doc["sleeves"] = [r for r in doc["sleeves"]
                              if not (isinstance(r, dict) and r.get("name")
                                      and str(r["name"]) not in sleeves)]
            SLEEVES_FILE.write_text(json.dumps(doc, indent=2), "utf-8")
        elif isinstance(doc, dict) and isinstance(doc.get("sleeves"), dict):
            doc["sleeves"] = sleeves
            SLEEVES_FILE.write_text(json.dumps(doc, indent=2), "utf-8")
        else:
            SLEEVES_FILE.write_text(json.dumps(sleeves, indent=2), "utf-8")
        with ACTIONS.open("a", encoding="utf-8") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

    # THE MODEL HALF, after the verdicts and reading none of them: a half-life per roster row,
    # merged onto the verdict row where one exists, and a successor hunt for every LIVE sleeve
    # whose edge halves inside the window a successor still has to clear.
    models = {} if source == "UNMEASURED" else decay_models(doc)
    for name, m in models.items():
        if name in report:
            report[name].update({"half_life_days": m["half_life_days"],
                                 "t_to_fade_days": m["t_to_fade_days"],
                                 "decay_model": m["status"]})
    hunts = successor_tasks(models, roster_rows(doc), now)
    queue = {"source": "decay_monitor", "n_tasks": len(hunts), "written": False,
             "why": "no LIVE sleeve's fitted half-life is under the successor lead time"}
    if hunts and write_queue:
        queue["written"], queue["why"] = _write_queue(hunts)
    elif hunts:
        queue["why"] = "queue write disabled for this pass (--no-queue)"
    rows_seen = roster_rows(doc)
    shape_note = None
    if rows_seen and not live:
        # The loop reads both shapes since 2026-09-16; what it finds is no LIVE row. The keys that
        # trade anyway (book keys on STANDBY or RETIRED rows) are judged into DECAY_ZERO below.
        shape_note = (f"the roster holds {len(rows_seen)} row(s) and none is LIVE, so the "
                      f"verdict loop judged none; every key that traded is judged against the "
                      f"promoter's retirement bars into {DECAY_ZERO.name} instead")
    # THE BOOK KEYS, every pass the roster was read: rebuilt in full, keeping the first `since`.
    zero_doc = None
    # Beside whatever roster this run judges (as `queue_close`): a test that redirects
    # SLEEVES_FILE can never write the desk's real DECAY_ZERO.json.
    zero_path = SLEEVES_FILE.parent / DECAY_ZERO.name
    if source != "UNMEASURED":
        prev_doc = _read_json(zero_path, {})
        prev_doc = prev_doc if isinstance(prev_doc, dict) else {}
        zero_doc = decay_zero_doc(live, now, roster_rows(doc), prev_doc)
        before_z, before_f = set(prev_doc.get("zeros") or {}), set(prev_doc.get("flags") or {})
        for k, z in zero_doc["zeros"].items():
            if k not in before_z:
                actions.append({"at": now, "sleeve": k, "action": "BOOK_ZERO", "why": z["why"],
                                "replacement": z.get("replacement")})
        for k, f_ in zero_doc["flags"].items():
            if k not in before_f:
                actions.append({"at": now, "sleeve": k, "action": "BOOK_FLAG", "why": f_["why"],
                                "flag": f_["flag"]})
        for k, z in zero_doc["lifted"].items():
            actions.append({"at": now, "sleeve": k, "action": "BOOK_LIFT",
                            "why": z["why_lifted"]})
        _write_atomic(zero_path, zero_doc)
        new_actions = [a for a in actions
                       if a["action"] in ("BOOK_ZERO", "BOOK_FLAG", "BOOK_LIFT")]
        if new_actions:
            with ACTIONS.open("a", encoding="utf-8") as f:
                for a in new_actions:
                    f.write(json.dumps(a) + "\n")

    OUT.write_text(json.dumps({
        "checked_at": now,
        "live_sleeves": None if source == "UNMEASURED" else len(live),
        "roster_state": source, "roster_why": source_why,
        "roster_rows_seen": len(rows_seen), "roster_shape_note": shape_note,
        "book_keys": (None if zero_doc is None else
                      {"judged": len(zero_doc["judged"]), "zeroed": sorted(zero_doc["zeros"]),
                       "flagged": sorted(zero_doc["flags"]),
                       "unmeasured": sorted(zero_doc["unmeasured"]),
                       "file": DECAY_ZERO.name}),
        "verdicts": report, "actions_taken": actions,
        "decay_model": models, "successor_hunts": hunts, "queue": queue,
        "model_rule": (
            f"half_life_days = ln 2 / lambda from a log-linear fit of the rolling expectancy "
            f"(window {FIT_WINDOW} trades) against calendar days; t_to_fade_days = days until the "
            f"fitted expectancy reaches {FADE_FLOOR_R}R (promoter.RETIRE_MIN_EXP). UNMEASURED "
            f"below {MIN_FIT_TRADES} trades / {MIN_FIT_POINTS} positive points / "
            f"{MIN_FIT_SPAN_DAYS} day of span. A successor_hunt is queued for a LIVE sleeve whose "
            f"half-life is under {SUCCESSOR_HALF_LIFE_MULT:.0f}x {FORWARD_BAR_DAYS} days. The "
            f"model moves no verdict, size or slot: it is published for the allocator to "
            f"consume as a per-sleeve decay probability"),
        # DECLARE WHY THE BYTES CANNOT MOVE, or a correct organ reads as a stuck one. With an
        # empty roster this file's content is a function of nothing, so `check_job_manifest`
        # flagged it FROZEN ("a loop turning without cutting") on 55 consecutive checks and
        # `check_live_readiness` blocked rung 0 on it -- a detector that is structurally red until
        # capital deploys, which is the always-red kind this desk retires on sight (L1.37). The
        # age check stays armed: a monitor that actually dies still goes STALE. Re-asserted on
        # every write, so the declaration goes stale exactly when the file does.
        "unchanged_because": (
            "the roster is empty (0 live sleeves), so there is nothing to decay and identical "
            "bytes are the correct output -- not a stalled loop"
        ) if (source != "UNMEASURED" and not live) else None,
        "note": ("a count is published only when the roster was READ or is provably absent; an "
                 "unreadable roster publishes null, because 0 and unknown are different answers "
                 "and only one of them is safe to act on (L1.28a)")}, indent=2), "utf-8")
    if source == "UNMEASURED":
        print(f"decay monitor: UNMEASURED -- {source_why}")
        return 1
    print(f"decay monitor: {len(live)} live sleeve(s) [{source}], "
          f"{sum(1 for r in report.values() if r['verdict'] != 'HEALTHY')} flagged, "
          f"{len(actions)} action(s); model: {len(models)} row(s), "
          f"{sum(1 for m in models.values() if m['status'] == 'MEASURED')} half-life(s) "
          f"measured, {len(hunts)} successor hunt(s) -- {queue['why']}; book keys: "
          f"{len(zero_doc['judged']) if zero_doc else 0} judged, "
          f"{len(zero_doc['zeros']) if zero_doc else 0} zeroed, "
          f"{len(zero_doc['flags']) if zero_doc else 0} flagged to the principal")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true",
                    help="publish the model but write no successor_hunt task into the queue")
    raise SystemExit(main(write_queue=not ap.parse_args().no_queue))
