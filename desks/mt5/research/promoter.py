"""Auto-promotion / auto-retirement for shadow-validated sleeves.

Runs daily at 22:00 UTC inside the gateway loop (after shadow_forward.main()).

PROMOTE (fully automatic):
  - shadow verdict == PROMOTION CANDIDATE and not yet promoted:
    * XAUUSD challengers: promote only if their forward exp >= the armed gold
      sleeve's forward exp (live ledger, same window) - 0.02 margin; else KILL.
    * JPY-cross sleeves: promote directly at 3% base risk (gateway sizes at order time).
  - promoted sleeves are written to data/sleeves.json (status LIVE) and the
    gateway picks them up on the next pass (< 1 min).

RETIRE (fully automatic):
  - for each LIVE promoted sleeve: forward stats from the live ledger:
    * n >= 10 and rolling-20 exp <= 0      -> RETIRED (edge gone)
    * forward maxDD < -25R                 -> RETIRED (tail breach)
    * n >= 50 and exp < 0.05R              -> RETIRED (weak)
  - retired sleeves are removed from trading config and marked KILL in shadow
    state (never re-promoted).

The armed gold book is NOT managed here (hunt5 authority, armed by human).
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "promoter.log"

# SIZING (principal 2026-08-25): promoted sleeves are sized by the gateway at order time --
# 3% of equity base risk per trade off the bracket's own stop distance (mt5desk/sizing.py),
# canary-ramped by live trade count. The promoter records the sleeve's risk fraction;
# raising it above the base requires recorded economic justification and stays capped there.
PROMOTED_RISK_FRAC = 0.03
PROMOTED_LOT = 0.01     # legacy field kept for old readers; the gateway ignores it
CHAMPION_MARGIN = 0.02   # challenger must beat armed forward exp by this much
RETIRE_MIN_N = 10
RETIRE_MAX_DD = -25.0
RETIRE_MIN_EXP = 0.05

GOLD_WINDOWS = ["asia", "london_am", "ny_open", "afternoon"]


def plog(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def load_shadow() -> dict:
    p = SHADOW_DIR / "shadow_state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_sleeves(sleeves: list[dict]) -> None:
    SLEEVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SLEEVES_FILE.write_text(json.dumps({"sleeves": sleeves}, indent=2),
                            encoding="utf-8")


def load_sleeves() -> list[dict]:
    if not SLEEVES_FILE.exists():
        return []
    try:
        return json.loads(SLEEVES_FILE.read_text(encoding="utf-8")).get("sleeves", [])
    except Exception:
        return []


def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    try:
        return [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except Exception:
        return []


def armed_forward_exp(ledger: list[dict], window: str) -> float | None:
    """Armed gold sleeve forward exp from the live ledger (same window)."""
    rs = [r["r_multiple"] for r in ledger if r["sleeve"] == f"gold_{window}"]
    if len(rs) < 5:
        return None
    return sum(rs) / len(rs)


def sleeve_forward_stats(ledger: list[dict], name: str) -> dict:
    rs = [r["r_multiple"] for r in ledger if r["sleeve"] == name]
    n = len(rs)
    if n == 0:
        return {"n": 0, "exp": 0.0, "max_dd": 0.0, "roll20_exp": 0.0}
    roll = rs[-20:] if n >= 20 else rs
    cum = []
    acc = 0.0
    for r in rs:
        acc += r
        cum.append(acc)
    max_dd = min(cum[i] - max(cum[:i + 1]) for i in range(len(cum)))
    return {"n": n, "exp": sum(rs) / n, "max_dd": float(max_dd),
            "roll20_exp": sum(roll) / len(roll)}


def main() -> None:
    shadow = load_shadow()
    sleeves = load_sleeves()
    ledger = load_ledger()
    existing = {s["name"] for s in sleeves}
    changed = False

    for key, st in shadow.items():
        if key == "last_run":
            continue
        if st.get("status") != "PROMOTION CANDIDATE":
            continue
        if key in existing:
            continue
        sym, win = key.split(".", 1)
        if win not in GOLD_WINDOWS:
            continue
        if sym == "XAUUSD":
            armed_exp = armed_forward_exp(ledger, win)
            if armed_exp is None:
                plog(f"{key}: PROMOTION CANDIDATE, armed book has no forward data yet; wait")
                continue
            if st["exp_r"] < armed_exp - CHAMPION_MARGIN:
                st["status"] = "KILL"
                plog(f"{key}: challenger LOST to armed book "
                     f"({st['exp_r']:.3f}R vs {armed_exp:.3f}R); KILL")
                changed = True
                continue
        sleeves.append({"name": key, "symbol": sym, "window": win,
                        "lot": "auto_ramp", "risk_frac": PROMOTED_RISK_FRAC,
                        "status": "LIVE",
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": st.get("exp_r", 0.0)})
        plog(f"AUTO-PROMOTED {key} -> LIVE at {PROMOTED_RISK_FRAC:.0%} base risk "
             f"(shadow exp={st.get('exp_r', 0.0):.3f}R n={st.get('n', 0)})")
        changed = True

    for s in sleeves:
        if s.get("status") != "LIVE":
            continue
        fs = sleeve_forward_stats(ledger, s["name"])
        retire = False
        reason = ""
        if fs["n"] >= RETIRE_MIN_N and fs["roll20_exp"] <= 0.0:
            retire, reason = True, f"roll20 exp {fs['roll20_exp']:.3f}R <= 0"
        elif fs["max_dd"] < RETIRE_MAX_DD:
            retire, reason = True, f"forward maxDD {fs['max_dd']:.1f}R < {RETIRE_MAX_DD}R"
        elif fs["n"] >= 50 and fs["exp"] < RETIRE_MIN_EXP:
            retire, reason = True, f"n={fs['n']} exp {fs['exp']:.3f}R < {RETIRE_MIN_EXP}R"
        if retire:
            s["status"] = "RETIRED"
            s["retired_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
            s["retire_reason"] = reason
            skey = f"{s['symbol']}.{s['window']}"
            if skey in shadow:
                shadow[skey]["status"] = "KILL"
            plog(f"AUTO-RETIRED {s['name']} ({reason})")
            changed = True

    if changed:
        save_sleeves(sleeves)
        (SHADOW_DIR / "shadow_state.json").write_text(
            json.dumps(shadow, indent=2), encoding="utf-8")
        plog(f"sleeves.json updated: {[s['name'] for s in sleeves if s['status']=='LIVE']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        plog("promoter error: " + traceback.format_exc())