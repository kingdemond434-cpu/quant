"""Regime/Decay monitor: live-ledger expectancy plus SHADOW-REPLAY wake evidence (GAP 130).

Reads live trades (data/live_ledger.jsonl, when present) and the per-sleeve shadow replay
ledgers (reports/shadow/ledger_*.json), computes trailing realized expectancy per sleeve, and
writes data/regime_state.json. The gateway kills new brackets for sleeves flagged
``hibernate`` (gateway.regime_hibernate); nothing here touches execution directly.

WHY SHADOW EVIDENCE IS LOAD-BEARING (gap register #130): a hibernated sleeve stops being
bracketed, stops trading, and stops producing LIVE rows -- so a monitor fed only by the live
ledger freezes at exactly the values that hibernated it and can never clear. The wake
therefore keys on the ZERO-CAPITAL SHADOW REPLAY, which keeps accruing while the sleeve is
dark (RESEARCH 6c: hibernation releases capital, never the clock). Wake threshold is the
existing WARN bar, giving a hibernate(-0.10)/wake(-0.05) hysteresis band keyed on the
economic condition, not on a rank cut.

Sleeve keys match gateway.regime_hibernate: ``SYM|window`` (live ledger tag, or shadow
ledger filename ``ledger_<SYM>_<window>.json``). Live-ledger rows tagged
``shadow|SYM|window`` are counted as shadow evidence for ``SYM|window`` -- the old parser
misfiled them all under ``shadow|SYM``, merging every session of a symbol into one
pseudo-sleeve.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
STATE = BASE / "data" / "regime_state.json"
WINDOW = 90
HIBERNATE_EXP = -0.10
WARN_EXP = -0.05
WAKE_EXP = WARN_EXP          # wake on the warn bar: hysteresis band, economically keyed
MIN_N = 30
DD_LIMIT_R = -25.0


def _window_stats(rs: list[float]) -> dict[str, Any]:
    rs = rs[-WINDOW:]
    n = len(rs)
    if not n:
        return {"n": 0, "exp_r": 0.0, "avg_win_r": 0.0, "avg_loss_r": 0.0, "max_dd_r": 0.0}
    exp = float(np.mean(rs))
    win = float(np.mean([x for x in rs if x > 0])) if any(x > 0 for x in rs) else 0.0
    loss = float(np.mean([x for x in rs if x < 0])) if any(x < 0 for x in rs) else 0.0
    cum = np.cumsum(rs)
    maxdd = float(min(cum[i] - cum[: i + 1].max() for i in range(n)))
    return {"n": n, "exp_r": round(exp, 4), "avg_win_r": round(win, 3),
            "avg_loss_r": round(loss, 3), "max_dd_r": round(maxdd, 1)}


def compute_state(live: dict[str, list[float]], shadow: dict[str, list[float]],
                  now: str) -> dict[str, Any]:
    """Pure core: per-sleeve stats + flag. Hibernate needs LIVE evidence; wake needs SHADOW."""
    state: dict[str, Any] = {"swept_at": now, "sleeves": {}}
    for sleeve in sorted(set(live) | set(shadow)):
        lv = _window_stats(live.get(sleeve, []))
        sh = _window_stats(shadow.get(sleeve, []))
        n, exp, maxdd = lv["n"], lv["exp_r"], lv["max_dd_r"]
        flag = "hibernate" if ((n >= MIN_N and exp < HIBERNATE_EXP)
                               or (n >= 10 and maxdd < DD_LIMIT_R)) else (
            "warn" if (n >= MIN_N and exp < WARN_EXP) else "ok")
        woke = False
        if flag == "hibernate" and sh["n"] >= MIN_N and sh["exp_r"] >= WAKE_EXP:
            flag, woke = "ok", True
        row = dict(lv)
        row.update({"flag": flag, "shadow_n": sh["n"], "shadow_exp_r": sh["exp_r"],
                    "woke_on_shadow": woke})
        state["sleeves"][sleeve] = row
    return state


def _read_live(path: Path) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """live ledger -> (live rows by sleeve, shadow-tagged rows by PARENT sleeve)."""
    live: dict[str, list[float]] = {}
    shadow: dict[str, list[float]] = {}
    if not path.exists():
        return live, shadow
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if "r_multiple" not in r:
            continue
        parts = str(r.get("tag", "")).split("|")
        if parts and parts[0] == "shadow":
            if len(parts) >= 3:
                shadow.setdefault(f"{parts[1]}|{parts[2]}", []).append(float(r["r_multiple"]))
        elif len(parts) >= 2:
            live.setdefault(f"{parts[0]}|{parts[1]}", []).append(float(r["r_multiple"]))
    return live, shadow


def _read_shadow_ledgers(shadow_dir: Path) -> dict[str, list[float]]:
    """reports/shadow/ledger_<SYM>_<window>.json -> 'SYM|window' -> r_multiples (time order)."""
    out: dict[str, list[float]] = {}
    for p in sorted(shadow_dir.glob("ledger_*.json")):
        stem = p.stem[len("ledger_"):]
        sym, _, window = stem.partition("_")
        if not window:
            continue
        try:
            trades = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(trades, list):
            continue
        rows = [t for t in trades if isinstance(t, dict) and "r_multiple" in t]
        rows.sort(key=lambda t: str(t.get("exit_time", "")))
        out[f"{sym}|{window}"] = [float(t["r_multiple"]) for t in rows]
    return out


def main() -> None:
    live, shadow_from_live = _read_live(LIVE_LEDGER)
    shadow = _read_shadow_ledgers(SHADOW_DIR)
    for k, v in shadow_from_live.items():
        shadow.setdefault(k, []).extend(v)
    prev: dict[str, Any] = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8")).get("sleeves", {})
        except Exception:
            prev = {}
    state = compute_state(live, shadow, datetime.now(UTC).isoformat())
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    flags = {s: v["flag"] for s, v in state["sleeves"].items() if v["flag"] != "ok"}
    transitions = {s: f"{prev.get(s, {}).get('flag', 'new')}->{v['flag']}"
                   for s, v in state["sleeves"].items()
                   if prev.get(s, {}).get("flag") not in (None, v["flag"])}
    if flags or transitions:
        from mt5desk import gateway
        gateway.log(f"REGIME: flags={flags} transitions={transitions}")


if __name__ == "__main__":
    main()
