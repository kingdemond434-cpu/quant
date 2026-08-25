"""Auto-promotion / auto-retirement for shadow-validated sleeves.

Runs daily at 22:00 UTC inside the gateway loop (after shadow_forward.main()).

PROMOTE (fully automatic):
  - shadow verdict == PROMOTION CANDIDATE and not yet promoted:
    * XAUUSD challengers: promote only if their forward exp >= the armed gold
      sleeve's forward exp (live ledger, same window) - 0.02 margin; else KILL.
    * JPY-cross sleeves: promote directly at 3% base risk, gateway-sized and ramped.
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

from mt5desk import provenance
from shadow_admission import authorized_specs, power_cure_specs

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "promoter.log"

# SIZING (principal 2026-08-25): the gateway sizes promoted sleeves at order time -- 3% of
# equity base risk off the bracket's own stop distance (mt5desk/sizing.py), authority-ramped
# 0.75%/1.5%/3% by live trade count. Raising a sleeve's risk_frac above the base requires
# recorded economic justification and is capped at MAX_RISK_FRAC there.
PROMOTED_RISK_FRAC = 0.03
PROMOTED_LOT = 0.01     # legacy display value; sleeve_set() overrides lot to "auto_ramp"
CHAMPION_MARGIN = 0.02   # challenger must beat armed forward exp by this much
RETIRE_MIN_N = 10
RETIRE_MAX_DD = -25.0
RETIRE_MIN_EXP = 0.05

GOLD_WINDOWS = ["asia", "london_am", "ny_open", "afternoon"]


def _cure_thresholds() -> dict:
    """Forward-cure bar, read from the CANONICAL SPEC rather than restated here.

    Two copies of one threshold WILL drift, and the drift surfaces as a promotion nobody can
    explain against a policy nobody changed. gate_spec.yaml is the single source.
    """
    try:
        from gate_policy import get_promotion_thresholds
        th = get_promotion_thresholds().get("forward_cure_thresholds", {})
        if th:
            return th
    except Exception:
        pass
    return {"min_trades": 50, "min_exp_r": 0.05, "max_dd_r": -25.0, "min_days_active": 14}


CURE = _cure_thresholds()


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
    """Closed trades from the account THIS DESK IS CURRENTLY TRADING, and no others.

    THE FILE IS NOT ONE ACCOUNT'S HISTORY. The broker is switched by editing one line of
    data/terminal_path.txt, so the moment that points at a Fusion DEMO terminal, demo fills append
    to this same file -- and they are read below to RETIRE live sleeves and to judge gold
    challengers against the armed book. Demo fills are optimistic in exactly the dimension that
    matters (a demo server fills stops at the trigger with no slippage), so a sleeve could be kept
    alive by practice results, or a newly funded live account judged on demo history sitting above
    it in the file.

    Rows predating provenance match nothing and are excluded. That is a deliberate loss of
    history: the alternative is silently treating pre-switch trades as belonging to whatever
    account happens to be connected today, which is the defect itself.
    """
    if not LEDGER.exists():
        return []
    try:
        rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except Exception:
        return []
    try:
        import MetaTrader5 as mt5
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


def load_qquant_shadow() -> dict:
    """The qquant (hunt-certified) forward clock, kept in its own state file."""
    p = SHADOW_DIR / "qquant_shadow_state.json"
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_cert_specs() -> dict[str, dict]:
    """Certificate key -> published shadow_spec, exact policy only (fail closed)."""
    from gate_policy import all_ten_pass, is_exact_policy
    p = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
    try:
        certs = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not is_exact_policy(certs.get("gate_policy")):
        return {}
    out = {}
    for key, cert in (certs.get("survivors") or {}).items():
        if isinstance(cert, dict) and all_ten_pass(cert.get("gates")) \
                and isinstance(cert.get("shadow_spec"), dict):
            out[key] = cert["shadow_spec"]
    return out


def promote_generic(sleeves: list[dict], qshadow: dict, existing: set,
                    gate_authority: set) -> bool:
    """GAP 124: hunt-certified (qquant) candidates gain the same automatic door.

    A qquant sleeve promotes when its OWN Fusion-native forward clock says
    PROMOTION_CANDIDATE (the canon 50-trade / day-14-with-20 schedule lives in
    qquant_shadow.py, not re-derived here) AND its certificate's published
    shadow_spec is in the exact-policy authority set. The sleeve row carries
    exec="family_market": the gateway executes it through the family-executor
    path, which stays LOG-ONLY until data/GENERIC_EXEC_ENABLED exists -- wired
    end to end, armed by one explicit human act (LAWS §4).
    """
    changed = False
    cert_specs = load_cert_specs()
    for key, row in qshadow.items():
        if not isinstance(row, dict) or row.get("status") != "PROMOTION_CANDIDATE":
            continue
        if key in existing:
            continue
        spec = cert_specs.get(key)
        if not spec:
            plog(f"{key}: qquant PROMOTION_CANDIDATE but no exact-policy shadow_spec; refused")
            continue
        tup = (str(spec["symbol"]), str(spec["selector"]), spec.get("condition") or None,
               str(spec["family"]), spec.get("is_universe") is True)
        if tup not in gate_authority:
            row["status"] = "BLOCKED_UNIVERSAL_GATES"
            plog(f"{key}: qquant candidate refused -- spec not in exact-gate authority")
            changed = True
            continue
        sleeves.append({"name": key, "symbol": tup[0], "selector": tup[1],
                        "state": tup[2], "family": tup[3],
                        "side": str(spec.get("side", "LONG")).upper(),
                        "exec": "family_market",
                        "lot": "auto_ramp", "risk_frac": PROMOTED_RISK_FRAC,
                        "status": "LIVE",
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": row.get("exp_r", 0.0)})
        plog(f"AUTO-PROMOTED (generic) {key} -> LIVE at {PROMOTED_RISK_FRAC:.0%} base risk, "
             f"ramped, exec=family_market (shadow exp={row.get('exp_r', 0.0):.3f}R "
             f"n={row.get('n', 0)}) -- orders LOG-ONLY until data/GENERIC_EXEC_ENABLED")
        changed = True
    return changed


def main() -> None:
    shadow = load_shadow()
    sleeves = load_sleeves()
    ledger = load_ledger()
    existing = {s["name"] for s in sleeves}
    gate_authority = authorized_specs(BASE)
    cure_authority = power_cure_specs(BASE)
    changed = False

    qshadow = load_qquant_shadow()
    if promote_generic(sleeves, qshadow, existing, gate_authority):
        changed = True
        (SHADOW_DIR / "qquant_shadow_state.json").write_text(
            json.dumps(qshadow, indent=2), encoding="utf-8")

    for key, st in shadow.items():
        if not isinstance(st, dict):
            continue
        if st.get("status") != "PROMOTION CANDIDATE":
            continue
        if key in existing:
            continue
        # KEYS NOW CARRY AN OPTIONAL THIRD FIELD: "SYM.window" or "SYM.window.STATE".
        # `split(".", 1)` would have put "asia.FAILED_BREAK" into `win`, which then fails the
        # gateway's window whitelist and silently drops the sleeve -- a conditioned candidate
        # would sit in shadow forever, meeting every promotion criterion and never promoting,
        # with no error anywhere. Parsed explicitly instead.
        parts = key.split(".")
        sym, win = parts[0], parts[1]
        cond = parts[2] if len(parts) > 2 else None
        gate_spec = (sym, win, cond, "session_range_breakout", False)
        # POWER-CURE PATH (gate_spec.yaml: power_cure_via_forward = true). A sleeve that cleared
        # every VALIDITY gate and missed only POWER gates was sent to shadow PRECISELY so forward
        # evidence could settle it -- and until now it could complete that cure and still be
        # refused here for lacking a certificate it was never going to earn. The policy promised
        # a cure with no path to cash it (L1.46: a duty with no instrument is a wish).
        # Admission uses the SPEC'S OWN thresholds, which are STRICTER than the ordinary bar,
        # never looser: 50 trades AND >= 0.05R AND maxDD > -25R AND >= 14 days.
        if gate_spec not in gate_authority and gate_spec in cure_authority:
            fs = sleeve_forward_stats(ledger, key)
            if (fs["n"] >= CURE["min_trades"] and fs["exp"] >= CURE["min_exp_r"]
                    and fs["max_dd"] > CURE["max_dd_r"]
                    and int(st.get("days_active", 0)) >= CURE["min_days_active"]):
                plog(f"{key}: POWER-CURE MET -- all validity gates passed, power failure cured "
                     f"by forward evidence (n={fs['n']} exp={fs['exp']:.3f}R "
                     f"dd={fs['max_dd']:.1f}R days={st.get('days_active')})")
                gate_authority = gate_authority | {gate_spec}
            else:
                st["status"] = "POWER_CURE_PENDING"
                st["gate_reason"] = (
                    f"validity-clean, power failure curing: n={fs['n']}/{CURE['min_trades']} "
                    f"exp={fs['exp']:.3f}/{CURE['min_exp_r']}R "
                    f"days={st.get('days_active', 0)}/{CURE['min_days_active']}")
                plog(f"{key}: power cure accruing -- {st['gate_reason']}")
                changed = True
                continue
        if gate_spec not in gate_authority:
            st["status"] = "BLOCKED_UNIVERSAL_GATES"
            st["promotion_authority"] = False
            st["gate_reason"] = "missing exact original universal ten-gate pass"
            plog(f"{key}: live promotion refused -- no canonical ten-gate certificate")
            changed = True
            continue
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
                        # Carried through to the gateway, which refuses to trade a conditioned
                        # sleeve whose state it cannot confirm. Without this field the gateway
                        # would trade the UNCONDITIONED strategy under this sleeve's name.
                        "state": cond,
                        "lot": PROMOTED_LOT, "risk_frac": PROMOTED_RISK_FRAC,
                        "status": "LIVE",
                        "promoted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                        "shadow_exp": st.get("exp_r", 0.0)})
        plog(f"AUTO-PROMOTED {key} -> LIVE at {PROMOTED_RISK_FRAC:.0%} base risk, ramped "
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
            # THE SLEEVE'S NAME *IS* ITS SHADOW KEY -- it was written from `key` at promotion.
            # Rebuilding it from symbol+window silently dropped the state, so retiring
            # "CADJPY.asia.FAILED_BREAK" wrote KILL onto "CADJPY.asia": a different sleeve, also
            # in the shadow set, which had done nothing wrong. Meanwhile the conditioned sleeve
            # kept PROMOTION CANDIDATE, so the next run promoted it again -- the desk oscillating
            # promote/retire forever, against this module's own "never re-promoted" guarantee.
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
    except Exception:
        import traceback
        plog("promoter error: " + traceback.format_exc())
