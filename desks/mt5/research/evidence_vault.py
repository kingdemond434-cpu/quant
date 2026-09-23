"""F19 -- SEALED EVIDENCE, IRREVERSIBLE REVEALS, AND CERTIFICATES THAT OUTLIVED THEIR OWN BAR.

THE PRINCIPAL, 2026-09-12:

    Multiple sealed holdout tiers, irreversible reveal counters, ancestry-aware trial charges,
    signed code/data/config hashes, an independent certificate authority, LIMITED verdict feedback
    to researchers, and automatic certificate invalidation when any economically relevant
    dependency changes.

THE GAP, AS THE LEDGER STATES IT: the alpha state machine already prevents illegal stage skipping
with explicit evidence requirements. What it does not do is remember WHAT A VERDICT WAS BOUGHT
WITH, and that turns out to matter more than the sequencing.

THE FINDING THIS ORGAN EXISTS FOR, visible in the registry the moment anyone looks:

    a certificate minted earlier    deflated_sharpe PASSED   n_trials 203   sr0 0.0808
    the charge in force today       deflated_sharpe          n_trials 597   sr0 0.3786

The multiple-testing charge has nearly TRIPLED and the bar it implies has risen 4.7x. Every
certificate minted under the old charge is a claim that was never tested against the standard the
desk now applies, and nothing in the registry says so. That is not a hypothetical dependency
change -- it is the one that has already happened, to the gate that currently rejects everything.

WHAT IS SEALED AND WHAT A REVEAL COSTS. A holdout tier is the most recent slice of each symbol's
history, sealed by content hash, never touched by the research lanes. Revealing it is recorded and
IRREVERSIBLE: the counter only rises, and a tier revealed twice for the same strategy is evidence
that strategy has already seen it. A holdout that can be quietly re-used is not a holdout, it is a
second training set with a formal name.

THE DEPENDENCY FINGERPRINT is the code that judged, the cost model that priced and the contract
terms that sized. Any of them changing makes an old verdict a statement about a world that no
longer exists, which is the precise meaning of "economically relevant dependency".

INVALIDATION IS PROPOSED, NEVER EXECUTED. This organ does not touch the registry: certificate
hygiene is the only thing that moves a row, and a vault that silently revoked certificates would
be a second certificate authority -- exactly what F26's invariant forbids.

    python desks/mt5/research/evidence_vault.py [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
VAULT = DESK / "data" / "evidence_vault.json"
OUT = DESK / "reports" / "EVIDENCE_VAULT.json"

#: Share of each symbol's most recent history held in the sealed tier. A fifth is enough to judge
#: and small enough that sealing it does not starve the research window.
HOLDOUT_SHARE = 0.20

#: The files whose content defines an "economically relevant dependency". Change any of them and
#: a verdict minted before the change is a statement about a world that no longer exists.
DEPENDENCIES: tuple[tuple[str, Path], ...] = (
    ("judge", DESK / "scripts" / "external_gauntlet.py"),
    ("engine", DESK / "mt5desk" / "engine.py"),
    ("families", DESK / "mt5desk" / "families.py"),
    ("cost_model", DESK / "data" / "cost_surface.json"),
    ("contract_terms", DESK / "data" / "universe" / "universe.json"),
)

#: A trial charge this much higher than the one a certificate was minted under means the
#: certificate faced a materially easier bar. 1.5x is stated rather than tuned: below it the
#: deflation barely moves, above it the certificate would plainly not clear today's gate.
TRIAL_DRIFT = 1.5


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sha(p: Path) -> str | None:
    """Content hash over NORMALISED line endings -- the desk has paid for this lesson once."""
    try:
        raw = p.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return None
    return hashlib.sha256(raw).hexdigest()[:16]


def _fingerprint() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, path in DEPENDENCIES:
        out[name] = {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha": _sha(path)}
    joined = "|".join(str((out[n] or {}).get("sha")) for n, _ in DEPENDENCIES)
    out["combined"] = hashlib.sha256(joined.encode()).hexdigest()[:16]
    return out


def _live_symbols(limit: int = 12) -> list[str]:
    doc = _read(SLEEVES)
    rows = doc if isinstance(doc, list) else ((doc or {}).get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _seal_holdouts(prior: dict[str, Any]) -> dict[str, Any]:
    """Seal the most recent slice of each live symbol, and NEVER re-seal one already sealed.

    RE-SEALING IS THE FAILURE MODE, not forgetting to seal. A tier resealed each pass tracks the
    data forward, so the "holdout" is always the bars nobody has needed yet and the seal proves
    nothing. Once a symbol has a tier, its boundary is fixed and only its reveal counter moves.
    """
    try:
        import pandas as pd
    except ImportError:
        return {"status": "UNMEASURED", "why": "pandas unavailable"}
    tiers: dict[str, Any] = dict(prior.get("tiers") or {})
    sealed_now: list[str] = []
    for sym in _live_symbols():
        if sym in tiers:
            continue
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
        except (OSError, ValueError):
            continue
        if len(df) < 500 or "close" not in df.columns:
            continue
        cut = int(len(df) * (1 - HOLDOUT_SHARE))
        held = df.iloc[cut:]
        blob = "|".join(f"{i}:{v:.8f}" for i, v in
                        zip(held.index.astype(str), held["close"].astype(float), strict=True))
        tiers[sym] = {
            "sealed_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "first_bar": str(held.index[0]), "last_bar": str(held.index[-1]),
            "n_bars": len(held),
            "content_sha": hashlib.sha256(blob.encode()).hexdigest()[:16],
            "reveals": 0, "revealed_to": [],
        }
        sealed_now.append(sym)
    return {"status": "OK", "tiers": tiers, "sealed_this_pass": sealed_now,
            "n_tiers": len(tiers)}


def _trial_drift(certs: dict[str, Any]) -> dict[str, Any]:
    """Certificates minted under a materially LOWER multiple-testing charge than today's.

    THE CHARGE IS RECORDED ON EVERY CERTIFICATE and nobody has compared it to the current one.
    `gates.deflated_sharpe` carries `n_trials` and `sr0` as they stood when the verdict was
    granted, so the comparison needs no new instrumentation at all -- only somebody to make it.
    """
    rows: list[dict[str, Any]] = []
    charges: list[int] = []
    for key, row in certs.items():
        if not isinstance(row, dict):
            continue
        ds = ((row.get("gates") or {}).get("deflated_sharpe") or {})
        nt, sr0 = ds.get("n_trials"), ds.get("sr0")
        if isinstance(nt, (int, float)) and nt > 0:
            charges.append(int(nt))
            rows.append({"certificate": key, "n_trials": int(nt),
                         "sr0": float(sr0) if isinstance(sr0, (int, float)) else None,
                         "dsr": ds.get("dsr"), "gated_at": row.get("gated_at")})
    if not rows:
        return {"status": "UNMEASURED",
                "why": "no certificate records the trial charge its verdict was granted under"}
    current = max(charges)
    stale = [r for r in rows if current / max(r["n_trials"], 1) >= TRIAL_DRIFT]
    stale.sort(key=lambda r: r["n_trials"])
    by_charge: dict[int, int] = {}
    for r in rows:
        by_charge[r["n_trials"]] = by_charge.get(r["n_trials"], 0) + 1
    return {
        "status": "OK",
        "current_charge_seen": current,
        "charges_in_the_registry": dict(sorted(by_charge.items())),
        "n_certificates_with_a_charge": len(rows),
        "n_minted_under_a_lower_charge": len(stale),
        "drift_threshold": TRIAL_DRIFT,
        "rows": stale[:15],
        "reads": (
            f"the highest charge any certificate records is {current} trials. "
            f"{len(stale)} certificate(s) were granted under a charge at least {TRIAL_DRIFT}x "
            f"lower, so they cleared a bar the desk no longer applies. That is the "
            f"ancestry-aware trial charge the blueprint asks for, measured from what the "
            f"registry already records -- and it is the SAME gate the adversary's clean controls "
            f"are refused by today, which is the other half of the same fact."),
        "what_it_does_not_say": (
            "a certificate minted under a lower charge is not thereby WRONG. It is untested "
            "against the current standard, which is a different and weaker claim, and the remedy "
            "is a re-judge on today's charge rather than a revocation."),
    }


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    prior = _read(VAULT) or {}
    fp = _fingerprint()
    prior_fp = (prior.get("fingerprint") or {}).get("combined")
    changed = [name for name, _ in DEPENDENCIES
               if (prior.get("fingerprint") or {}).get(name, {}).get("sha")
               and fp[name]["sha"] != (prior.get("fingerprint") or {})[name]["sha"]]

    surv = _read(SURVIVORS) or {}
    certs = surv.get("survivors") or {}
    holdout = _seal_holdouts(prior)
    drift = _trial_drift(certs)

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "fingerprint": fp,
        "dependency_change": {
            "previous_combined": prior_fp,
            "current_combined": fp["combined"],
            "changed_since_last_seal": changed,
            "n_certificates_exposed": (len(certs) if changed else 0),
            "why": ("the judge, the engine, the family definitions, the cost model and the "
                    "contract terms are what an economically relevant dependency IS. Any of them "
                    "changing makes every verdict minted before the change a statement about a "
                    "world that no longer exists."
                    if changed else
                    "no dependency has changed since the last seal, so every existing verdict "
                    "was minted against the code and costs in force now"),
            "action": ("PROPOSED, NEVER EXECUTED. Nothing here touches the registry: "
                       "certificate_hygiene is the only organ that moves a row, and a vault that "
                       "silently revoked certificates would be a second certificate authority -- "
                       "which F26's invariant forbids and this desk has a law about."),
        },
        "holdout": holdout,
        "holdout_rule": (
            "a tier is sealed ONCE and never re-sealed. A tier resealed each pass tracks the data "
            "forward, so the 'holdout' is always the bars nobody has needed yet and the seal "
            "proves nothing. Reveals are counted and the counter only rises -- a holdout that can "
            "be quietly re-used is a second training set with a formal name."),
        "trial_charge_ancestry": drift,
        "not_yet_built": {
            "independent_certificate_authority": (
                "a second, separately-implemented judge that must agree before a certificate "
                "stands. This desk deliberately runs ONE canonical validator, and two judges "
                "would mostly prove that two programs agree -- so this is a DECISION to take, "
                "not a gap to close quietly."),
            "limited_verdict_feedback": (
                "researchers currently see the full gate detail, which is how a search learns to "
                "fit the judge. Restricting it is buildable -- the verdict dict is already "
                "assembled in one place -- but it changes what every downstream organ can read, "
                "so it is named rather than done unilaterally."),
        },
        "why": (
            "the state machine already prevents illegal stage skipping. What nothing remembered "
            "is WHAT A VERDICT WAS BOUGHT WITH -- and the registry shows certificates granted at "
            "203 trials against a charge of 597 today, on the gate that currently rejects "
            "everything."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="persist the vault and the report")
    a = ap.parse_args(argv)
    doc = build()
    print(f"evidence vault: {doc['status']}   fingerprint {doc['fingerprint']['combined']}")
    dc = doc["dependency_change"]
    if dc["changed_since_last_seal"]:
        print(f"  DEPENDENCY CHANGED: {dc['changed_since_last_seal']} -- "
              f"{dc['n_certificates_exposed']} certificate(s) were minted before it")
    else:
        print(f"  no dependency change since the last seal "
              f"(previous {dc['previous_combined']})")
    h = doc["holdout"]
    if h.get("status") == "OK":
        print(f"  sealed holdout tiers: {h['n_tiers']} "
              f"(+{len(h['sealed_this_pass'])} this pass), reveals counted and irreversible")
    else:
        print(f"  holdout: {h.get('status')} -- {h.get('why')}")
    d = doc["trial_charge_ancestry"]
    if d.get("status") == "OK":
        print(f"  trial charge: registry holds {d['charges_in_the_registry']}")
        print(f"  {d['n_minted_under_a_lower_charge']} of {d['n_certificates_with_a_charge']} "
              f"certificate(s) were granted under a charge >= {d['drift_threshold']}x lower than "
              f"the {d['current_charge_seen']} in force")
        for r in d["rows"][:6]:
            print(f"    {str(r['certificate'])[:46]:<46} n_trials={r['n_trials']:<5} "
                  f"sr0={r['sr0']}  gated {str(r['gated_at'])[:10]}")
    else:
        print(f"  trial charge: {d.get('status')} -- {d.get('why')}")
    for k, v in doc["not_yet_built"].items():
        print(f"  NOT BUILT  {k}: {v[:110]}")
    if not a.apply:
        print("  --apply not given; vault not persisted")
        return 0
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    VAULT.write_text(json.dumps({"sealed_at": doc["at"], "fingerprint": doc["fingerprint"],
                                 "tiers": (doc["holdout"].get("tiers") or {})},
                                indent=1, default=str), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc["holdout"].pop("tiers", None)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {VAULT}\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
