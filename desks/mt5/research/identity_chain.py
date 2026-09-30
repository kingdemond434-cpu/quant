#!/usr/bin/env python3
"""THE IDENTITY CHAIN -- every live trade walked back to its raw data, and every link graded.

Item 1 of the principal's 2026-09-29 list asks that one immutable research identity survive
candidate -> gate -> certificate -> clock -> sleeve -> allocator -> order -> fill -> P&L, with no
fuzzy join, no sleeve-name matching and no recomputed identity, so that any trade can be
reconstructed years later. The arithmetic is `libs/research/trade_identity.py`; this organ applies
it to the desk's own records and MEASURES how much of the live book the chain actually reaches.

WHAT IT DOES, per live deal in `data/live_ledger.jsonl`:

    fill -> order          the deal's `entry_order` / `position_id` / `order` against the ticket
                           recorded in `order_intents.jsonl` or `decision_ledger.jsonl`. EXACT
                           when an integer ticket matches; BROKEN when the deal names an order
                           no journal recorded.
    fill -> sleeve         the deal's `sleeve` field against `data/sleeves.json` names. That field
                           is the ORDER COMMENT read back from the venue -- `gateway.order_comment`
                           = "DW" + name, truncated to the terminal's comment bound -- so a long
                           name comes back as a prefix. EXACT on equality (or through an exactly
                           joined order), FUZZY on a unique prefix, BROKEN when the prefix is
                           shared, the sleeve left the roster, or the broker overwrote the
                           comment ("[sl 0.94555]", "[tp 4360.71]").
    sleeve -> certificate  the sleeve row's `certificate.cell` as a key of the canon. EXACT or
                           BROKEN ("forward_clock", null).
    certificate -> clock   `trade_identity.spec_hash` of the certificate's shadow_spec against the
                           same hash of every forward-clock identity in `sleeve_registry.json`.
                           CONTENT when exactly one clock carries it; FUZZY when several do.
    sleeve -> allocation   the key the promoter RECORDED joining the sleeve to the allocator on
                           (`admission.joined` in sleeves.json). EXACT when that key is the sleeve's
                           own name; FUZZY when it is a composite `sym|family|selector` several
                           sleeves share; BROKEN when no allocator row answered.
    clock -> raw data      the `<SYMBOL>_<TF>.parquet` digest in `data/input_identity.json`.

Then it builds the content-addressed chain (raw_data -> transformation -> hypothesis ->
experiment -> certificate -> clock -> sleeve -> allocation -> order -> fill -> pnl) over the nodes
it could resolve, and appends ONE row per newly-seen deal to `data/identity_chain.jsonl` with
every node's payload and hash -- so the trade is reconstructable from that row alone after the
roster, the canon and the registry have all moved on. Rows are hash-chained (`row_hash =
sha256(prev_row_hash + canonical(row))`), append-only, never rewritten.

THE MEASUREMENT is `clean_fraction`: deals whose every required link is EXACT or CONTENT, over
all live deals. It is published beside the per-link break table, and it RATCHETS: the report
carries the high-water mark, and `--check` exits 1 when the fraction falls below it.

WHAT IT MAY NOT DO. It reads records and writes its own two files. It changes no order comment,
no sleeve, no allocation and no gateway path: carrying the chain head on the order (the natural
fix for the fill -> sleeve break) would change what the gateway SENDS, and that is the
principal's call. `PROPOSED_ORDER_TAG` below names it; the gateway now carries it (2026-09-30).

    python desks/mt5/research/identity_chain.py --once          # measure, append, write report
    python desks/mt5/research/identity_chain.py --trade 200224334   # reconstruct one deal
    python desks/mt5/research/identity_chain.py --check         # rc=1 if clean_fraction fell
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import trade_identity as ti  # noqa: E402

DATA = DESK / "data"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
INTENTS = DATA / "order_intents.jsonl"
DECISIONS = DATA / "decision_ledger.jsonl"
SLEEVES = DATA / "sleeves.json"
REGISTRY = DATA / "sleeve_registry.json"
CANON = DATA / "UNIVERSAL_SURVIVORS.canon.json"
INPUT_IDENTITY = DATA / "input_identity.json"
LEDGER = DATA / "identity_chain.jsonl"
REPORT = DESK / "reports" / "IDENTITY_CHAIN.json"

#: The links a trade must cross to be reconstructable end to end. Every one must be EXACT or
#: CONTENT for the trade to count as clean.
REQUIRED_LINKS: tuple[str, ...] = (
    "fill->order", "fill->sleeve", "sleeve->allocation", "sleeve->certificate",
    "certificate->clock", "clock->raw_data",
)

#: ON (blueprint identity chain, 2026-09-30). The gateway sends `trade_identity.tag(head)` of the
#: order's pre-trade chain in the order comment (`decision_core.tagged_comment`: 16 characters of
#: `DW<name>`, `#`, the 12-hex tag), records tag -> sleeve in `data/order_tags.json` and the
#: head and node hashes on the intent row, and stamps the fill's ledger row with `order_tag`.
#: This organ does not read the flag; it names the switch's state in code.
PROPOSED_ORDER_TAG = True

_BROKER_COMMENT = re.compile(r"^\[(sl|tp|so)\b", re.I)


# ------------------------------------------------------------------------------ readers
def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _int(x: Any) -> int | None:
    try:
        v = int(x)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


class Sources:
    """Every record the chain is resolved against, read once. Paths are injectable for tests."""

    def __init__(self, *, live_ledger: Path = LIVE_LEDGER, intents: Path = INTENTS,
                 decisions: Path = DECISIONS, sleeves: Path = SLEEVES,
                 registry: Path = REGISTRY, canon: Path = CANON,
                 input_identity: Path = INPUT_IDENTITY) -> None:
        self.deals = _jsonl(live_ledger)
        self.orders: dict[int, dict[str, Any]] = {}
        for src, rows in (("order_intents", _jsonl(intents)),
                          ("decision_ledger", _jsonl(decisions))):
            for r in rows:
                t = _int(r.get("ticket"))
                if t is not None and t not in self.orders:
                    self.orders[t] = {**r, "_source": src}
        sl = _json(sleeves)
        rows = sl.get("sleeves") if isinstance(sl, dict) else None
        self.sleeves: dict[str, dict[str, Any]] = {
            str(r["name"]): r for r in (rows or []) if isinstance(r, dict) and r.get("name")}
        self.sleeves_read = rows is not None
        reg = _json(registry)
        self.clocks: dict[str, dict[str, Any]] = dict((reg or {}).get("sleeves") or {}) \
            if isinstance(reg, dict) else {}
        self.clocks_by_spec: dict[str, list[str]] = {}
        for key, row in self.clocks.items():
            ident = (row or {}).get("identity") if isinstance(row, dict) else None
            if isinstance(ident, dict):
                self.clocks_by_spec.setdefault(ti.spec_hash(ident), []).append(key)
        can = _json(canon)
        self.canon: dict[str, dict[str, Any]] = dict((can or {}).get("survivors") or {}) \
            if isinstance(can, dict) else {}
        self.gate_policy = (can or {}).get("gate_policy") if isinstance(can, dict) else None
        iid = _json(input_identity)
        self.inputs: dict[str, Any] = dict((iid or {}).get("files") or {}) \
            if isinstance(iid, dict) else {}
        self.inputs_rollup = (iid or {}).get("rollup") if isinstance(iid, dict) else None


# ------------------------------------------------------------------------------ the links
def _j(cls: str, why: str, **kw: Any) -> dict[str, Any]:
    return {"class": cls, "why": why, **kw}


def link_fill_order(deal: Mapping[str, Any], src: Sources) -> tuple[dict[str, Any], Any]:
    ids = [(k, _int(deal.get(k))) for k in ("entry_order", "position_id", "order")]
    ids = [(k, v) for k, v in ids if v is not None]
    if not ids:
        return _j(ti.UNMEASURED, "the deal carries no order ticket"), None
    for k, v in ids:
        o = src.orders.get(v)
        if o is not None:
            return _j(ti.EXACT, f"ticket {v} ({k}) recorded in {o['_source']}", ticket=v), o
    return _j(ti.BROKEN, "no order journal recorded tickets "
              + ", ".join(str(v) for _, v in ids)), None


def link_fill_sleeve(deal: Mapping[str, Any], order: Mapping[str, Any] | None,
                     src: Sources) -> tuple[dict[str, Any], str | None]:
    if not src.sleeves_read:
        return _j(ti.UNMEASURED, "sleeves.json unreadable"), None
    tag = str(deal.get("sleeve") or "")
    if tag in src.sleeves:
        return _j(ti.EXACT, "the deal's comment is the sleeve's full name"), tag
    if order is not None and str(order.get("sleeve") or "") in src.sleeves:
        name = str(order["sleeve"])
        return _j(ti.EXACT, "through the exactly-joined order's sleeve field"), name
    if not tag:
        return _j(ti.BROKEN, "the deal carries no comment"), None
    if _BROKER_COMMENT.match(tag):
        return _j(ti.BROKEN, f"the broker overwrote the order comment ({tag!r})"), None
    hits = [n for n in src.sleeves if n.startswith(tag)]
    if len(hits) == 1:
        return _j(ti.FUZZY, f"only a prefix match: the comment {tag!r} is the name truncated "
                  "to the venue's comment bound", matched=hits[0]), hits[0]
    if len(hits) > 1:
        return _j(ti.BROKEN, f"ambiguous: {len(hits)} sleeves start with {tag!r}",
                  candidates=sorted(hits)[:6]), None
    return _j(ti.BROKEN, f"no sleeve on the roster answers to {tag!r} (retired, renamed or "
              "never on this roster)"), None


def link_sleeve_certificate(sleeve: Mapping[str, Any], src: Sources
                            ) -> tuple[dict[str, Any], str | None]:
    cert = sleeve.get("certificate")
    if isinstance(cert, dict) and cert.get("cell"):
        cell = str(cert["cell"])
        if cell in src.canon:
            return _j(ti.EXACT, "certificate.cell is a canon key"), cell
        if not src.canon:
            return _j(ti.UNMEASURED, "canon unreadable"), None
        return _j(ti.BROKEN, f"certificate.cell {cell!r} is not in the canon (revoked or "
                  "evicted)"), None
    return _j(ti.BROKEN, f"the sleeve names no certificate (certificate={cert!r})"), None


def link_certificate_clock(cert_key: str, src: Sources) -> tuple[dict[str, Any], str | None]:
    rec = src.canon.get(cert_key) or {}
    spec = rec.get("shadow_spec")
    if not isinstance(spec, dict):
        return _j(ti.BROKEN, "the certificate carries no shadow_spec"), None
    if not src.clocks:
        return _j(ti.UNMEASURED, "sleeve_registry unreadable"), None
    h = ti.spec_hash(spec)
    keys = src.clocks_by_spec.get(h) or []
    if len(keys) == 1:
        return _j(ti.CONTENT, "one forward clock carries the certificate's spec hash",
                  spec_hash=h), keys[0]
    if len(keys) > 1:
        side = str(spec.get("side") or "").upper()
        same = [k for k in keys
                if str(((src.clocks[k] or {}).get("identity") or {}).get("direction") or "")
                .upper() == side] if side else []
        if len(same) == 1:
            return _j(ti.CONTENT, "the spec hash plus the certificate's own side", spec_hash=h,
                      ), same[0]
        return _j(ti.FUZZY, f"{len(keys)} forward clocks carry this spec hash",
                  spec_hash=h, candidates=sorted(keys)[:6]), sorted(keys)[0]
    return _j(ti.BROKEN, "no forward clock carries the certificate's spec hash",
              spec_hash=h), None


_JOINED = re.compile(r"joined on '([^']*)'")


def link_sleeve_allocation(name: str, sleeve: Mapping[str, Any]) -> tuple[dict[str, Any], Any]:
    adm = sleeve.get("admission") if isinstance(sleeve.get("admission"), dict) else {}
    joined = str((adm or {}).get("joined") or "")
    m = _JOINED.search(joined)
    if not joined:
        return _j(ti.UNMEASURED, "the promoter recorded no allocator join for this sleeve"), None
    if not m:
        return _j(ti.BROKEN, "no allocator row answered this sleeve", recorded=joined[:160]), None
    key = m.group(1)
    payload = {k: adm.get(k) for k in ("status", "risk_frac", "heat_earned", "allocator_heat",
                                       "delta_elogw_per_day", "joined")}
    payload["key"] = key
    if key == name:
        return _j(ti.EXACT, "the allocator row is keyed by the sleeve's own name", key=key), payload
    if key == name.lower():
        return _j(ti.FUZZY, "joined only after lower-casing the sleeve name", key=key), payload
    return _j(ti.FUZZY, f"joined on the composite key {key!r}, which every sleeve of that "
              "symbol/family/session shares", key=key), payload


def link_clock_data(clock: Mapping[str, Any] | None, src: Sources
                    ) -> tuple[dict[str, Any], Any]:
    ident = (clock or {}).get("identity") if isinstance(clock, dict) else None
    if not isinstance(ident, dict):
        return _j(ti.BROKEN, "no clock identity to name the bars"), None
    if not src.inputs:
        return _j(ti.UNMEASURED, "input_identity.json unreadable on this host"), None
    fname = f"{ident.get('symbol')}_{str(ident.get('timeframe') or 'H1').upper()}.parquet"
    row = src.inputs.get(fname)
    if not isinstance(row, dict):
        return _j(ti.BROKEN, f"{fname} is not in the input identity"), None
    return _j(ti.EXACT, f"{fname} digest in input_identity.json", file=fname), \
        {"file": fname, **{k: row.get(k) for k in ("sha", "bytes", "mtime")},
         "rollup": src.inputs_rollup}


# ------------------------------------------------------------------------------ one trade
_FILL_KEYS = ("deal", "order", "position_id", "entry_order", "entry_deal", "close_order",
              "time", "symbol", "side", "volume", "fill_price", "entry_price", "sl", "tp",
              "account", "server", "account_kind", "magic", "sleeve")
_PNL_KEYS = ("pl_quote", "commission", "swap", "r_multiple", "risk_quote",
             "r_unreconstructible", "contract_size")
_SLEEVE_KEYS = ("name", "symbol", "family", "selector", "timeframe", "session", "exec", "lot",
                "status", "risk_frac", "risk_frac_source", "sleeve_id", "params", "side",
                "stop_atr", "target_atr", "max_hold")


def resolve(deal: Mapping[str, Any], src: Sources) -> dict[str, Any]:
    """Walk one deal back to its raw data. Every link graded, every resolved node hashed."""
    joins: dict[str, dict[str, Any]] = {}
    nodes: dict[str, Any] = {
        "fill": {k: deal.get(k) for k in _FILL_KEYS},
        "pnl": {k: deal.get(k) for k in _PNL_KEYS},
    }
    joins["fill->order"], order = link_fill_order(deal, src)
    if order is not None:
        nodes["order"] = {k: v for k, v in order.items() if not str(k).startswith("_")}
    joins["fill->sleeve"], name = link_fill_sleeve(deal, order, src)
    sleeve = src.sleeves.get(name) if name else None
    cert_key = clock_key = None
    if sleeve is not None:
        nodes["sleeve"] = {k: sleeve.get(k) for k in _SLEEVE_KEYS if k in sleeve}
        joins["sleeve->allocation"], alloc = link_sleeve_allocation(str(name), sleeve)
        if alloc is not None:
            nodes["allocation"] = alloc
        joins["sleeve->certificate"], cert_key = link_sleeve_certificate(sleeve, src)
    else:
        for k in ("sleeve->allocation", "sleeve->certificate"):
            joins[k] = _j(ti.BROKEN, "no sleeve resolved, so nothing downstream of it can be")
    if cert_key is not None:
        rec = src.canon[cert_key]
        nodes["certificate"] = _certificate_node(cert_key, rec, src)
        spec = rec.get("shadow_spec") or {}
        nodes["hypothesis"] = {"spec_hash": ti.spec_hash(spec), "spec": spec}
        nodes["experiment"] = {
            "cert": cert_key, "hunt": rec.get("hunt"), "days": rec.get("days"),
            "gated_at": rec.get("gated_at"),
            "n_trials": ((rec.get("gates") or {}).get("deflated_sharpe") or {}).get("n_trials"),
            "gates": {g: {k: v for k, v in (s or {}).items() if k != "message"}
                      for g, s in (rec.get("gates") or {}).items() if isinstance(s, dict)},
            "gate_policy": src.gate_policy}
        joins["certificate->clock"], clock_key = link_certificate_clock(cert_key, src)
    else:
        joins["certificate->clock"] = _j(ti.BROKEN, "no certificate resolved")
    clock = src.clocks.get(clock_key) if clock_key else None
    if clock is not None:
        ident = dict(clock.get("identity") or {})
        nodes["clock"] = {"key": clock_key, "identity": ident,
                          "frozen_at": clock.get("frozen_at"),
                          "forward_start": clock.get("forward_start"),
                          "cost_fields": clock.get("cost_fields")}
        nodes["transformation"] = {k: ident.get(k) for k in
                                   ("code_hash", "behaviour_hash", "cost_hash", "data_venue")}
    joins["clock->raw_data"], data = link_clock_data(clock, src)
    if data is not None:
        nodes["raw_data"] = data
    ch = ti.chain(nodes)
    verdict = ti.classify(joins, REQUIRED_LINKS)
    return {"deal": _int(deal.get("deal")), "time": deal.get("time"),
            "symbol": deal.get("symbol"), "sleeve_tag": deal.get("sleeve"),
            "sleeve": name, "certificate": cert_key, "clock": clock_key,
            "verdict": verdict["verdict"], "weak_links": verdict["weak_links"],
            "joins": joins, "chain": ch, "tag": ti.tag(ch["head"]), "nodes": nodes}


def _certificate_node(cert_key: str, rec: Mapping[str, Any], src: Sources) -> dict[str, Any]:
    """The certificate's evidence-chain Merkle root when that module imports, else its record."""
    try:
        import evidence_chain
        m = evidence_chain.manifest(cert_key, dict(rec), dict(src.gate_policy or {}))
        return {"cert": cert_key, "merkle_root": m["merkle_root"],
                "leaves": {x["leaf"]: x["hash"] for x in m["leaves"]}}
    except Exception as exc:
        return {"cert": cert_key, "record_hash": ti.sha256(ti.canonical(dict(rec))),
                "basis": f"evidence_chain unavailable ({type(exc).__name__})"}


