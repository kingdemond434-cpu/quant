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

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
OUT = BASE / "data" / "decay_live.json"
ACTIONS = BASE / "data" / "decay_actions.jsonl"
#: The forward clocks' own ledgers, the model's fallback series while the live ledger is thin:
#: a promoted sleeve's shadow clock keeps running (promoter.py never stops it), so its forward
#: rows are the longest untouched expectancy series the desk holds for that sleeve.
SHADOW_LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")

#: The promotion bar, mirrored. Change gate_spec.yaml, not this file, if the bar ever moves.
T_PROMOTE = 2.5
N_MIN_VERDICT = 20
DD_HARD_R = -25.0
#: Trailing window: judge the sleeve the market currently sees, not its lifetime average.
TRAIL_DAYS = 45
TRAIL_MAX_TRADES = 60
FADE_FACTOR = 0.5

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
        if r.get("sleeve") != name or "r_multiple" not in r:
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
    out = {"n": n, "exp_r": 0.0, "t": 0.0, "max_dd_r": 0.0, "cum_r": 0.0}
    if not n:
        return out
    cum, peak, dd = 0.0, 0.0, 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    mean = sum(rs) / n
    out.update({"exp_r": round(mean, 4), "cum_r": round(cum, 3), "max_dd_r": round(dd, 3)})
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
    sleeves = doc.get("sleeves") if isinstance(doc, dict) else None
    if not isinstance(sleeves, dict):
        sleeves = doc if isinstance(doc, dict) else {}
    report, actions, changed = {}, [], False

    live = {k: v for k, v in sleeves.items() if isinstance(v, dict)}
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
            actions.append({"at": now, "sleeve": name, "action": "FADE",
                            "risk_frac": [eff, round(eff * FADE_FACTOR, 4)], "why": why})
            changed = True
        elif v == "HEALTHY" and row.get("decay_faded"):
            # recovery from a fade is automatic -- the fade was a hedge on uncertainty, not a
            # sentence. RETIRE recovery is NOT automatic: that runs back through the forward window.
            eff = float(row.get("risk_frac") or 0.03)
            del row["decay_faded"]
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
            changed = True

    if changed:
        if isinstance(doc, dict) and "sleeves" in doc:
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
        shape_note = (f"the roster holds {len(rows_seen)} row(s) in the LIST shape "
                      f"promoter.save_sleeves writes; the verdict loop reads a DICT-shaped roster "
                      f"and judged none of them (a standing defect, reported here and NOT "
                      f"changed by the model half -- fixing it arms a demotion path)")

    OUT.write_text(json.dumps({
        "checked_at": now,
        "live_sleeves": None if source == "UNMEASURED" else len(live),
        "roster_state": source, "roster_why": source_why,
        "roster_rows_seen": len(rows_seen), "roster_shape_note": shape_note,
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
          f"measured, {len(hunts)} successor hunt(s) -- {queue['why']}")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-queue", action="store_true",
                    help="publish the model but write no successor_hunt task into the queue")
    raise SystemExit(main(write_queue=not ap.parse_args().no_queue))
