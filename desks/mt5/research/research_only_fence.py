"""RESEARCH-ONLY DATA NEVER SILENTLY BECOMES A PRODUCTION INPUT (DATA-38), measured every hour.

THE GAP. `libs/research/data_contract.py` records, per dataset, the acquisition method, the
licence, the `permitted_uses` and the provenance -- and `live_signal` is the use that means
"production". Nothing read that field at the moment it matters: a sleeve conditioned on a series
whose contract permits only `research`/`backtest` could be promoted, funded and traded, and no
fence would say so. The promoter, the allocator and the gateway are sealed, so the fence lives on
the research side and publishes what it finds; the sealed-side refusal is a patch under
/mnt/project-files/patches/ for the principal to apply.

WHAT IT WALKS, every pass, read from disk:

    data/sleeves.json                every LIVE or STANDBY row
      -> certificate.cell            the survivor row in reports/UNIVERSAL_SURVIVORS.json
      -> shadow_spec / own params    conditioner, source, required_data, dataset(s), condition
      -> dataset ids                 lake:<stem> / axis:<id> / acquired:<series> / bars:<SYM>
      -> the contract                data/feature_genome/contracts.json (the feature compiler's
                                     store), by exact id, then by the acquired series' host;
                                     broker bars by the compiler's declared `prices` contract

A DATASET IS PRODUCTION-ELIGIBLE when its contract lists `live_signal`, its recorded admission is
not refused, and -- for an acquired series -- the acquirer granted it PIT authority. Every other
input feeding a LIVE or STANDBY sleeve is a VIOLATION, by kind:

    RESEARCH_ONLY       the contract exists and does not permit live_signal
    INADMISSIBLE        the contract's own legality gate is shut
    NO_PIT_AUTHORITY    an acquired series the acquirer refused promotion authority
    UNCONTRACTED        no contract names the dataset: absence is not permission

A sleeve whose certificate cannot be resolved to a spec is UNMEASURED by name (the lineage is not
on this host), never a pass and never a violation.

    python desks/mt5/research/research_only_fence.py         -> reports/RESEARCH_ONLY_DATA.json
    python scripts/check_research_only_data.py               -> the same, exit 1 on a violation
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CONTRACTS = DESK / "data" / "feature_genome" / "contracts.json"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
REPORT = DESK / "reports" / "RESEARCH_ONLY_DATA.json"

UNMEASURED = "UNMEASURED"
PRODUCTION_USE = "live_signal"
GUARDED_STATUSES = ("LIVE", "STANDBY")
VIOLATION_KINDS = ("RESEARCH_ONLY", "INADMISSIBLE", "NO_PIT_AUTHORITY", "UNCONTRACTED")
_INPUT_KEYS = ("conditioner", "conditioners", "condition", "source", "dataset", "datasets",
               "axis", "required_data", "series")
_LAKE_PATH = re.compile(r"lake/series/([^/]+?)\.(?:parquet|csv|json)$")
_ACQ_PATH = re.compile(r"acquired/([^/]+?)\.parquet$")
_AXIS_PATH = re.compile(r"axes/([^/]+?)\.json$")
#: The qquant day states (side_channels/mech_battery.py): computed from the symbol's OWN bars
#: (range against its median), so a `condition` naming one is a price input, not a dataset.
PRICE_STATES = frozenset({"TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK"})
_PREFIXES = ("lake:", "axis:", "acquired:", "bars:", "claims:", "calendar:", "rule_state:",
             "representation:", "modality:")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def dataset_ids(value: Any) -> list[str]:
    """The dataset ids one declared input names. Never guesses past what the text says: an
    input it cannot place keeps its raw text under `conditioner:` and is judged UNCONTRACTED."""
    out: list[str] = []
    if value is None or value == "" or isinstance(value, (bool, int, float)):
        return out
    if isinstance(value, Mapping):
        for k in ("dataset", "series", "axis", "source", "conditioner", "path"):
            out.extend(dataset_ids(value.get(k)))
        return out
    if isinstance(value, (list, tuple, set)):
        for v in value:
            out.extend(dataset_ids(v))
        return out
    text = str(value).strip().replace("\\", "/")
    if text in PRICE_STATES:
        return []                                  # the sleeve's own bars, added by the caller
    for rx, prefix in ((_LAKE_PATH, "lake:"), (_ACQ_PATH, "acquired:"), (_AXIS_PATH, "axis:")):
        m = rx.search(text)
        if m:
            return [prefix + m.group(1)]
    if text.startswith("alt:"):                    # alt_proxies.conditioner_spec
        return ["lake:" + text[4:].split(":", 1)[0]]
    if text.startswith(_PREFIXES):
        head, _, rest = text.partition(":")
        return [f"{head}:{rest.split(':', 1)[0]}"]
    if "=" in text:                                # event_response_atlas "<axis>=<bucket>"
        return ["axis:" + text.split("=", 1)[0].strip()]
    if re.fullmatch(r"[A-Za-z0-9_.-]+", text):
        return ["lake:" + text]                    # a pack id: pack_cells reads lake/series/<id>
    return ["conditioner:" + text[:120]]


def spec_inputs(params: Mapping[str, Any] | None, extra: Mapping[str, Any] | None = None
                ) -> list[str]:
    """Every non-price dataset a spec conditions on, from its params and its own fields."""
    out: list[str] = []
    for src in (params or {}, extra or {}):
        if not isinstance(src, Mapping):
            continue
        for k in _INPUT_KEYS:
            if k in src and not (k == "source" and src is extra):
                out.extend(dataset_ids(src.get(k)))
        sym = src.get("input_symbol")
        if isinstance(sym, str) and sym:
            out.append(f"bars:{sym}")              # a cross-asset input is another symbol's bars
    return sorted(set(out))


def survivor_spec(sleeve: Mapping[str, Any], survivors: Mapping[str, Any]) -> dict[str, Any] | None:
    cert = sleeve.get("certificate")
    cell = str(cert.get("cell") or "") if isinstance(cert, Mapping) else ""
    if not cell:
        return None
    row = survivors.get(cell) or survivors.get(f"external.{cell}") or survivors.get(
        cell.removeprefix("external."))
    spec = row.get("shadow_spec") if isinstance(row, Mapping) else None
    return dict(spec) if isinstance(spec, Mapping) else None


def sleeve_lineage(sleeve: Mapping[str, Any], survivors: Mapping[str, Any]
                   ) -> tuple[list[str], str]:
    """(datasets this sleeve consumes, lineage basis). Broker bars for its own symbol always."""
    inputs = spec_inputs(sleeve.get("params") if isinstance(sleeve.get("params"), Mapping)
                         else None, sleeve)
    cert = sleeve.get("certificate")
    basis = "sleeve row (no certificate cell)"
    if isinstance(cert, Mapping) and cert.get("cell"):
        spec = survivor_spec(sleeve, survivors)
        if spec is None:
            basis = UNMEASURED
        else:
            inputs = sorted(set(inputs) | set(spec_inputs(spec.get("params")
                                                          if isinstance(spec.get("params"),
                                                                        Mapping) else None,
                                                          {"condition": spec.get("condition")})))
            basis = "certificate -> UNIVERSAL_SURVIVORS shadow_spec"
    sym = str(sleeve.get("symbol") or "")
    if sym:
        inputs = sorted(set(inputs) | {f"bars:{sym}"})
    return inputs, basis


def _prices_contract() -> dict[str, Any] | None:
    try:
        import feature_compiler as F
        base = dict(F.CONTRACT_BASE["prices"])
    except Exception:
        return None
    return {"contract": {"dataset_id": "modality:prices", **base,
                         "permitted_uses": list(base.get("permitted_uses") or ())},
            "admission": {"admitted": True}, "basis": "feature_compiler CONTRACT_BASE['prices']"}


def resolve_contract(ds: str, contracts: Mapping[str, Any], acquired: Mapping[str, Any],
                     prices: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The contract entry that governs `ds`, with the basis it was found on, or None."""
    row = contracts.get(ds)
    if isinstance(row, Mapping) and isinstance(row.get("contract"), Mapping):
        return {**row, "basis": f"contracts.json[{ds}]"}
    if ds.startswith("acquired:"):
        meta = (acquired.get("series") or {}).get(ds.split(":", 1)[1]) or {}
        host = str(meta.get("host") or "")
        row = contracts.get(f"acquired:{host}") if host else None
        if isinstance(row, Mapping) and isinstance(row.get("contract"), Mapping):
            return {**row, "basis": f"contracts.json[acquired:{host}] (the series' host)"}
    if ds.startswith("bars:") and prices is not None:
        return dict(prices)
    return None


