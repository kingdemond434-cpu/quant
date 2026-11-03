"""THE TERMS-BASIS CENSUS -- does every certificate's input data stand on a quoted terms clause?
Report-only; regenerated every hour.

    python desks/mt5/research/terms_basis_census.py --once

WHY (IDEA_QUEUE row 233, 2026-10-21). Nothing checked that a cell's DATA carries a terms basis
before it trades. The fetch doors refuse an IDEAS_ONLY or held source at request time, but a
certificate minted on a series fetched before a row existed, or on a host with no row at all, was
never asked. This census asks, for every certificate on the canon, which datasets it reads and
what the ONE register says about each (libs/data/terms_fence.SOURCE_POLICY -- row 233 proposed a
second register; the auditor's one-register ruling stands, so there is none: every status read
here is a row of that table).

PER INPUT, ONE OF FOUR WORDS, AND NEVER A BLANK:

    OK                a row with a quoted clause from the source's own terms page and a status that
                      permits live input (API_PERMITTED with its key present, or PUBLIC_PAGE)
    NEEDS_KEY         a quoted, permitting row whose key is absent on THIS host
    REFUSED           the row says ideas only, or holds the route (IDEAS_ONLY, METHOD_BLOCKED,
                      a held route): the input should not be live data
    TERMS_UNMEASURED  no row, a row with no quoted clause, or an input this census cannot resolve
                      to a source -- never read as OK (fail closed, auditor ruling 2026-10-14)

A certificate's verdict is its WORST input (REFUSED > NEEDS_KEY > TERMS_UNMEASURED > OK). Every
certificate also trades on the broker's own MT5 bars; that input is named `mt5_broker` and read
from the register like any other, and `third_party_verdict` repeats the verdict without it, so a
broker-terms gap does not hide a third-party one.

HOW INPUTS ARE RESOLVED (declared, never guessed): the family's information source
(`axis_registry.classify_family`); explicit references on the recipe (`series_key` -> the world
dataset hunter's key map -> its provider's door; `conditioner` / `source` / `input_data`-style
fields -> `terms_fence.source_key` or the URL's row; `input_symbol` -> the broker); positioning
families -> the CFTC door. A non-price family with nothing resolvable is TERMS_UNMEASURED with
that reason.

Each non-OK input carries a missed-growth line (GROWTH GOVERNANCE): delta E[log W] UNMEASURED,
with its cause; a REFUSED input with a row reuses `terms_fence.held_missed_growth`.

Promotion reads nothing here yet: the auditor routes the verdict later (row 233). This organ only
measures.

Clock: `hourly_cycle:terms_basis_census` (department `meta`, layer `meta`).
Artifact: desks/mt5/reports/TERMS_BASIS_CENSUS.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402

REPORT = DESK / "reports" / "TERMS_BASIS_CENSUS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
WORLD_KEYS = DESK / "data" / "world_datasets" / "keys.json"
UNMEASURED = "UNMEASURED"
OK, NEEDS_KEY, REFUSED, TERMS_UNMEASURED = "OK", "NEEDS_KEY", "REFUSED", "TERMS_UNMEASURED"
SEVERITY = {OK: 0, TERMS_UNMEASURED: 1, NEEDS_KEY: 2, REFUSED: 3}
#: The broker's own feed (bars, ticks, swaps) every certificate trades on.
BROKER = "mt5_broker"
#: Recipe fields that name an input dataset or source.
REF_FIELDS = ("conditioner", "source", "data_source", "input_data", "input_source",
              "input_sources", "series_source", "feed", "url", "dataset")
#: Information sources (axis_registry) that read nothing beyond the broker's own feed.
BROKER_ONLY = frozenset({"price_only", "seasonality", "microstructure", "carry"})
#: World-hunter provider -> the door it reads when the dataset is not one of the direct specs.
PROVIDER_DOOR = {"DBNOMICS": "https://api.db.nomics.world/v22",
                 "BIS_BULK": "https://data.bis.org/static/bulk/",
                 "CFTC": "https://publicreporting.cftc.gov/resource/",
                 "TREASURY": "https://api.fiscaldata.treasury.gov/services/api/",
                 "FRED": "https://fred.stlouisfed.org/graph/fredgraph.csv",
                 "NOAA_CPC": "https://www.cpc.ncep.noaa.gov/", "EIA": "https://api.eia.gov/v2/"}
CFTC_DOOR = "https://publicreporting.cftc.gov/resource/"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def certificates() -> tuple[dict[str, dict[str, Any]], str]:
    """`{key: row}` from the canon, else its published twin, and which file was read."""
    for p in (CANON, SURVIVORS):
        doc = _read_json(p)
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(surv, dict) and surv:
            return {str(k): v for k, v in surv.items() if isinstance(v, dict)}, \
                p.relative_to(ROOT).as_posix()
    return {}, UNMEASURED


def basis_of_row(key: str | None) -> dict[str, Any]:
    """The register's answer for one policy row (None = no row)."""
    if not key:
        return {"policy_row": None, "status": "UNLISTED", "terms_state": tf.UNREAD,
                "basis": TERMS_UNMEASURED,
                "why": "no SOURCE_POLICY row: no quoted clause permits live input"}
    try:
        st = tf.live_input_status(key)
        ts = tf.terms_state(key)
    except KeyError:
        return {"policy_row": key, "status": UNMEASURED, "terms_state": tf.UNREAD,
                "basis": TERMS_UNMEASURED, "why": "row named but absent from the register"}
    row = tf.SOURCE_POLICY.get(key) or {}
    if st in (tf.IDEAS_ONLY, tf.METHOD_BLOCKED) or row.get("held_route"):
        basis, why = REFUSED, f"{st}: {row.get('why', '')}"[:240]
    elif ts != "READ":
        basis, why = TERMS_UNMEASURED, "row carries no quoted clause from its own terms page"
    elif st == tf.NEEDS_KEY:
        basis, why = NEEDS_KEY, "quoted and permitting, but its key is absent on this host"
    elif st in (tf.API_PERMITTED, tf.PUBLIC_PAGE):
        basis, why = OK, "quoted clause and a permitting status"
    else:
        basis, why = TERMS_UNMEASURED, f"status {st} is not a permitting status"
    return {"policy_row": key, "status": st, "terms_state": ts, "basis": basis, "why": why,
            "terms_url": (row.get("terms") or {}).get("url")}


