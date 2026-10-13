"""Scalp certificates re-ranked at the desk's MEASURED own-fill markout. REPORTS ONLY.

Every scalp certificate (the forward clocks in reports/shadow/scalp_shadow_state.json and the
scalp rows on data/sleeves.json) carries an expectancy measured at the bracket price. The fill
join (mt5desk.markout) measures what the desk actually paid against that price, per position.
This organ subtracts the sleeve's OWN measured slip from its expectancy and re-ranks.

Sign convention is mt5desk.markout's own: slip_r = (fill - intended) * side / risk, so a
POSITIVE slip is a cost and a negative one is price improvement. net_exp_r = exp_r - slip_r.

A sleeve with no matched fill is UNMEASURED: its net expectancy is null, never its gross
expectancy dressed as net (L1.28a). The book-level mean slip is reported beside the ranking but
is never imputed to a sleeve that did not trade -- it is dominated by a few sleeves.

Nothing here touches sizing, the roster or the promoter. It writes reports/scalp_markout_rerank.json.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "scalp_markout_rerank.json"
SCALP_STATE = BASE / "reports" / "shadow" / "scalp_shadow_state.json"
SLEEVES = BASE / "data" / "sleeves.json"
#: MT5 truncates the order comment, so the ledger's sleeve is a prefix of the certificate name.
MIN_PREFIX = 20


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def certificates(state: Any, sleeves: Any) -> dict[str, dict]:
    """Every scalp certificate, by name: the forward clock first, the roster row filling gaps."""
    out: dict[str, dict] = {}
    rows = (state or {}).get("sleeves") if isinstance(state, dict) else None
    for name, r in (rows or {}).items():
        if isinstance(r, dict):
            out[str(name)] = {"source": "scalp_shadow", "status": r.get("status"),
                              "timeframe": r.get("timeframe"),
                              "exp_r": r.get("expectancy_r"), "n": r.get("n")}
    roster = sleeves if isinstance(sleeves, list) else (
        (sleeves or {}).get("sleeves") if isinstance(sleeves, dict) else None)
    for r in roster or []:
        if not isinstance(r, dict) or r.get("exec") != "scalp_market":
            continue
        name = str(r.get("name"))
        row = out.setdefault(name, {"source": "sleeves", "status": r.get("status"),
                                    "timeframe": r.get("timeframe"),
                                    "exp_r": r.get("shadow_exp"), "n": r.get("shadow_n")})
        row["roster_status"] = r.get("status")
    return out


def slips_by_sleeve(rows: list[dict], names: list[str]) -> dict[str, list[float]]:
    """Measured slip_r per certificate, matching the ledger's truncated sleeve by prefix. A
    ledger name that prefixes two certificates is ambiguous and attributed to neither."""
    out: dict[str, list[float]] = {}
    for r in rows:
        s, v = str(r.get("sleeve") or ""), r.get("slip_r")
        if v is None or not s:
            continue
        hits = [n for n in names if n == s or (len(s) >= MIN_PREFIX and n.startswith(s))]
        if len(hits) == 1:
            out.setdefault(hits[0], []).append(float(v))
    return out


def rerank(certs: dict[str, dict], slips: dict[str, list[float]]) -> list[dict]:
    rows = []
    for name, c in certs.items():
        exp = c.get("exp_r")
        exp = float(exp) if isinstance(exp, (int, float)) else None
        s = slips.get(name) or []
        row = {"name": name, **c, "exp_r": exp, "n_fills": len(s)}
        if s and exp is not None:
            slip = sum(s) / len(s)
            row.update(slip_r=slip, net_exp_r=exp - slip, verdict="MEASURED",
                       edge_share=(slip / exp) if exp else None)
        else:
            row.update(slip_r=None, net_exp_r=None, edge_share=None, verdict="UNMEASURED",
                       why="no matched own fill" if not s else "no expectancy on the cert")
        rows.append(row)
    gross = sorted(rows, key=lambda r: -(r["exp_r"] if r["exp_r"] is not None else -1e9))
    for i, r in enumerate(gross, 1):
        r["rank_gross"] = i
    measured = sorted((r for r in rows if r["verdict"] == "MEASURED"),
                      key=lambda r: -r["net_exp_r"])
    for i, r in enumerate(measured, 1):
        r["rank_net"] = i
    for r in rows:
        r.setdefault("rank_net", None)
    return sorted(rows, key=lambda r: (r["rank_net"] is None, r["rank_net"] or 0, r["rank_gross"]))


def build() -> dict:
    from libs.ops.live_ledger_view import ledger_path
    from mt5desk import markout as mk
    m = mk.compute(mk.load_jsonl(BASE / "data" / "order_intents.jsonl"),
                   mk.load_jsonl(ledger_path(BASE / "data" / "live_ledger.jsonl")))
    certs = certificates(_read(SCALP_STATE), _read(SLEEVES))
    ranked = rerank(certs, slips_by_sleeve(list(m.rows or []), list(certs)))
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "reports_only": True,
        "markout_usable": bool(m.usable), "account_kind": getattr(m, "account_kind", None),
        "book": {"n_matched": m.n_matched, "mean_slip_r": m.mean_slip_r,
                 "edge_share": m.edge_share},
        "sign": "slip_r > 0 is a cost (mt5desk.markout); net_exp_r = exp_r - slip_r",
        "n_certs": len(ranked),
        "n_measured": sum(1 for r in ranked if r["verdict"] == "MEASURED"),
        "certs": ranked,
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(OUT)
    for r in doc["certs"]:
        print(f"{r['name']:<32} gross={r['exp_r']} slip={r['slip_r']} net={r['net_exp_r']} "
              f"n={r['n_fills']} {r['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
