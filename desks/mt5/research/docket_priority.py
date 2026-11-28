"""THE DOCKET PRIORITY LEG: originality (H2), cross-source agreement (H4) and information gain
(H5) over the judge's docket, in one streaming pass, every hour.

    python desks/mt5/research/docket_priority.py            # hourly leg `docket_priority`

Reads the one file the judge opens (`data/hypotheses/external_survivors.json`, streamed), the
certificate birth record and the sealed gauntlet's own verdicts. Writes three reports and one
lookup:

    reports/ORIGINALITY.json   H2: ORIGINAL / VARIANT / COPIED share of docket rows and
                               certificates, per producer, plus hypmax generator-collapse readings
    reports/CROSS_SOURCE.json  H4: independent sources agreeing on each row
    reports/INFO_GAIN.json     H5: expected information gain per (family, chart), i.e. per cell
    data/docket_priority.json  the compact lookup `judge_docket_order.priority_tilt` reads:
                               ORIGINAL cell keys, (symbol, family) agreement counts and the
                               information-gain scores (box-local, gitignored, rebuilt hourly)

NOTHING HERE TOUCHES A GATE. The lookup only reorders the judge's next docket inside a bounded
tilt (see `judge_docket_order.priority_tilt`), which changes which cells are warmed -- and so
judged -- first. Membership of the docket, the family trim and every verdict are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cross_source_synthesis as XS  # noqa: E402
import information_gain as IG  # noqa: E402
import originality_share as OS  # noqa: E402

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
CERTS = DESK / "data" / "certificate_provenance.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
GATES = DESK / "reports" / "universal_gates_external.json"
OUT_ORIGINALITY = DESK / "reports" / "ORIGINALITY.json"
OUT_CROSS = DESK / "reports" / "CROSS_SOURCE.json"
OUT_INFO = DESK / "reports" / "INFO_GAIN.json"
LOOKUP = DESK / "data" / "docket_priority.json"

#: Bumped when the lookup's shape changes; the reader ignores any other version.
LOOKUP_VERSION = 1


def norm_sym(sym: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(sym or "").upper())


def fold_params(row: dict[str, Any]) -> dict[str, Any]:
    """The params the judge keys a row by: the row's chart folded in (as `sealed_docket` does)."""
    params = dict(row.get("params") or {}) if isinstance(row.get("params"), dict) else {}
    row_tf = str(row.get("timeframe") or "").upper()
    if row_tf and row_tf != "H1" and "timeframe" not in params:
        params["timeframe"] = row_tf
    return params


def cell_key(sym: object, family: object, params: dict[str, Any]) -> str:
    """The lookup key both this leg and `judge_docket_order` compute for one cell."""
    raw = f"{norm_sym(sym)}.{family}.{json.dumps(params, sort_keys=True, default=str)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def mech_key(sym: object, family: object) -> str:
    return f"{norm_sym(sym)}|{family}"


def _rows(path: Path) -> Iterator[Any]:
    try:
        from libs.research.family_firing import iter_json_array
        yield from iter_json_array(path)
        return
    except ImportError:
        pass
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        doc = []
    yield from (doc if isinstance(doc, list) else [])


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:          # Windows: a reader holds the destination open
            time.sleep(0.2 * (attempt + 1))
    os.replace(tmp, path)


def _cell_id_fn() -> Any:
    try:
        from frontier_identity import cell_id
        return cell_id
    except Exception:
        return None


def _canon_specs(path: Path) -> dict[str, dict[str, Any]]:
    """cell -> shadow_spec from the certificate store (canon, else its published twin)."""
    out: dict[str, dict[str, Any]] = {}
    for p in (path, path.parents[1] / "reports" / "UNIVERSAL_SURVIVORS.json"):
        doc = _json(p)
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(surv, dict):
            for v in surv.values():
                if isinstance(v, dict) and isinstance(v.get("shadow_spec"), dict) and v.get("cell"):
                    out.setdefault(str(v["cell"]), v["shadow_spec"])
            if out:
                break
    return out


