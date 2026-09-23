"""Auto-promotion / auto-retirement for shadow-validated sleeves.

Runs daily at 22:00 UTC inside the gateway loop (after shadow_forward.main()).

PROMOTE (fully automatic):
  - shadow verdict == PROMOTION CANDIDATE and not yet promoted:
    * If historical 10/10 pass: promote (existing logic)
    * If historical validity pass + power deficiencies + forward evidence passes:
      promote (NEW: forward evidence cures power deficiencies)
    * XAUUSD challengers: promote only if their forward exp >= the armed gold
      sleeve's forward exp (live ledger, same window) - 0.02 margin; else KILL.
    * JPY-cross sleeves: promote directly at PROMOTED_LOT.
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
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, for libs.*

from libs.ops.forward_clock import forward_days  # noqa: E402

from mt5desk import provenance  # noqa: E402
from shadow_admission import authorized_specs  # noqa: E402
from gate_classification import (  # noqa: E402
    historical_certificate_status,
    validity_all_pass,
    power_deficiencies,
    VALIDITY_GATES,
    POWER_GATES,
)

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "promoter.log"

PROMOTED_LOT = 0.01
CHAMPION_MARGIN = 0.02   # challenger must beat armed forward exp by this much
RETIRE_MIN_N = 10
RETIRE_MAX_DD = -25.0
RETIRE_MIN_EXP = 0.05

GOLD_WINDOWS = ["asia", "london_am", "ny_open", "afternoon"]

# Forward evidence thresholds to cure power deficiencies
FORWARD_CURE_MIN_TRADES = 50
FORWARD_CURE_MIN_EXP = 0.05
FORWARD_CURE_MAX_DD = -25.0
FORWARD_CURE_MIN_DAYS = 14


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
    """Closed trades from the account THIS DESK IS CURRENTLY TRADING, and no others."""
    if not LEDGER.exists():
        return []
    try:
        rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except Exception:
        return []
    try:
        import MetaTrader5 as mt5  # noqa: PLC0415
        acc = provenance.current_account(mt5.account_info())
    except Exception:
        acc = provenance.current_account(None)
    kept = [r for r in rows if provenance.same_account(r, acc)]
    if len(kept) != len(rows):
        plog(f"ledger: {len(kept)}/{len(rows)} rows are from the account in hand "
             f"(login={acc['login']} server={acc['server']} kind={acc['kind']}); "
             f"{len(rows) - len(kept)} from another account or predating provenance, excluded")
    return kept


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


def _load_historical_cert(key: str) -> dict | None:
    """Load the historical certificate for a shadow key from all possible sources."""
    reports = BASE / "reports"
    
    # Try QQUANT_GATES.json
    qquant = _read(reports / "QQUANT_GATES.json")
    if qquant.get("gate_policy") == "mt5-original-universal-10-v2-calibrated-inputs":
        for row in qquant.get("verdicts", []):
            if not isinstance(row, dict):
                continue
            row_key = f"{row.get('sym')} {row.get('fam')} {row.get('side')} {row.get('win')} {row.get('cond')}"
            if row_key == key:
                return {"gates": row.get("stages", {})}
    
    # Try REAL_SURVIVORS.json
    real = _read(reports / "REAL_SURVIVORS.json")
    for row in real.get("real_survivors", []):
        if not isinstance(row, dict):
            continue
        row_key = f"{row.get('sym')} {row.get('fam')} {row.get('side')} {row.get('win')} {row.get('state')}"
        if row_key == key:
            return {"gates": row.get("qquant_gates", {}).get("stages", {})}
    
    # Try UNIVERSAL_SURVIVORS.json
    universal = _read(reports / "UNIVERSAL_SURVIVORS.json")
    for cert in universal.get("survivors", {}).values():
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec")
        if not isinstance(spec, dict):
            continue
        cert_key = f"{spec.get('symbol')} {spec.get('family')} {spec.get('side')} {spec.get('selector')} {spec.get('condition')}"
        if cert_key == key:
            return {"gates": cert.get("gates", {})}
    
    return None


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _check_forward_cure(shadow_st: dict, key: str) -> bool:
    """Check if forward evidence cures the historical power deficiencies."""
    # Forward evidence must meet the cure thresholds
    n = int(shadow_st.get("n", 0) or 0)
    exp_r = float(shadow_st.get("exp_r", 0.0) or 0.0)
    max_dd_r = float(shadow_st.get("max_dd_r", 0.0) or 0.0)
    # DERIVED from the pre-registration stamp, never restated (LAWS L1.58). The stored
    # `days_active` was computed from the first trade ever taken on any row written before
    # 2026-08-26, so this gate could be cleared eight days early on selection-period
    # evidence. Unstamped derives to 0 and fails the window closed.
    days_active = forward_days(shadow_st) or 0
    
    if n < FORWARD_CURE_MIN_TRADES:
        return False
    if exp_r < FORWARD_CURE_MIN_EXP:
        return False
    if max_dd_r < FORWARD_CURE_MAX_DD:
        return False
    if days_active < FORWARD_CURE_MIN_DAYS:
        return False
    
    plog(f"{key}: forward cure SATISFIED (n={n}, exp={exp_r:.3f}R, maxDD={max_dd_r:.1f}R, days={days_active})")
    return True


def main() -> None:
    shadow = load_shadow()
    sleeves = load_sleeves()
    ledger = load_ledger()
    existing = {s["name"] for s in sleeves}
    gate_authority = authorized_specs(BASE)
    changed = False

    for key, st in shadow.items():
        if not isinstance(st, dict):
            continue
        if st.get("status") != "PROMOTION CANDIDATE":
            continue
        if key in existing:
            continue
        
        parts = key.split(".")
        sym, win = parts[0], parts[1]
        cond = parts[2] if len(parts) > 2 else None
        gate_spec = (sym, win, cond, "session_range_breakout", False)
        
        # Check historical certificate
        hist_cert = _load_historical_cert(key)
        hist_status = historical_certificate_status(hist_cert) if hist_cert else None
        has_full_10_pass = gate_spec in gate_authority
        has_validity_pass = hist_status and hist_status.get("validity_pass", False)
        power_defs = hist_status.get("power_deficiencies", []) if hist_status else list(POWER_GATES)
        
        if not has_full_10_pass:
            if has_validity_pass and power_defs:
                # Historical validity pass + power deficiencies -> check forward cure
                if _check_forward_cure(st, key):
                    plog(f"{key}: VALIDITY PASS + power deficiencies {power_defs} CURED by forward evidence")
                else:
                    st["status"] = "BLOCKED_POWER_UNCURED"
                    st["promotion_authority"] = False
                    st["gate_reason"] = f"historical power deficiencies {power_defs} not cured by forward evidence"
                    plog(f"{key}: promotion refused -- power deficiencies {power_defs} not cured")
                    changed = True
                    continue
            else:
                # No validity pass or no historical cert at all
                st["status"] = "BLOCKED_UNIVERSAL_GATES"
                st["promotion_authority"] = False
                st["gate_reason"] = "missing validity pass or historical certificate"
                plog(f"{key}: live promotion refused -- no canonical validity certificate")
                changed = True
                continue
        
        # Has full 10/10 pass (existing logic)
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
        
        # Promote
        sleeves.append({"name": key, "symbol": sym, "window": win,
                        "state": cond,
                        "lot": PROMOTED_LOT, "status": "LIVE",
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": st.get("exp_r", 0.0),
                        "promotion_basis": "FULL_10_PASS" if has_full_10_pass else "VALIDITY_PASS_FORWARD_CURE"})
        basis = "FULL_10_PASS" if has_full_10_pass else "VALIDITY_PASS_FORWARD_CURE"
        plog(f"AUTO-PROMOTED {key} -> LIVE at {PROMOTED_LOT} lot "
             f"(shadow exp={st.get('exp_r', 0.0):.3f}R n={st.get('n', 0)} basis={basis})")
        changed = True

    # Retirement logic unchanged
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
            skey = s["name"]
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