def eligibility(ds: str, entry: Mapping[str, Any] | None,
                acquired: Mapping[str, Any]) -> dict[str, Any]:
    """Production eligibility of one dataset, with the violation kind when it is not."""
    if entry is None:
        return {"dataset": ds, "production_eligible": False, "violation": "UNCONTRACTED",
                "why": "no contract names this dataset; absence is not permission"}
    contract = entry.get("contract") or {}
    uses = [str(u) for u in (contract.get("permitted_uses") or [])]
    adm = entry.get("admission") if isinstance(entry.get("admission"), Mapping) else {}
    row: dict[str, Any] = {"dataset": ds, "contract_basis": entry.get("basis"),
                           "permitted_uses": uses,
                           "acquisition_method": contract.get("acquisition_method", UNMEASURED),
                           "licence": contract.get("licence_version", UNMEASURED),
                           "provenance": contract.get("provenance_state", UNMEASURED)}
    if PRODUCTION_USE not in uses:
        return {**row, "production_eligible": False, "violation": "RESEARCH_ONLY",
                "why": f"permitted_uses {uses} carries no {PRODUCTION_USE!r}"}
    if adm and adm.get("admitted") is False:
        return {**row, "production_eligible": False, "violation": "INADMISSIBLE",
                "why": "; ".join(str(r) for r in (adm.get("reasons") or [])[:3])
                or "the contract's legality gate is shut"}
    if ds.startswith("acquired:"):
        meta = (acquired.get("series") or {}).get(ds.split(":", 1)[1]) or {}
        if meta.get("pit_authority") is not True:
            return {**row, "production_eligible": False, "violation": "NO_PIT_AUTHORITY",
                    "why": ("the acquirer withheld PIT authority: "
                            + ", ".join(str(b) for b in (meta.get("pit_blocking") or [])[:3])
                            if meta else "the series is not in the acquired registry")}
    return {**row, "production_eligible": True, "violation": None}