def _cert_fingerprint(cell: str, spec: dict[str, Any] | None,
                      orig: OS.Originality) -> tuple[str, str] | None:
    """(fingerprint, basis) for a certificate whose exact cell left the docket."""
    parts = cell.split(".")
    if len(parts) < 2:
        return None
    sym, fam = parts[0], parts[1]
    tf = sym.split("@", 1)[1].upper() if "@" in sym else "H1"
    if spec is not None and spec.get("family"):
        params = dict(spec.get("params") or {})
        params.setdefault("timeframe", tf)
        return OS.mechanism_fingerprint({"family": spec["family"], "params": params}), \
            "canon_spec"
    probe = OS.mechanism_fingerprint({"family": fam, "params": {"timeframe": tf}})
    head, tail = probe.split("|", 1)[0], probe.rsplit("|", 1)[1]
    same = [fp for fp in orig.birth if fp.startswith(head + "|") and fp.endswith("|" + tail)]
    if not same:
        return None
    if len(same) == 1:
        return same[0], "family_chart"
    # Several parameter shapes of the family on this chart: the mechanism's BIRTH on the chart
    # is the earliest of them, which is the question originality asks.
    return min(same, key=lambda fp: orig.birth[fp][:2]), "family_chart_birth"


def run(*, docket: Path = DOCKET, certs: Path = CERTS, gates: Path = GATES,
        canon: Path = CANON,
        out_originality: Path = OUT_ORIGINALITY, out_cross: Path = OUT_CROSS,
        out_info: Path = OUT_INFO, lookup: Path = LOOKUP,
        now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    stamp = now.isoformat(timespec="seconds")
    recent_cut = (now - timedelta(hours=24)).isoformat(timespec="seconds")
    orig = OS.Originality()
    cross = XS.CrossSource()
    cid_fn = _cell_id_fn()
    rows: list[tuple[str, str, str, str, str, str, str, int]] = []
    fam_tf: dict[tuple[str, str], int] = {}
    recent: dict[str, list[str]] = {}
    for r in _rows(docket):
        if not isinstance(r, dict) or not r.get("symbol") or not r.get("family"):
            continue
        params = fold_params(r)
        fam = str(r["family"])
        prod = OS.producer_of(r)
        fp = OS.mechanism_fingerprint(r)
        basis = OS.copy_basis(r)
        first = str(r.get("first_seen") or "")
        orig.observe_parts(fp, first, prod, bool(basis))
        ck = cell_key(r["symbol"], fam, params)
        cross.observe(r, ck)
        tf = OS.timeframe_of({"params": params})
        fam_tf[(fam, tf)] = fam_tf.get((fam, tf), 0) + 1
        if first and first >= recent_cut:
            recent.setdefault(prod, []).append(fp)
        cid = ""
        if cid_fn is not None:
            try:
                cid = str(cid_fn({"sym": r["symbol"], "family": fam, "params": params}))
            except Exception:
                cid = ""
        named = r.get("n_independent_sources")
        rows.append((prod, fp, basis, ck, mech_key(r["symbol"], fam), cid,
                     XS.mechanism_key(r), int(named) if isinstance(named, int) else 0))

    per_row_o: list[tuple[str, str, str, str]] = []
    per_row_x: list[tuple[int, int, int]] = []
    cell_class: dict[str, str] = {}
    original_keys: set[str] = set()
    mech_agree: dict[str, int] = {}
    for prod, fp, basis, ck, mk, cid, xmk, named in rows:
        cls, why = orig.classify_parts(fp, prod, basis)
        per_row_o.append((prod, cls, why, fp))
        if cid:
            prev = cell_class.get(cid)
            # one cell, several rows: ORIGINAL if any row of it is; COPIED only if all are
            if prev is None or cls == OS.ORIGINAL or (prev == OS.COPIED and cls == OS.VARIANT):
                cell_class[cid] = cls
        if cls == OS.ORIGINAL:
            original_keys.add(ck)
        nm = len(cross.by_mech.get(xmk, ()))
        per_row_x.append((nm, cross.n_cell(ck), named))
        if nm >= XS.AGREEMENT_MIN:
            mech_agree[mk] = max(mech_agree.get(mk, 0), nm)

    prior = _json(out_originality)
    cert_doc = _json(certs)
    records = cert_doc.get("records") if isinstance(cert_doc, dict) else None
    cert_basis: dict[str, int] = {}
    if isinstance(records, dict):
        specs = _canon_specs(canon)
        for cell, rec in records.items():
            if str(cell) in cell_class:
                cert_basis["exact_cell"] = cert_basis.get("exact_cell", 0) + 1
                continue
            fp = _cert_fingerprint(str(cell), specs.get(str(cell)), orig)
            if not fp:
                cert_basis["unmeasured"] = cert_basis.get("unmeasured", 0) + 1
                continue
            who = {"source": str((rec or {}).get("producer") or "?")} \
                if isinstance(rec, dict) else {"source": "?"}
            cls, _why = orig.classify_parts(fp[0], OS.producer_of(who), OS.copy_basis(who))
            cell_class[str(cell)] = cls
            cert_basis[fp[1]] = cert_basis.get(fp[1], 0) + 1
    o_doc = OS.report(per_row_o, certificates=records if isinstance(records, dict) else None,
                      cell_class=cell_class, recent_fps=recent,
                      prior=prior if isinstance(prior, dict) else None)
    if isinstance(o_doc.get("certificates"), dict) and cert_basis:
        o_doc["certificates"]["join"] = {
            **cert_basis,
            "rule": "exact_cell: the certificate's cell is on the docket and takes its row's "
                    "class; canon_spec: the certificate store's own family/params give the "
                    "fingerprint; family_chart: every docket fingerprint of that family and "
                    "chart is one fingerprint; family_chart_birth: the earliest-born of that "
                    "family's fingerprints on the chart; unmeasured: none of these reaches it"}
    if cid_fn is None and isinstance(o_doc.get("certificates"), dict):
        o_doc["certificates"] = {"status": "UNMEASURED",
                                 "why": "frontier_identity.cell_id not importable"}
    x_doc = XS.report(cross, per_row_x)

    gates_doc = _json(gates)
    verdicts = gates_doc.get("verdicts") if isinstance(gates_doc, dict) else None
    measured = isinstance(verdicts, list) and bool(verdicts)
    counts = IG.ruled_counts(verdicts if isinstance(verdicts, list) else [])
    table = IG.score_table(counts, fam_tf)
    i_doc = IG.report(table, measured=measured,
                      why="" if measured else f"{gates.name} absent or empty: every family "
                      "scores the same prior, so the blend moves nothing")

    head = {"at": stamp, "docket": str(docket.relative_to(ROOT)) if docket.is_relative_to(ROOT)
            else str(docket), "docket_rows": len(rows)}
    for path, doc in ((out_originality, o_doc), (out_cross, x_doc), (out_info, i_doc)):
        _atomic(path, {**head, **doc})
    _atomic(lookup, {
        "version": LOOKUP_VERSION, "at": stamp, "at_epoch": now.timestamp(),
        "rows": len(rows),
        "original": sorted(original_keys),
        "agreement": mech_agree,
        "info_gain": ({k: v["score"] for k, v in table["rows"].items()} if measured else {}),
        "info_gain_status": "MEASURED" if measured else "UNMEASURED",
        "key": "cell: sha1(SYM.family.json(params))[:16], SYM upper-alnum; agreement: "
               "SYM|family; info_gain: family|chart"})
    return {"rows": len(rows), "original_rows": o_doc["docket"]["totals"][OS.ORIGINAL],
            "share_original": o_doc["docket"]["share_original"],
            "rows_with_agreement": x_doc["rows_with_agreement"],
            "info_gain": i_doc["status"], "families_charts": i_doc["families_charts"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    t0 = time.time()
    out = run()
    print(f"docket_priority: {out['rows']} docket row(s); ORIGINAL {out['original_rows']} "
          f"(share {out['share_original']}); {out['rows_with_agreement']} row(s) with 2+ "
          f"independent sources; info gain {out['info_gain']} over {out['families_charts']} "
          f"(family, chart) row(s); {time.time() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
