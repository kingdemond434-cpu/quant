"""Every dormant sleeve or window owes a forward clock -- or a re-judge that can give it one.

WHY (principal 2026-11-18 02:04Z, permanent: every account trades every market day). The gold
`london_am` and `afternoon` windows were zeroed on the live book (`decision_core.
GOLD_ASIA_ONLY_ZERO`) after their hunt6 cells failed PBO 0.5961 on 2026-08-26, and no forward
clock ran for either since. A sleeve with no clock produces no forward evidence, so the only door
back to capital -- a matured clock on a ten-gate certificate -- can never open for it: dormant
forever, by construction, while E8 went unfilled on 5 of 12 November market days.

WHAT A CLOCK IS HERE. Enrolment is a CERTIFICATE (RESEARCH section 6d, the one-pipeline law;
principal 2026-09-24 "unify the whole pipeline" deleted the non-certificate lane). So this organ
never starts a clock by hand. For every dormant row it measures one of:

  CLOCKED                 a forward clock runs for its exact identity -- nothing to do
  CERTIFIED_NOT_CLOCKED   it holds a certificate but no clock: the enrolment defect the
                          certificate-clock law fences; named here, repaired by shadow_forward
  QUEUED_FOR_REJUDGE      no certificate and no clock: its EXACT spec is on the gauntlet docket,
                          so the next sweep judges it under the attestation and costs in force; a
                          pass enrols the clock automatically (certified_sleeves), a fail is the
                          desk's measured answer, recorded where every verdict is
  UNRESOLVED              no spec this organ can state exactly -- never guessed; named with why

Dormant means a roster row that is STANDBY (reversible, zero risk) plus every gateway window the
live book zeroes by name. RETIRED rows are retirements on evidence and are counted, not swept.

Artifact: `reports/DORMANT_CLOCKS.json`. Clock: the hourly cycle's `dormant_clock_sweep` leg.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = DESK / "data" / "sleeves.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
OUT = DESK / "reports" / "DORMANT_CLOCKS.json"
SOURCE = "dormant_clock_sweep"
TAG_FIELD = "dormant_tag"
UNMEASURED = "UNMEASURED"
BREAKOUT = "session_range_breakout"
GOLD = "XAUUSD"

#: Gateway windows the live book zeroes by name, with the window each trades on. Read from
#: decision_core when it imports; this literal is only the fallback for a host that cannot.
_ZEROED_FALLBACK = {"gold_london_am": "london_am", "gold_afternoon": "afternoon"}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def zeroed_windows() -> dict[str, str]:
    """Gateway window name -> shadow window, for every gold window the live book zeroes."""
    try:
        from mt5desk.decision_core import GOLD_ASIA_ONLY_ZERO
        names = sorted(str(n) for n in GOLD_ASIA_ONLY_ZERO)
    except Exception:
        return dict(_ZEROED_FALLBACK)
    return {n: n.removeprefix("gold_") for n in names}


def _windows() -> dict[str, dict[str, Any]]:
    import shadow_forward as sf
    return {k: dict(v) for k, v in sf.WINDOWS.items()}


def _key(sym: str, win: str, params: dict[str, Any], fam: str, side: str = "LONG") -> str:
    import shadow_forward as sf
    return str(sf.sleeve_key(sym, win, params, fam, side))


def certificate_clock_keys() -> dict[str, str]:
    """certificate name -> the clock key the forward engine keys it by (same door, same rule)."""
    import shadow_forward as sf
    from shadow_admission import authorized_runs
    out: dict[str, str] = {}
    windows = _windows()
    for run in authorized_runs(DESK):
        fam = str(run.get("family") or BREAKOUT)
        params = dict(run.get("params") or {})
        if fam == BREAKOUT:
            if run.get("selector") not in windows:
                continue
            merged = dict(windows[run["selector"]])
            merged.update(params)
            params = merged
        side = sf._runnable_side(run, fam) or "LONG"
        out[str(run.get("certificate") or "")] = _key(
            str(run["symbol"]), str(run["selector"]), params, fam, side)
    return out


def _cell_id(sym: str, fam: str, params: dict[str, Any]) -> str:
    from research.frontier_identity import cell_id
    return str(cell_id({"sym": sym, "family": fam, "params": params}))


def docket_tags(path: Path) -> set[str] | None:
    """Every `dormant_tag` already on the docket (None when the docket cannot be read)."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return set()
    except OSError:
        return None
    import re
    return {m.decode("utf-8") for m in re.findall(rb'"dormant_tag"\s*:\s*"([^"]+)"', raw)}


def docket_row(target: dict[str, Any], now: datetime) -> dict[str, Any]:
    from libs.data.pit import stamp
    body = {
        "symbol": target["symbol"], "family": target["family"],
        "params": dict(target["params"]), "source": SOURCE, "producer": SOURCE,
        "priority": "DORMANT_WINDOW_REJUDGE", TAG_FIELD: target["cell_id"],
        "dormant_names": list(target["names"]),
        # Gate 1 reads this: the mechanism is the one the gateway already trades on the window.
        "mechanism_status": "NAMED",
        "mechanism_note": (f"re-judge of the dormant {target['symbol']} {target['window']} "
                           f"{target['family']} window the live book zeroes "
                           f"({', '.join(target['names'])}), at the gateway's exact params, under "
                           f"the attestation and costs in force; a pass enrols its forward clock"),
        "first_seen": now.isoformat(timespec="seconds"),
    }
    return stamp(body, SOURCE, now=now)


