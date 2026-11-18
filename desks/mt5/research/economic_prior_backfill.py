"""Economic-prior backfill: which families still owe the six-field EconomicPrior (H3).

Gate 1 (`frontier_identity.economic_prior`) now asks every NAMED cell for the six-field
`EconomicPrior` -- why the edge exists, why it might fail, why it might be overfit, why it might
decay, how decay is detected, what replaces it. Families on the 2026-11-18 grandfather roster keep
passing without one, so nothing already hunted or certified is cut by the new rule. This report is
the other half of that bargain: it names, every hour, the debt the grandfather path carries, so the
exemption is a measured backlog rather than a silent pass.

Per family it reads the prior from `desks/mt5/data/economic_priors.json` and says COMPLETE,
INCOMPLETE (with the missing fields) or UNMEASURED (no prior written), together with how many
docket rows, certificates and sleeves stand on it. It also counts docket rows that gate 1
records PRIOR_INCOMPLETE: a NAMED family off the roster with no complete prior.

THE SWITCH AND ITS EVIDENCE (Rule 1). PRIOR_INCOMPLETE is recorded, not binding, while
`data/ECONOMIC_PRIOR_MODE.json` reads SHADOW (the default). This organ is the only writer that
moves it, on a window declared here before any data is read: per forward clock in
reports/shadow/shadow_state.json with >= MIN_CLOCK_N forward observations, its forward exp_r,
split by whether the clock's family holds a complete prior. The statistic is the difference of
the two group means (complete minus incomplete) over the newest WINDOW clocks a side, with the
Welch SE. LIVE when mean - 2 SE > 0 with >= N_MIN clocks a side, SHADOW when mean + 1 SE < 0,
held in between; `"pinned": true` and OFF are left alone. Its missed-growth line -- what the
veto WOULD cost in SHADOW and does cost in LIVE -- is published on the report and carried into
MISSED_GROWTH.json by research/missed_growth.py.

Writes desks/mt5/reports/ECONOMIC_PRIOR_BACKFILL.json, and the switch only across a bar. Changes
no verdict already recorded, no certificate and no sleeve.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.family_firing import iter_json_array  # noqa: E402
from research.frontier_identity import (  # noqa: E402
    GRANDFATHERED_FAMILIES,
    PRIOR_INCOMPLETE,
    PRIOR_MODE_PATH,
    PRIOR_MODES,
    PRIOR_REGISTRY_PATH,
    economic_prior,
    prior_missing,
)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "ECONOMIC_PRIOR_BACKFILL.json"
CLOCKS = DESK / "reports" / "shadow" / "shadow_state.json"

#: THE PRE-DECLARED WINDOW. A clock counts once it holds MIN_CLOCK_N forward observations; each
#: side is read over its newest WINDOW clocks (by last entry) and needs N_MIN of them.
MIN_CLOCK_N = 10
N_MIN = 10
WINDOW = 200
#: Asymmetric bars, as every shadow-first gate on this desk: a strict one to start binding and a
#: looser one to stop, held in between.
PROMOTE_SE = 2.0
DEMOTE_SE = 1.0
EARNS, COSTS, UNMEASURED = "EARNS_ITS_PLACE", "COSTS_GROWTH", "UNMEASURED"
MODE_RULE = ("SHADOW records only: a NAMED cell of a family off the 2026-11-18 grandfather "
             "roster without a complete six-field EconomicPrior passes gate 1 as "
             "PRIOR_INCOMPLETE with its missing fields named. research/economic_prior_backfill.py "
             "writes LIVE (PRIOR_INCOMPLETE fails gate 1) when mean - 2 SE > 0 of the "
             "forward-clock difference (prior-complete minus prior-incomplete exp_r per clock) "
             f"over >= {N_MIN} clocks a side with >= {MIN_CLOCK_N} forward observations each "
             f"(newest {WINDOW} clocks a side), SHADOW when mean + 1 SE < 0, and leaves the mode "
             "alone in between. pinned=true freezes the mode; OFF stops the requirement.")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _docket_counts(path: Path) -> tuple[Counter[str], Counter[str], str]:
    """Rows per family, and gate-1 verdicts per family, streamed. UNMEASURED when unreadable."""
    rows: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    if not path.exists():
        return rows, verdicts, "UNMEASURED"
    try:
        for h in iter_json_array(path):
            if not isinstance(h, dict):
                continue
            fam = str(h.get("family") or "")
            rows[fam] += 1
            stage = economic_prior({"family": fam, "mechanism_status": h.get("mechanism_status"),
                                    "economic_prior": h.get("economic_prior")})
            verdicts[str(stage["verdict"])] += 1
    except (OSError, ValueError):
        return Counter(), Counter(), "UNMEASURED"
    return rows, verdicts, "MEASURED"


def _clock_family(key: str) -> str | None:
    """`SYM.family.session[#variant]` -> family; a two-part hunt key names none."""
    parts = key.split("#", 1)[0].split(".")
    return parts[1] if len(parts) >= 3 and parts[1] else None


def clock_rows(path: Path, complete: set[str]) -> tuple[list[dict[str, Any]], str]:
    """One row per forward clock old enough to count, tagged by its family's prior status."""
    doc = _read_json(path)
    if not isinstance(doc, dict):
        return [], "UNMEASURED"
    rows = []
    for key, st in doc.items():
        if not isinstance(st, dict):
            continue
        fam = _clock_family(str(key))
        n, exp = st.get("n"), st.get("exp_r")
        if (fam is None or not isinstance(n, (int, float)) or n < MIN_CLOCK_N
                or not isinstance(exp, (int, float)) or not math.isfinite(exp)):
            continue
        rows.append({"clock": key, "family": fam, "n": int(n), "exp_r": float(exp),
                     "last_entry": str(st.get("last_entry") or ""),
                     "prior_complete": fam in complete,
                     "grandfathered": fam in GRANDFATHERED_FAMILIES})
    return rows, "MEASURED"


