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
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import provenance
from shadow_admission import authorized_specs

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "promoter.log"

#: A cross-process append collision on Windows clears in milliseconds. Six tries over ~0.5s
#: outlasts it; longer would be a promoter that waits on a log file, the wrong priority.
_LOG_RETRIES = 6
_LOG_RETRY_SLEEP_S = 0.03

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


def plog(msg: str) -> None:
    """Append one line to the promoter log. A locked log NEVER fails the promoter.

    WINDOWS LOCKS FILES EXCLUSIVELY AND THIS RUNS ON WINDOWS. Two processes appending collide, and
    the loser raised PermissionError out of `plog` -- called from inside the promotion pass, so a
    LOGGING collision aborted the PROMOTION. Measured 2026-09-03 on the desk box, every shadow
    cycle reported status FAILED with errors.promoter = PermissionError on promoter.log, a file
    that was writable, appendable and last modified a week earlier. The cycle had 43 sleeves with
    forward trades and zero evidence-blocked sleeves; the only thing that failed was note-taking.

    `print` happens first and unconditionally, so the line still reaches the cycle's captured
    output and nothing is lost -- a log the desk could not write is worth strictly less than a
    promotion it did not run.
    """
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    for attempt in range(_LOG_RETRIES):
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except (PermissionError, OSError):
            if attempt == _LOG_RETRIES - 1:
                return
            time.sleep(_LOG_RETRY_SLEEP_S * (attempt + 1))


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


#: The hardcoded live book, by the names gateway.sleeve_set() emits. Kept here rather than
#: imported because promoter runs on the research side and gateway imports MetaTrader5, which is
#: Windows-only; a wrong name here retires nothing rather than the wrong thing, and the names are
#: asserted against the gateway by tests/test_gold_retire_names.py.
GOLD_SLEEVE_NAMES = ("gold_asia", "gold_london_am", "gold_afternoon")

#: Windows the gateway must stop emitting. Absent file = nothing retired, which is the state the
#: desk has been in until now, so behaviour is unchanged until a rule actually fires.
GOLD_RETIRED_FILE = BASE / "data" / "GOLD_RETIRED.json"


def _load_gold_retired() -> dict:
    try:
        v = json.loads(GOLD_RETIRED_FILE.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_gold_retired(rows: dict) -> None:
    GOLD_RETIRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    GOLD_RETIRED_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def degenerate_evidence(ledger: list[dict], name: str) -> str:
    """Why this sleeve's r-series cannot support a retirement, or "" when it can.

    RETIRING IS AS CONSEQUENTIAL AS PROMOTING AND HAD NONE OF THE GUARDS. Measured 2026-09-01:
    gold_asia was auto-retired on n=30 with exp EXACTLY -1.000R, roll20 EXACTLY -1.000R and
    max_dd -29.0 -- thirty consecutive losses of precisely one R -- while the account those
    sleeves trade went 500.00 -> 603.84 on the same day, +103.84. Real trading does not produce
    thirty identical outcomes; a constant series is the signature of a broken r_multiple
    computation, and the ledger it was read from is not on either box now.

    A series with NO DISPERSION carries no information about performance. Acting on it is not
    conservative -- it stops a book on a bug, and the stop looks exactly like a verdict
    afterwards. So dispersion is required before any retire rule may fire. This does not soften
    a single threshold: a genuinely losing sleeve has losing trades of DIFFERENT sizes and still
    trips every rule below.
    """
    rs = [r.get("r_multiple") for r in ledger if r.get("sleeve") == name]
    rs = [float(x) for x in rs if isinstance(x, (int, float))]
    if len(rs) < 2:
        return ""
    if len({round(x, 9) for x in rs}) == 1:
        return (f"every one of {len(rs)} r_multiples is exactly {rs[0]:+.3f} -- a constant series "
                f"is a computation defect, not performance; refusing to retire on it")
    if all(x == 0.0 for x in rs):
        return f"all {len(rs)} r_multiples are 0.0 -- risk_per_lot was unmeasurable on every fill"
    return ""


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
        why_not = degenerate_evidence(ledger, s["name"])
        if why_not:
            plog(f"RETIRE-REFUSED {s['name']}: {why_not}")
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

    # ---------------------------------------------------------------- the gold book
    # THE ARMED GOLD BOOK NOW DECAYS LIKE EVERYTHING ELSE (principal, 2026-09-01). It used to be
    # exempt -- "The armed gold book is NOT managed here" -- because it predates the gauntlet and
    # is armed by a person. The consequence was that the desk's ONLY live sleeves were the only
    # ones with no automatic decay protection: the three retire rules below walked sleeves.json,
    # which is empty, so they applied to nothing that could actually lose money. A gold book whose
    # edge died would have degraded indefinitely with no organ able to notice.
    #
    # RETIREMENT HERE DOES NOT DELETE ANYTHING. It writes the window into data/GOLD_RETIRED.json
    # with its reason; gateway.sleeve_set() reads that file and stops emitting the window. Undo is
    # deleting the entry, which keeps re-arming a person's act exactly as it is today.
    #
    # SAFE BEFORE THE LEDGER FILLS: sleeve_forward_stats returns n=0/max_dd=0.0 for a sleeve with
    # no rows, and every rule below requires either n >= 10 or a drawdown worse than -25R, so an
    # empty or missing ledger retires nothing. It arms itself only once real fills are recorded.
    gold_retired = _load_gold_retired()
    for gname in GOLD_SLEEVE_NAMES:
        if gname in gold_retired:
            continue
        why_not = degenerate_evidence(ledger, gname)
        if why_not:
            plog(f"RETIRE-REFUSED {gname}: {why_not}")
            continue
        fs = sleeve_forward_stats(ledger, gname)
        retire = False
        reason = ""
        if fs["n"] >= RETIRE_MIN_N and fs["roll20_exp"] <= 0.0:
            retire, reason = True, f"roll20 exp {fs['roll20_exp']:.3f}R <= 0"
        elif fs["max_dd"] < RETIRE_MAX_DD:
            retire, reason = True, f"forward maxDD {fs['max_dd']:.1f}R < {RETIRE_MAX_DD}R"
        elif fs["n"] >= 50 and fs["exp"] < RETIRE_MIN_EXP:
            retire, reason = True, f"n={fs['n']} exp {fs['exp']:.3f}R < {RETIRE_MIN_EXP}R"
        if retire:
            gold_retired[gname] = {
                "retired_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "reason": reason, "n": fs["n"], "exp": fs["exp"],
                "roll20_exp": fs["roll20_exp"], "max_dd": fs["max_dd"]}
            _save_gold_retired(gold_retired)
            plog(f"AUTO-RETIRED {gname} ({reason}) -- gateway stops emitting this window")
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
