"""DECAY-AWARE REFIT TRIGGER -- when a live or forward cell's edge decays, or the regime breaks,
re-fit its learned model on the new state and send it back through the whole gauntlet.

THE ASK (GAP_MAP row 35, "decay-aware online refit, the CN shops' continuous retraining against
alpha decay"; it joins row 29, "regime-triggered model regeneration"): "when a live or forward
cell's measured edge decays (DECAY monitor) or a regime shift fires, re-fit the learned configs
and re-judge through the full gauntlet; never auto-arms, trials as set".

THE TWO HALVES.
  * In the model: `libs.models.learned_propagation` carries the refit schedule as a declared
    part of every learned model (REFIT_MODES): "clock" (the fixed 21-row walk), "regime" (refit
    the row after a panel vol-regime break, training from the break) and "decay" (a one-sided
    CUSUM on the model's own out-of-sample IC, its threshold calibrated to a declared false-alarm
    run length; refit from the change-point estimate). Every learned miner charges one "regime"
    and one "decay" configuration per model, so the schedules are searched like any other
    configuration and pay the multiple-testing bill.
  * Here, on the desk: every hour this organ reads which live and forward cells have DECAYED
    or sit in a BROKEN REGIME, and for each one whose family is a learned model it proposes the
    SAME certified spec with the event-driven schedule (`refit: "decay"` or `"regime"`) through
    the ordinary intake door (`proposer_common.donate`, seat `decay_refit`). The compiler takes it
    on the EXACT_RECIPE path, the gauntlet rules it from scratch, the trial is charged, and a
    survivor earns its own forward clock. Nothing here arms, sizes, promotes or retires anything.

TRIGGERS (each read point-in-time from its owner's artifact; an absent artifact is UNMEASURED):
  decay   live:    data/decay_live.json verdict FADE or RETIRE, or decay_regime class
                   STRUCTURAL_BREAK / PERSISTENT_BAD_REGIME (decay_monitor + decay_regime)
          forward: reports/shadow/shadow_state.json status KILL, or n >= DECAY_FWD_N with
                   forward_t <= 0 (the promotion arithmetic with the sign flipped)
          hazard:  reports/DRIFT.json hazard_by_sleeve verdict BREAKING (edge break ahead)
  regime  reports/DRIFT.json structure_verdict STRUCTURE_SHIFTED (every watched cell), or a
          per-symbol forecast hazard_max > DRIFT_Z (cells on that symbol)

A cell that triggers but whose family has NO declared refit schedule (every non-learned family
today) is not dropped: it is counted by family under `no_refit_schedule`, because "continuous
retraining" for a hand-specified rule is a parameter re-search and charges new trials -- a named
gap the report carries, never a silent skip.

DEDUPLICATION: one proposal per (cell, mode) per REPROPOSE_DAYS (data/decay_refit_ledger.jsonl,
gitignored, bounded), so a cell that stays decayed does not re-enter the docket every hour.

Outputs: reports/DECAY_REFIT.json (schema "decay-refit/1"); proposals in
data/intelligence/decay_refit/discoveries_*.json via the intake door.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
OUT = REPORTS / "DECAY_REFIT.json"
LEDGER = DESK / "data" / "decay_refit_ledger.jsonl"
DECAY_LIVE = DESK / "data" / "decay_live.json"
SLEEVES = DESK / "data" / "sleeves.json"
SHADOW = REPORTS / "shadow" / "shadow_state.json"
DRIFT = REPORTS / "DRIFT.json"
SCHEMA = "decay-refit/1"
SEAT = "decay_refit"

#: The learned families and the model each one runs (learned_miners.MINERS).
LEARNED_FAMILIES: dict[str, str] = {"gnn_propagation": "gnn", "attention_ts": "attention",
                                    "rocket_ts": "rocket", "sig_path": "signature",
                                    "ae_latent": "autoencoder"}
DECAY_VERDICTS = frozenset({"FADE", "RETIRE"})
DECAY_REGIME_CLASSES = frozenset({"STRUCTURAL_BREAK", "PERSISTENT_BAD_REGIME"})
DECAY_FWD_N = 20
DRIFT_Z = 2.0
REPROPOSE_DAYS = 30
FRESH_H = {"decay_live": 26.0, "shadow": 26.0, "drift": 26.0}
RETENTION_DAYS = 120
MAX_ROWS = 20_000
UNMEASURED = "UNMEASURED"


def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(UTC) if t.tzinfo else None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _read(path: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _fresh(doc: Mapping[str, Any] | None, keys: Sequence[str], now: datetime,
           limit_h: float) -> tuple[bool, str]:
    if doc is None:
        return False, "absent or unreadable"
    for k in keys:
        t = _ts(doc.get(k))
        if t is not None:
            age = (now - t).total_seconds() / 3600.0
            return (age <= limit_h,
                    f"{age:.1f} h old" + ("" if age <= limit_h else f" (limit {limit_h:.0f} h)"))
    return False, "unstamped"


# ------------------------------------------------------------------------------------ triggers
def live_decays(doc: Mapping[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, row in ((doc or {}).get("verdicts") or {}).items():
        if not isinstance(row, Mapping):
            continue
        v, cls = str(row.get("verdict") or ""), str(row.get("regime_class") or "")
        if v in DECAY_VERDICTS:
            out[str(name)] = f"live verdict {v}: {row.get('why') or ''}".strip()
        elif cls in DECAY_REGIME_CLASSES:
            out[str(name)] = f"live decay class {cls}: {row.get('regime_why') or ''}".strip()
    return out


def forward_decays(state: Mapping[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, st in (state or {}).items():
        if not isinstance(st, Mapping) or "n" not in st:
            continue
        status, n, t = str(st.get("status") or ""), _num(st.get("n")), _num(st.get("forward_t"))
        if status == "KILL":
            out[str(key)] = f"forward clock KILL (n={st.get('n')}, forward t={st.get('forward_t')})"
        elif n is not None and t is not None and n >= DECAY_FWD_N and t <= 0:
            out[str(key)] = f"forward edge absent: n={int(n)} forward t={t:+.2f} <= 0"
    return out


def drift_triggers(drift: Mapping[str, Any] | None) -> tuple[bool, dict[str, str], dict[str, str]]:
    """(book-wide regime shift?, regime-shifted symbols, sleeves whose edge break is ahead)."""
    if drift is None:
        return False, {}, {}
    book = str(drift.get("structure_verdict") or "") == "STRUCTURE_SHIFTED"
    syms: dict[str, str] = {}
    for sym, row in (drift.get("per_symbol") or {}).items():
        hz = _num((row or {}).get("hazard_max")) if isinstance(row, Mapping) else None
        if hz is not None and hz > DRIFT_Z:
            syms[str(sym)] = f"{sym} next-window hazard {hz:.2f} > {DRIFT_Z}"
    breaking: dict[str, str] = {}
    for name, row in (drift.get("hazard_by_sleeve") or {}).items():
        if isinstance(row, Mapping) and str(row.get("verdict") or "") == "BREAKING":
            breaking[str(name)] = (f"edge-break hazard BREAKING (P={row.get('hazard')}, "
                                   f"channel {row.get('leading_channel')})")
    return book, syms, breaking


# ------------------------------------------------------------------------------------ specs
def certified_specs() -> tuple[dict[str, dict[str, Any]], str]:
    """Clock key -> {symbol, family, params, side}, from the same fail-closed door the forward
    clocks enrol through (`shadow_admission.authorized_runs`, keyed by
    `shadow_forward.sleeve_key`)."""
    try:
        from research.shadow_admission import authorized_runs
        from research.shadow_forward import WINDOWS, sleeve_key
    except Exception as exc:
        return {}, f"spec door unimportable: {type(exc).__name__}"
    out: dict[str, dict[str, Any]] = {}
    try:
        for run in authorized_runs(DESK):
            fam = str(run.get("family") or "")
            params = dict(run.get("params") or {})
            if fam == "session_range_breakout":
                params = {**dict(WINDOWS.get(run["selector"], {})), **params}
            side = str(run.get("side") or run.get("direction") or "LONG").upper()
            key = sleeve_key(run["symbol"], run["selector"], params, fam, side)
            out[key] = {"symbol": run["symbol"], "family": fam, "params": params, "side": side,
                        "selector": run["selector"]}
    except Exception as exc:
        return out, f"spec door failed: {type(exc).__name__}"
    return out, f"{len(out)} certified spec(s)"


def live_specs(doc: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (doc or {}).get("sleeves") if isinstance(doc, Mapping) else None
    out: dict[str, dict[str, Any]] = {}
    for r in rows or []:
        if isinstance(r, Mapping) and isinstance(r.get("state"), Mapping) and r.get("family"):
            out[str(r.get("name"))] = {"symbol": r.get("symbol"), "family": r.get("family"),
                                       "params": dict(r["state"]),
                                       "side": str(r.get("side") or "LONG").upper(),
                                       "selector": r.get("selector")}
    return out


def family_from_key(key: str) -> str | None:
    """The family a clock key names (`SYM.family.window...`, shadow_forward.sleeve_key); a
    breakout key (`SYM.window`) names none and reads as session_range_breakout."""
    stem = key.split("#", 1)[0].split("@", 1)[0]
    parts = stem.split(".")
    if len(parts) >= 3:
        return parts[1]
    if len(parts) == 2:
        return "session_range_breakout"
    return None


# ------------------------------------------------------------------------------------ ledger
def load_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def recently_proposed(rows: Sequence[Mapping[str, Any]], now: datetime) -> set[tuple[str, str]]:
    cut = now - timedelta(days=REPROPOSE_DAYS)
    return {(str(r.get("cell")), str(r.get("mode"))) for r in rows
            if (t := _ts(r.get("at"))) is not None and t >= cut}


# ------------------------------------------------------------------------------------ plan
def plan(now: datetime, *, decay_live: Mapping[str, Any] | None,
         shadow: Mapping[str, Any] | None, drift: Mapping[str, Any] | None,
         specs: Mapping[str, Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]]
         ) -> dict[str, Any]:
    """Which cells trigger, in which mode, and what is proposed. Pure: no I/O."""
    inputs: dict[str, Any] = {}
    ok_live, why_live = _fresh(decay_live, ("checked_at", "at"), now, FRESH_H["decay_live"])
    ok_fwd, why_fwd = _fresh(shadow, ("updated_at", "last_run"), now, FRESH_H["shadow"])
    ok_drift, why_drift = _fresh(drift, ("generated_utc", "at"), now, FRESH_H["drift"])
    inputs = {"decay_live": {"fresh": ok_live, "why": why_live},
              "forward": {"fresh": ok_fwd, "why": why_fwd},
              "drift": {"fresh": ok_drift, "why": why_drift}}

    triggers: dict[tuple[str, str], list[str]] = {}

    def add(cell: str, mode: str, why: str) -> None:
        triggers.setdefault((cell, mode), []).append(why)

    if ok_live:
        for c, w in live_decays(decay_live).items():
            add(c, "decay", w)
    if ok_fwd:
        for c, w in forward_decays(shadow).items():
            add(c, "decay", w)
    book_shift, sym_shift, breaking = drift_triggers(drift if ok_drift else None)
    for c, w in breaking.items():
        add(c, "decay", w)
    watched = set(specs)
    if book_shift:
        for c in watched:
            add(c, "regime", "book correlation topology STRUCTURE_SHIFTED")
    for c in watched:
        sym = str((specs[c] or {}).get("symbol") or "")
        if sym in sym_shift:
            add(c, "regime", sym_shift[sym])

    seen = recently_proposed(ledger, now)
    proposals: list[dict[str, Any]] = []
    no_schedule: Counter[str] = Counter()
    unresolved: list[str] = []
    already: list[str] = []
    same_mode: list[str] = []
    for (cell, mode), whys in sorted(triggers.items()):
        spec = specs.get(cell)
        if spec is None:
            fam_guess = family_from_key(cell)
            if fam_guess and fam_guess not in LEARNED_FAMILIES:
                no_schedule[fam_guess] += 1     # counted by its key's family; spec not needed
            else:
                unresolved.append(cell)
            continue
        fam = str(spec.get("family") or "")
        if fam not in LEARNED_FAMILIES:
            no_schedule[fam or "?"] += 1
            continue
        params = dict(spec.get("params") or {})
        if str(params.get("refit", "clock")) == mode:
            same_mode.append(f"{cell}:{mode}")
            continue
        if (cell, mode) in seen:
            already.append(f"{cell}:{mode}")
            continue
        proposals.append({"cell": cell, "mode": mode, "family": fam,
                          "model": LEARNED_FAMILIES[fam], "symbol": spec.get("symbol"),
                          "params": {**params, "refit": mode}, "side": spec.get("side"),
                          "why": whys})
    status = ("MEASURED" if (ok_live or ok_fwd or ok_drift) else UNMEASURED)
    return {"status": status, "inputs": inputs,
            "triggered": {"decay": sum(m == "decay" for _c, m in triggers),
                          "regime": sum(m == "regime" for _c, m in triggers)},
            "regime": {"book_structure_shifted": book_shift, "symbols": sym_shift},
            "proposals": proposals,
            "no_refit_schedule": dict(no_schedule),
            "unresolved_spec": sorted(unresolved)[:50], "n_unresolved_spec": len(unresolved),
            "already_proposed": already[:50], "n_already_proposed": len(already),
            "already_on_that_schedule": same_mode[:50]}


def to_candidate(p: Mapping[str, Any]) -> dict[str, Any]:
    from research import proposer_common as pc
    sym, fam, mode = str(p["symbol"]), str(p["family"]), str(p["mode"])
    title = f"{sym}.{fam} refit={mode} (re-fit of decayed/regime-broken {p['cell']})"
    mech = (f"the certified {fam} model on {sym}, re-fitted on its {mode} schedule because its "
            f"forward/live edge {'decayed' if mode == 'decay' else 'faces a regime break'}: "
            + "; ".join(p.get("why") or []))
    c = pc.candidate(SEAT, sym, fam, dict(p["params"]), mechanism=mech, title=title,
                     evidence={"trigger": mode, "parent_cell": p["cell"],
                               "trigger_why": list(p.get("why") or []),
                               "tests_attempted": 1})
    c.update({"trial_family": f"{SEAT}:{fam}", "model_family": p["model"],
              "lineage": {"root": f"decay_refit:{p['cell']}", "parent_cell": p["cell"],
                          "novelty_key": f"{fam}|refit={mode}|{p['cell']}", "source": SEAT},
              "falsifier": ("the re-fitted schedule fails the same ten gates the parent passed, "
                            "or its forward clock reads t <= 0 at n >= 20"),
              "failure_mode_hypothesis": ("the decay was the mechanism dying, not the fit going "
                                          "stale: a refit then learns noise on the new rows")})
    return c


def _write_atomic(path: Path, text: str) -> None:
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(now: datetime | None = None, *, donate: bool = True, out: Path = OUT,
        ledger_path: Path = LEDGER) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    specs, spec_why = certified_specs()
    sleeves_doc = _read(SLEEVES)
    specs = {**specs, **live_specs(sleeves_doc)}
    ledger = load_ledger(ledger_path)
    doc = plan(now, decay_live=_read(DECAY_LIVE), shadow=_read(SHADOW), drift=_read(DRIFT),
               specs=specs, ledger=ledger)
    doc.update({"schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
                "specs": {"n": len(specs), "why": spec_why},
                "authority": ("none: proposals enter the intake like any miner's and are ruled by "
                              "the full gauntlet; nothing is armed, sized, promoted or retired")})
    donated: dict[str, Any] = {"donated": 0}
    if donate and doc["proposals"]:
        from research import proposer_common as pc
        cands = [to_candidate(p) for p in doc["proposals"]]
        path = pc.donate(SEAT, cands, tests_run=len(cands))
        donated = {**pc.donation_counts(), "path": None if path is None else path.name}
        if path is not None:
            cut = now - timedelta(days=RETENTION_DAYS)
            kept = [r for r in ledger if (t := _ts(r.get("at"))) is not None and t >= cut]
            kept += [{"at": doc["at"], "cell": p["cell"], "mode": p["mode"],
                      "family": p["family"], "file": path.name} for p in doc["proposals"]]
            _write_atomic(ledger_path, "".join(json.dumps(r, sort_keys=True) + "\n"
                                               for r in kept[-MAX_ROWS:]))
    doc["donation"] = {k: v for k, v in donated.items() if k != "refusals"}
    _write_atomic(out, json.dumps(doc, indent=1, default=str) + "\n")
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--no-donate", action="store_true", help="plan and report only")
    a = ap.parse_args(argv)
    try:
        doc = run(donate=not a.no_donate)
    except Exception as exc:          # a proposer never takes the cycle down
        print(f"decay refit trigger failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"decay refit: {doc['status']} -- triggered {doc['triggered']}, "
          f"{len(doc['proposals'])} proposal(s), no schedule {doc['no_refit_schedule']}, "
          f"donated {doc['donation'].get('donated', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