def _side(rows: list[dict[str, Any]]) -> tuple[int, float | None, float | None]:
    recent = sorted(rows, key=lambda r: r["last_entry"])[-WINDOW:]
    vals = [r["exp_r"] for r in recent]
    n = len(vals)
    if n == 0:
        return 0, None, None
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1) if n > 1 else math.inf
    return n, mean, var


def evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """PROMOTE when (complete - incomplete) - 2 SE > 0, DEMOTE when + 1 SE < 0, else HOLD."""
    nc, mc, vc = _side([r for r in rows if r["prior_complete"]])
    ni, mi, vi = _side([r for r in rows if not r["prior_complete"]])
    out: dict[str, Any] = {
        "metric": "forward exp_r per clock, prior-complete minus prior-incomplete",
        "window": {"min_clock_n": MIN_CLOCK_N, "n_min_per_side": N_MIN, "newest": WINDOW},
        "bars": {"promote": f"mean - {PROMOTE_SE:g} SE > 0",
                 "demote": f"mean + {DEMOTE_SE:g} SE < 0", "between": "hold the current mode"},
        "n_complete": nc, "n_incomplete": ni,
        "mean_complete_r": None if mc is None else round(mc, 6),
        "mean_incomplete_r": None if mi is None else round(mi, 6)}
    if nc < N_MIN or ni < N_MIN or mc is None or mi is None or vc is None or vi is None:
        return {**out, "verdict": UNMEASURED, "action": "HOLD", "promote": False,
                "demote": False,
                "why": f"{nc} prior-complete and {ni} prior-incomplete clocks; {N_MIN} a side "
                       f"are needed before the requirement can bind"}
    diff = mc - mi
    se = math.sqrt(vc / nc + vi / ni)
    out.update(diff_r=round(diff, 6), se_r=round(se, 6),
               promote_bar_r=round(diff - PROMOTE_SE * se, 6),
               demote_bar_r=round(diff + DEMOTE_SE * se, 6))
    if diff + DEMOTE_SE * se < 0:
        return {**out, "verdict": COSTS, "action": "DEMOTE", "promote": False, "demote": True,
                "why": "prior-complete clocks earn less forward than prior-incomplete ones "
                       "(mean + 1 SE < 0): requiring the prior would cost growth"}
    if diff - PROMOTE_SE * se > 0:
        return {**out, "verdict": EARNS, "action": "PROMOTE", "promote": True, "demote": False,
                "why": "prior-complete clocks earn more forward (mean - 2 SE > 0): the "
                       "requirement selects what survives"}
    return {**out, "verdict": UNMEASURED, "action": "HOLD", "promote": False, "demote": False,
            "why": "inside the dead band (mean - 2 SE <= 0 <= mean + 1 SE): mode held"}


