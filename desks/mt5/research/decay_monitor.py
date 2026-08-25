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
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
OUT = BASE / "data" / "decay_live.json"
ACTIONS = BASE / "data" / "decay_actions.jsonl"

#: The promotion bar, mirrored. Change gate_spec.yaml, not this file, if the bar ever moves.
T_PROMOTE = 2.5
N_MIN_VERDICT = 20
DD_HARD_R = -25.0
#: Trailing window: judge the sleeve the market currently sees, not its lifetime average.
TRAIL_DAYS = 45
TRAIL_MAX_TRADES = 60
FADE_FACTOR = 0.5


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


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
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
        if v == "FADE" and not row.get("decay_faded"):
            old = float(row.get("risk_frac") or 0.03)
            row["risk_frac"] = round(old * FADE_FACTOR, 4)
            row["decay_faded"] = now
            actions.append({"at": now, "sleeve": name, "action": "FADE",
                            "risk_frac": [old, row["risk_frac"]], "why": why})
            changed = True
        elif v == "HEALTHY" and row.get("decay_faded"):
            # recovery from a fade is automatic -- the fade was a hedge on uncertainty, not a
            # sentence. RETIRE recovery is NOT automatic: that runs back through the forward window.
            old = float(row.get("risk_frac") or 0.015)
            row["risk_frac"] = round(old / FADE_FACTOR, 4)
            del row["decay_faded"]
            actions.append({"at": now, "sleeve": name, "action": "UNFADE",
                            "risk_frac": [old, row["risk_frac"]], "why": why})
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

    OUT.write_text(json.dumps({
        "checked_at": now, "live_sleeves": len(live),
        "verdicts": report, "actions_taken": actions,
        "note": "0 live sleeves is a measured zero, not a silence (L1.28a)"}, indent=2), "utf-8")
    print(f"decay monitor: {len(live)} live sleeve(s), "
          f"{sum(1 for r in report.values() if r['verdict'] != 'HEALTHY')} flagged, "
          f"{len(actions)} action(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