def basis_of_ref(ref: str) -> dict[str, Any]:
    """A source NAME or URL -> its row's basis."""
    r = str(ref or "").strip()
    is_url = "://" in r or ("/" in r and "." in r.split("/")[0])
    key = tf.source_of_url(r) if is_url else tf.source_key(r)
    if not key and not is_url and r.startswith("alt:") and r.count(":") >= 1:
        key = tf.source_key(r.split(":")[1])
    return basis_of_row(key)


def _world_keys() -> dict[str, Any] | None:
    doc = _read_json(WORLD_KEYS)
    return doc if isinstance(doc, dict) else None


def _world_door(provider: str, dataset: str) -> str:
    try:
        from research.world_dataset_hunter import direct_sources
        for spec in direct_sources():
            if spec.get("provider") == provider and spec.get("dataset") == dataset:
                return str(spec.get("url") or "")
    except Exception:                                     # pragma: no cover - import guard
        pass
    return PROVIDER_DOOR.get(provider, PROVIDER_DOOR["DBNOMICS"])


def _classify(family: str) -> str:
    try:
        from research.axis_registry import classify_family
        return str(classify_family(family)[1])
    except Exception:                                     # pragma: no cover - import guard
        return "UNKNOWN"


def _spec(cert: dict[str, Any]) -> dict[str, Any]:
    raw = cert.get("shadow_spec")
    return raw if isinstance(raw, dict) else {}