def read_mode(path: Path = PRIOR_MODE_PATH) -> tuple[str, dict[str, Any]]:
    doc = _read_json(path)
    doc = doc if isinstance(doc, dict) else {}
    mode = str(doc.get("mode") or "SHADOW").upper()
    return (mode if mode in PRIOR_MODES else "SHADOW"), doc


def move_switch(v: dict[str, Any], *, path: Path = PRIOR_MODE_PATH,
                write: bool = True) -> dict[str, Any]:
    """Move the switch only across a bar; hold inside the dead band. Pinned and OFF stay."""
    cur, doc = read_mode(path)
    if doc.get("pinned") or cur == "OFF":
        return {"mode": cur, "changed": False, "why": "pinned or OFF by the switch file"}
    want = ("LIVE" if v.get("promote") and cur != "LIVE"
            else "SHADOW" if v.get("demote") and cur == "LIVE" else cur)
    if want == cur:
        return {"mode": cur, "changed": False, "action": v.get("action", "HOLD")}
    if write:
        path.write_text(json.dumps({
            "mode": want, "set_by": "research/economic_prior_backfill.py",
            "at": datetime.now(tz=UTC).isoformat(), "rule": MODE_RULE,
            "evidence": {k: v.get(k) for k in ("n_complete", "n_incomplete", "diff_r", "se_r",
                                               "promote_bar_r", "demote_bar_r", "verdict",
                                               "action")}}, indent=1) + "\n", "utf-8")
    return {"mode": want, "changed": True, "from": cur, "action": v.get("action")}