# ------------------------------------------------------------------------------ ledger
def ledger_rows(path: Path = LEDGER) -> list[dict[str, Any]]:
    return _jsonl(path)


def row_hash(prev: str, row: Mapping[str, Any]) -> str:
    body = {k: v for k, v in row.items() if k != "row_hash"}
    return ti.sha256(prev + ti.canonical(body))


def verify_ledger(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    prev = ti.GENESIS
    n = 0
    for i, r in enumerate(rows):
        if r.get("prev") != prev or row_hash(prev, r) != r.get("row_hash"):
            return {"verdict": "BROKEN", "at_row": i, "rows": n}
        prev = str(r["row_hash"])
        n += 1
    return {"verdict": "INTACT", "rows": n, "head": prev}


def append_new(results: Iterable[Mapping[str, Any]], path: Path = LEDGER) -> int:
    """One row per deal never recorded before. Append-only; the chain links every row."""
    rows = ledger_rows(path)
    seen = {r.get("deal") for r in rows}
    prev = str(rows[-1].get("row_hash")) if rows else ti.GENESIS
    now = datetime.now(UTC).isoformat(timespec="seconds")
    new = 0
    lines = []
    for res in results:
        if res.get("deal") is None or res["deal"] in seen:
            continue
        row = {"at": now, "deal": res["deal"], "verdict": res["verdict"],
               "weak_links": res["weak_links"],
               "joins": {k: v.get("class") for k, v in res["joins"].items()},
               "head": res["chain"]["head"], "broken_at": res["chain"]["broken_at"],
               "node_hashes": {n["kind"]: n["hash"] for n in res["chain"]["nodes"]},
               "nodes": res["nodes"], "prev": prev}
        row["row_hash"] = row_hash(prev, row)
        prev = row["row_hash"]
        seen.add(res["deal"])
        lines.append(json.dumps(row, default=str))
        new += 1
    if lines:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return new


# ------------------------------------------------------------------------------ the measure
def _reason_shape(why: str) -> str:
    """A break reason with its particulars masked, so the table counts SHAPES of break."""
    return re.sub(r"[0-9]{5,}", "<n>", re.sub(r"'[^']*'", "<x>", str(why)))[:140]


def measure(src: Sources) -> dict[str, Any]:
    live = [d for d in src.deals if str(d.get("account_kind") or "live") == "live"]
    results = [resolve(d, src) for d in live]
    verdicts = Counter(r["verdict"] for r in results)
    per_link: dict[str, dict[str, int]] = {}
    reasons: Counter[str] = Counter()
    for r in results:
        for k, j in r["joins"].items():
            per_link.setdefault(k, dict.fromkeys(ti.JOIN_CLASSES, 0))[j["class"]] += 1
            if j["class"] not in ti.CLEAN:
                reasons[f"{k}: {_reason_shape(j['why'])}"] += 1
    n = len(results)
    clean = verdicts.get("CLEAN", 0)
    # CERTIFICATE-SIDE COVERAGE: of the LIVE sleeves that name a certificate, how many reach a
    # clock by content and an allocator row by their own name -- the half of the chain that does
    # not depend on a trade having happened yet.
    certs = []
    for name, s in src.sleeves.items():
        if str(s.get("status")) != "LIVE":
            continue
        cj, ck = link_sleeve_certificate(s, src)
        kj, _ = link_certificate_clock(ck, src) if ck else (_j(ti.BROKEN, "no cert"), None)
        aj, _ = link_sleeve_allocation(name, s)
        certs.append({"sleeve": name, "certificate": cj["class"], "clock": kj["class"],
                      "allocation": aj["class"]})
    cert_clean = sum(1 for c in certs if all(c[k] in ti.CLEAN
                                             for k in ("certificate", "clock", "allocation")))
    return {"results": results, "n_deals": n, "clean": clean,
            "clean_fraction": (clean / n) if n else None,
            "verdicts": dict(verdicts), "per_link": per_link,
            "top_breaks": [{"reason": k, "n": v} for k, v in reasons.most_common(15)],
            "live_sleeves": len(certs), "live_sleeves_clean": cert_clean,
            "live_sleeve_clean_fraction": (cert_clean / len(certs)) if certs else None,
            "live_sleeve_links": certs}


def build(src: Sources, *, ledger: Path = LEDGER, report: Path = REPORT,
          write: bool = True) -> dict[str, Any]:
    m = measure(src)
    prev = _json(report) if report.exists() else None
    hw_prev = (prev or {}).get("high_water") if isinstance(prev, dict) else None
    frac = m["clean_fraction"]
    high_water = max([x for x in (hw_prev, frac) if isinstance(x, (int, float))], default=None)
    appended = append_new(m["results"], ledger) if write else 0
    doc = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "UNMEASURED" if frac is None else "MEASURED",
        "clean_fraction": frac, "high_water": high_water,
        "ratchet_ok": frac is None or high_water is None or frac >= high_water - 1e-12,
        "n_deals": m["n_deals"], "clean": m["clean"], "verdicts": m["verdicts"],
        "per_link": m["per_link"], "top_breaks": m["top_breaks"],
        "live_sleeves": m["live_sleeves"], "live_sleeves_clean": m["live_sleeves_clean"],
        "live_sleeve_clean_fraction": m["live_sleeve_clean_fraction"],
        "live_sleeve_links": m["live_sleeve_links"],
        "ledger": {"path": str(ledger.relative_to(ROOT)) if ledger.is_relative_to(ROOT)
                   else str(ledger), "appended": appended,
                   **verify_ledger(ledger_rows(ledger))},
        "required_links": list(REQUIRED_LINKS),
        "proposed_order_tag": {"enabled": PROPOSED_ORDER_TAG,
                               "what": "carry trade_identity.tag(chain head) in the order "
                                       "comment so fill->sleeve is EXACT by construction",
                               "status": ("live: gateway.new_order_identity stamps every new "
                                          "order; fills carry order_tag in live_ledger")},
        "sample": [{k: r[k] for k in ("deal", "sleeve_tag", "sleeve", "verdict",
                                      "weak_links", "tag")} for r in m["results"][-10:]],
    }
    if write:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def reconstruct(deal_id: int, src: Sources, ledger: Path = LEDGER) -> dict[str, Any]:
    """The recorded chain for one deal if the ledger holds it, else a fresh resolution."""
    for r in ledger_rows(ledger):
        if r.get("deal") == deal_id:
            nodes = r.get("nodes") or {}
            check = ti.verify_chain({"nodes": [{"kind": k, "hash": h} for k, h in
                                               (r.get("node_hashes") or {}).items()],
                                     "head": r.get("head")}, nodes)
            return {"source": "ledger", "row": r, "recomputed": check}
    for d in src.deals:
        if _int(d.get("deal")) == deal_id:
            return {"source": "live resolution (not yet in the ledger)",
                    "row": resolve(d, src)}
    return {"source": None, "why": f"deal {deal_id} is in neither the ledger nor live_ledger"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="measure, append, write the report")
    ap.add_argument("--trade", type=int, help="reconstruct one deal by its venue deal ticket")
    ap.add_argument("--check", action="store_true", help="rc=1 if clean_fraction fell")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=60.0, help="accepted for the cycle")
    a = ap.parse_args(argv)
    src = Sources()
    if a.trade is not None:
        print(json.dumps(reconstruct(a.trade, src), indent=1, default=str))
        return 0
    doc = build(src, write=not a.dry_run)
    print(f"identity chain: {doc['clean']}/{doc['n_deals']} live deals clean end to end "
          f"(fraction {doc['clean_fraction']}, high-water {doc['high_water']}); "
          f"live sleeves clean {doc['live_sleeves_clean']}/{doc['live_sleeves']}; "
          f"verdicts {doc['verdicts']}")
    for b in doc["top_breaks"][:6]:
        print(f"  {b['n']:4d}  {b['reason']}")
    if a.check and not doc["ratchet_ok"]:
        print("  RATCHET: clean_fraction fell below its high-water mark")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