def build(now: datetime | None = None, *, sleeves: Any = None, shadow: Any = None,
          cert_keys: dict[str, str] | None = None,
          docket_present: set[str] | None = None) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    sl = _read(SLEEVES) if sleeves is None else sleeves
    sh = _read(SHADOW_STATE) if shadow is None else shadow
    rows = (sl.get("sleeves") if isinstance(sl, dict) else sl) if sl is not None else None
    if not isinstance(rows, list) or not isinstance(sh, dict):
        why = ("sleeves.json unreadable" if not isinstance(rows, list)
               else "shadow_state.json unreadable")
        return {"at": t.isoformat(timespec="seconds"), "status": UNMEASURED, "why": why,
                "rows": [], "targets": []}
    clocks = {k for k, v in sh.items() if isinstance(v, dict)}
    if cert_keys is None:
        try:
            cert_keys = certificate_clock_keys()
        except Exception as exc:
            cert_keys = {}
            cert_why = f"certificate keys unreadable ({type(exc).__name__})"
        else:
            cert_why = ""
    else:
        cert_why = ""
    windows = _windows()
    out_rows: list[dict[str, Any]] = []
    targets: dict[str, dict[str, Any]] = {}

    def window_target(name: str, sym: str, win: str) -> dict[str, Any]:
        params = dict(windows[win])
        key = _key(sym, win, params, BREAKOUT)
        if key in clocks:
            return {"name": name, "state": "CLOCKED", "clock": key}
        cid = _cell_id(sym, BREAKOUT, params)
        tg = targets.setdefault(cid, {"symbol": sym, "family": BREAKOUT, "window": win,
                                      "params": params, "cell_id": cid, "names": [],
                                      "clock_key": key})
        tg["names"].append(name)
        return {"name": name, "state": "QUEUED_FOR_REJUDGE", "clock_key": key, "cell_id": cid}

    for gw, win in sorted(zeroed_windows().items()):
        if win not in windows:
            out_rows.append({"name": gw, "kind": "zeroed_window", "state": "UNRESOLVED",
                             "why": f"window {win!r} has no shadow_forward.WINDOWS spec"})
            continue
        out_rows.append({"kind": "zeroed_window", **window_target(gw, GOLD, win)})
    n_retired = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        status = str(r.get("status") or "").upper()
        if status == "RETIRED":
            n_retired += 1
        if status != "STANDBY":
            continue
        name = str(r.get("name") or "")
        cert = r.get("certificate")
        cell = str(cert.get("cell") or "") if isinstance(cert, dict) else str(cert or "")
        if cell:
            key = cert_keys.get(cell)
            if key and key in clocks:
                out_rows.append({"name": name, "kind": "standby", "state": "CLOCKED",
                                 "clock": key, "certificate": cell})
            else:
                out_rows.append({"name": name, "kind": "standby",
                                 "state": "CERTIFIED_NOT_CLOCKED", "certificate": cell,
                                 "clock_key": key,
                                 "why": ((cert_why or "no authorized run for this certificate")
                                         if not key else "authorized, but no clock in "
                                         "shadow_state yet")})
            continue
        win = str(r.get("window") or r.get("selector") or "")
        sym = str(r.get("symbol") or "")
        if not r.get("family") and win in windows and sym == GOLD:
            out_rows.append({"kind": "standby", **window_target(name, sym, win)})
        else:
            out_rows.append({"name": name, "kind": "standby", "state": "UNRESOLVED",
                             "why": "no certificate and no gateway window spec to state exactly"})
    present = docket_present
    counts: dict[str, int] = {}
    for row in out_rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    tg_list = sorted(targets.values(), key=lambda x: x["cell_id"])
    for tg in tg_list:
        tg["on_docket"] = None if present is None else tg["cell_id"] in present
    return {
        "at": t.isoformat(timespec="seconds"), "status": "MEASURED",
        "counts": counts, "n_dormant": len(out_rows), "n_retired_not_swept": n_retired,
        "rows": out_rows, "targets": tg_list,
        "rule": ("every dormant sleeve or zeroed window holds a forward clock, or its exact spec "
                 "is on the gauntlet docket so a pass can give it one; no clock is ever started "
                 "without a certificate"),
    }


def apply(doc: dict[str, Any], now: datetime | None = None,
          docket: Path | None = None) -> dict[str, Any]:
    """Append every target not yet on the docket. Never removes, never rewrites a row."""
    path = docket or DOCKET
    t = now or datetime.now(UTC)
    targets = doc.get("targets") or []
    if not targets:
        return {"queued": 0}
    present = docket_tags(path)
    if present is None:
        return {"queued": 0, "refused": "docket unreadable; UNMEASURED, retried next pass"}
    missing = [x for x in targets if x["cell_id"] not in present]
    from attestation_remint import append_to_docket
    res = append_to_docket(path, [docket_row(x, t) for x in missing])
    queued_ok = not res.get("refused")
    missing_ids = {x["cell_id"] for x in missing}
    for x in targets:
        x["on_docket"] = x["cell_id"] in present or (x["cell_id"] in missing_ids and queued_ok)
    return {"queued": int(res.get("appended") or 0),
            "already_on_docket": len(targets) - len(missing),
            **({"refused": res["refused"]} if res.get("refused") else {})}


def write(doc: dict[str, Any], path: Path | None = None) -> None:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def main(argv: list[str] | None = None) -> int:
    doc = build()
    if doc.get("status") == "MEASURED":
        doc["docket"] = apply(doc)
    write(doc)
    c = doc.get("counts") or {}
    print(f"dormant_clock_sweep: {doc.get('n_dormant', 0)} dormant -- "
          + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))
          + (f"; docket {doc['docket']}" if doc.get("docket") else "")
          + (f" ({doc.get('why')})" if doc.get("status") != "MEASURED" else ""))
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