def build(now: datetime | None = None, *, sleeves_path: Path = SLEEVES,
          survivors_path: Path = SURVIVORS, contracts_path: Path = CONTRACTS,
          acquired_path: Path = ACQUIRED) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sdoc = _read(sleeves_path, None)
    rows = sdoc.get("sleeves") if isinstance(sdoc, dict) else sdoc
    if isinstance(rows, dict):
        rows = [{"name": k, **v} for k, v in rows.items() if isinstance(v, dict)]
    base = {"measured_at": now.isoformat(timespec="seconds"),
            "law": "DATA-38: research-only data never silently becomes a production input",
            "production_use": PRODUCTION_USE, "guarded_statuses": list(GUARDED_STATUSES)}
    if not isinstance(rows, list):
        return {**base, "status": UNMEASURED, "why": f"{sleeves_path.name} unreadable",
                "violations": [], "n_violations": None}
    survivors_doc = _read(survivors_path, {})
    survivors = (survivors_doc.get("survivors") if isinstance(survivors_doc, dict) else None) or {}
    cdoc = _read(contracts_path, {})
    contracts = (cdoc.get("contracts") if isinstance(cdoc, dict) else None) or {}
    acquired = _read(acquired_path, {}) or {}
    prices = _prices_contract()
    per_sleeve: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    unresolved: list[str] = []
    eligible_cache: dict[str, dict[str, Any]] = {}
    for s in rows:
        if not isinstance(s, dict):
            continue
        status = str(s.get("status") or "").upper()
        if status not in GUARDED_STATUSES:
            continue
        name = str(s.get("name") or s.get("sleeve_id") or "")
        inputs, basis = sleeve_lineage(s, survivors)
        if basis == UNMEASURED:
            unresolved.append(name)
        verdicts = []
        for ds in inputs:
            if ds not in eligible_cache:
                eligible_cache[ds] = eligibility(
                    ds, resolve_contract(ds, contracts, acquired, prices), acquired)
            v = eligible_cache[ds]
            verdicts.append(v)
            if v["violation"]:
                violations.append({"sleeve": name, "status": status, "dataset": ds,
                                   "kind": v["violation"], "why": v["why"],
                                   "lineage": basis})
        per_sleeve.append({"sleeve": name, "status": status, "lineage": basis,
                           "inputs": inputs,
                           "non_price_inputs": [d for d in inputs if not d.startswith("bars:")],
                           "eligible": all(v["production_eligible"] for v in verdicts)})
    by_kind = {k: sum(1 for v in violations if v["kind"] == k) for k in VIOLATION_KINDS}
    return {
        **base,
        "status": "VIOLATION" if violations else "OK",
        "n_guarded_sleeves": len(per_sleeve),
        "n_violations": len(violations), "by_kind": by_kind,
        "violations": violations,
        "lineage_unmeasured": sorted(unresolved),
        "n_lineage_unmeasured": len(unresolved),
        "lineage_note": ("a sleeve whose certificate cell is not in UNIVERSAL_SURVIVORS on this "
                         "host has an unknown spec: UNMEASURED by name, never a pass"),
        "contracts_held": len(contracts),
        "datasets": sorted(eligible_cache.values(), key=lambda r: r["dataset"]),
        "sleeves": per_sleeve,
        "enforcement": ("research side: scripts/check_research_only_data.py fails the hourly box "
                        "gate on any violation; sealed side (promoter refusal) is the patch "
                        "/mnt/project-files/patches/data38_promoter_research_only.patch"),
    }