def inputs_of(cert: dict[str, Any], *, world_keys: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The datasets one certificate reads, each with its basis. Declared resolution only."""
    spec = _spec(cert)
    sym = str(spec.get("symbol") or cert.get("sym") or "?")
    family = str(spec.get("family") or "?")
    raw = spec.get("params")
    params: dict[str, Any] = raw if isinstance(raw, dict) else {}
    info = _classify(family)
    out: list[dict[str, Any]] = [{"input": f"{BROKER}:{sym}", "kind": "broker_bars",
                                  **basis_of_ref(BROKER)}]
    seen_third = False
    other = params.get("input_symbol")
    if isinstance(other, str) and other and other != sym:
        out.append({"input": f"{BROKER}:{other}", "kind": "broker_bars", **basis_of_ref(BROKER)})
    sk = params.get("series_key")
    if isinstance(sk, str) and sk:
        seen_third = True
        if world_keys is None:
            out.append({"input": f"world:{sk}", "kind": "world_series",
                        **basis_of_row(None), "basis": TERMS_UNMEASURED,
                        "why": "world_datasets/keys.json absent on this host: the series' "
                               "provider cannot be resolved"})
        else:
            loc = world_keys.get(sk)
            if isinstance(loc, list) and len(loc) == 3:
                door = _world_door(str(loc[0]), str(loc[1]))
                out.append({"input": f"world:{loc[0]}/{loc[1]}/{loc[2]}", "kind": "world_series",
                            "door": door, **basis_of_ref(door)})
            else:
                out.append({"input": f"world:{sk}", "kind": "world_series",
                            **basis_of_row(None),
                            "why": "series_key absent from the hunter's key map"})
    for f in REF_FIELDS:
        v = params.get(f)
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            if isinstance(x, str) and x.strip():
                seen_third = True
                out.append({"input": f"{f}:{x[:120]}", "kind": "declared_ref", **basis_of_ref(x)})
    if not seen_third and info == "positioning":
        seen_third = True
        out.append({"input": "cftc_positioning", "kind": "family_default", "door": CFTC_DOOR,
                    **basis_of_ref(CFTC_DOOR)})
    if not seen_third and info not in BROKER_ONLY:
        out.append({"input": f"family:{family}", "kind": "unresolved", **basis_of_row(None),
                    "why": (f"family {family!r} reads {info} information and its recipe names "
                            "no resolvable input dataset")})
    return out


def _worst(rows: list[dict[str, Any]]) -> str:
    return max((r["basis"] for r in rows), key=lambda b: SEVERITY[b], default=TERMS_UNMEASURED)


def missed_growth(inp: dict[str, Any], cert_key: str) -> dict[str, Any]:
    key = inp.get("policy_row")
    if inp["basis"] == REFUSED and key and key in tf.SOURCE_POLICY:
        line = tf.held_missed_growth(key, source=inp["input"],
                                     live_input_refusal=not tf.held_on_terms(key))
    else:
        b = inp["basis"].lower()
        line = {"source": inp["input"], "kind": b if b.startswith("terms_") else f"terms_{b}",
                "policy_row": key, "delta_elogw": UNMEASURED,
                "cause": (f"{inp['basis']}: {inp.get('why', '')}; the growth at stake on this "
                          "input is UNMEASURED until its terms are quoted into its row")}
    line["certificate"] = cert_key
    return line


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    certs, read_from = certificates()
    wk = _world_keys()
    rows = []
    by_verdict: Counter[str] = Counter()
    by_third: Counter[str] = Counter()
    by_input: dict[str, Counter[str]] = {}
    lines = []
    for key in sorted(certs):
        cert = certs[key]
        ins = inputs_of(cert, world_keys=wk)
        third = [i for i in ins if i["kind"] != "broker_bars"]
        verdict = _worst(ins)
        tv = _worst(third) if third else "BROKER_ONLY"
        by_verdict[verdict] += 1
        by_third[tv] += 1
        for i in ins:
            name = i["policy_row"] or i["input"].split(":")[0]
            by_input.setdefault(name, Counter())[i["basis"]] += 1
            if i["basis"] != OK:
                lines.append(missed_growth(i, key))
        spec = _spec(cert)
        rows.append({"certificate": key, "symbol": spec.get("symbol") or cert.get("sym"),
                     "family": spec.get("family"), "verdict": verdict,
                     "third_party_verdict": tv, "inputs": ins})
    measured = bool(certs)
    # One missed-growth line per (input, basis): the same broker gap on 174 certificates is one
    # cause, not 174; the certificates it touches are counted on it.
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    for ln in lines:
        k = (str(ln.get("policy_row") or str(ln.get("source", "")).split(":")[0]),
             str(ln.get("kind")))
        a = agg.setdefault(k, {**{x: y for x, y in ln.items()
                                  if x not in ("certificate", "source")},
                               "input": k[0], "certificates": 0})
        a["certificates"] += 1
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/terms_basis_census.py",
        "leg": "hourly_cycle:terms_basis_census",
        "register": "libs/data/terms_fence.SOURCE_POLICY (the one register; no second table)",
        "rule": ("an input with no quoted clause from its own terms page is TERMS_UNMEASURED, "
                 "never OK; a certificate's verdict is its worst input; report-only"),
        "certificates_read_from": read_from,
        "world_keys": "present" if wk is not None else UNMEASURED,
        "summary": {
            "certificates": len(certs) if measured else UNMEASURED,
            "by_verdict": dict(by_verdict) if measured else UNMEASURED,
            "by_third_party_verdict": dict(by_third) if measured else UNMEASURED,
            "ok": by_verdict.get(OK, 0) if measured else UNMEASURED,
            "terms_unmeasured": by_verdict.get(TERMS_UNMEASURED, 0) if measured else UNMEASURED,
            "refused": by_verdict.get(REFUSED, 0) if measured else UNMEASURED,
        },
        "by_input": {k: dict(v) for k, v in sorted(by_input.items())},
        "missed_growth": sorted(agg.values(), key=lambda x: -x["certificates"]),
        "certificates": rows,
    }


def write(doc: dict[str, Any], path: Path = REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--out", default=str(REPORT))
    a = ap.parse_args(argv)
    doc = build()
    write(doc, Path(a.out))
    s = doc["summary"]
    print(f"terms_basis_census: {s['certificates']} certificates; verdicts {s['by_verdict']}; "
          f"third-party {s['by_third_party_verdict']} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