def build(docket: Path = DOCKET, certs: Path = CERTS, sleeves: Path = SLEEVES,
          registry: Path = PRIOR_REGISTRY_PATH, clocks: Path = CLOCKS,
          mode_path: Path = PRIOR_MODE_PATH, write_switch: bool = False) -> dict[str, Any]:
    reg_doc = _read_json(registry)
    reg = (reg_doc or {}).get("families") if isinstance(reg_doc, dict) else None
    reg = reg if isinstance(reg, dict) else {}

    d_rows, d_verdicts, d_state = _docket_counts(docket)

    c_doc = _read_json(certs)
    cert_fams: Counter[str] = Counter()
    certs_state = "UNMEASURED"
    if isinstance(c_doc, dict) and isinstance(c_doc.get("survivors"), dict):
        certs_state = "MEASURED"
        for row in c_doc["survivors"].values():
            spec = (row or {}).get("shadow_spec") or {}
            cert_fams[str(spec.get("family") or (row or {}).get("family") or "")] += 1

    s_doc = _read_json(sleeves)
    sleeve_fams: Counter[str] = Counter()
    sleeves_state = "UNMEASURED"
    if isinstance(s_doc, dict) and isinstance(s_doc.get("sleeves"), list):
        sleeves_state = "MEASURED"
        for row in s_doc["sleeves"]:
            if isinstance(row, dict) and row.get("status") != "RETIRED":
                sleeve_fams[str(row.get("family") or "")] += 1

    families = sorted(set(GRANDFATHERED_FAMILIES) | set(reg) | set(d_rows) - {""})
    per_family: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for fam in families:
        prior = reg.get(fam) if isinstance(reg.get(fam), dict) else None
        missing = prior_missing(prior)
        status = "COMPLETE" if not missing else ("INCOMPLETE" if prior else "UNMEASURED")
        status_counts[status] += 1
        per_family.append({
            "family": fam, "status": status, "missing": missing,
            "grandfathered": fam in GRANDFATHERED_FAMILIES,
            "docket_rows": d_rows.get(fam, 0), "certificates": cert_fams.get(fam, 0),
            "sleeves_not_retired": sleeve_fams.get(fam, 0),
        })
    complete = {r["family"] for r in per_family if r["status"] == "COMPLETE"}
    clocks_rows, clocks_state = clock_rows(clocks, complete)
    ev = evidence(clocks_rows)
    mode = move_switch(ev, path=mode_path, write=write_switch)
    # THE MISSED-GROWTH LINE. What binding the requirement costs (LIVE) or would cost (SHADOW):
    # the docket rows it vetoes, and the forward R of clocks whose family it would refuse today.
    refused = [r for r in clocks_rows if not r["prior_complete"] and not r["grandfathered"]]
    now = datetime.now(UTC).isoformat()
    line = {"gate": "economic_prior_six_field", "at": now, "mode": mode["mode"],
            "binding": mode["mode"] == "LIVE",
            "verdict": ev["verdict"], "action": ev["action"],
            "docket_rows_vetoed_if_binding": d_verdicts.get(PRIOR_INCOMPLETE, 0),
            "forward_clocks_refused_if_binding": len(refused),
            "forward_r_per_trade_refused": (round(sum(r["exp_r"] for r in refused)
                                                  / len(refused), 6) if refused else None),
            **{k: ev.get(k) for k in ("n_complete", "n_incomplete", "diff_r", "se_r",
                                      "promote_bar_r", "demote_bar_r")},
            "why": ("forward exp_r per clock, prior-complete minus prior-incomplete; in SHADOW "
                    "it is what the requirement WOULD select, and nothing was vetoed. The "
                    "E[log W] price is UNMEASURED until a side carries a risk fraction.")}
    # Largest exposure first: the families whose prior would cover the most of the desk.
    per_family.sort(key=lambda r: (r["status"] == "COMPLETE", -r["docket_rows"],
                                   -r["certificates"], r["family"]))
    return {
        "schema": "economic_prior_backfill/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": "desks/mt5/research/economic_prior_backfill.py",
        "rule": ("gate 1 requires the six-field EconomicPrior of a NAMED cell; families on the "
                 "2026-11-18 grandfather roster pass without one (GRANDFATHERED_UNMEASURED) and "
                 "are listed here as backfill debt; any other family without a complete prior "
                 "is recorded PRIOR_INCOMPLETE"),
        "registry": (str(registry.relative_to(ROOT)) if registry.is_relative_to(ROOT)
                     else str(registry)),
        "grandfathered_families": len(GRANDFATHERED_FAMILIES),
        "family_status": dict(status_counts),
        "docket": {"state": d_state, "rows": sum(d_rows.values()),
                   "gate1_verdicts": dict(d_verdicts)},
        "mode": mode, "evidence": {**ev, "clocks_state": clocks_state,
                                   "clocks_counted": len(clocks_rows)},
        "missed_growth": [line],
        # THE ROSTER, AS A REPORT (never a gate): families the desk holds today that are not on
        # the frozen roster. Each is a new mechanism whose cells read PRIOR_INCOMPLETE.
        "held_off_roster": sorted(f for f in set(d_rows) | set(cert_fams) | set(sleeve_fams)
                                  if f and f not in GRANDFATHERED_FAMILIES),
        "certificates": {"state": certs_state, "n": sum(cert_fams.values())},
        "sleeves": {"state": sleeves_state, "not_retired": sum(sleeve_fams.values())},
        "families": per_family,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--docket", type=Path, default=DOCKET)
    args = ap.parse_args(argv)
    report = build(docket=args.docket, write_switch=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(f"economic_prior_backfill: families {report['family_status']}; docket "
          f"{report['docket']['state']} {report['docket']['rows']} rows, gate-1 verdicts "
          f"{report['docket']['gate1_verdicts']}; certificates {report['certificates']['n']}; "
          f"switch {report['mode']['mode']} ({report['evidence']['verdict']}: "
          f"{report['evidence']['why']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