def eligibility_index(datasets: Iterable[str], *, contracts_path: Path = CONTRACTS,
                      acquired_path: Path = ACQUIRED) -> dict[str, dict[str, Any]]:
    """Production eligibility for any dataset ids -- the source ledger's door into this fence."""
    cdoc = _read(contracts_path, {})
    contracts = (cdoc.get("contracts") if isinstance(cdoc, dict) else None) or {}
    acquired = _read(acquired_path, {}) or {}
    prices = _prices_contract()
    return {ds: eligibility(ds, resolve_contract(ds, contracts, acquired, prices), acquired)
            for ds in datasets}


def write(doc: Mapping[str, Any], path: Path = REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main() -> int:
    doc = build()
    write(doc)
    print(f"research-only fence: {doc['status']}; {doc.get('n_guarded_sleeves')} LIVE/STANDBY "
          f"sleeve(s), {doc.get('n_violations')} violation(s) {doc.get('by_kind')}, "
          f"{doc.get('n_lineage_unmeasured')} lineage UNMEASURED -> {REPORT}")
    for v in doc.get("violations") or []:
        print(f"   VIOLATION {v['kind']:<16} {v['sleeve']} <- {v['dataset']}: {v['why'][:90]}")
    print("YIELD " + json.dumps({"targets": doc.get("n_violations") or 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
