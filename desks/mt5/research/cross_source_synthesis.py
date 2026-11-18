"""H4 CROSS-SOURCE SYNTHESIS: how many INDEPENDENT sources agree on each docket row.

WHY. A mechanism that three unrelated grounds arrive at on the same instrument is better evidence
for a prior than one a single producer emitted 25,000 parameterisations of -- and the docket did
not distinguish them. The compiler already stamps `contributing_sources` / `agreeing_sources`, but
by producer NAME: two seats reading the same web host, or two sub-lanes of one generator
(`descendants:session`, `descendants:instrument`), counted as two sources. Nothing published the
count, and nothing ordering the judge's docket read it.

INDEPENDENCE, DECLARED. Every source a row names is reduced to an INDEPENDENCE ROOT:

    * a row whose source is an external http(s) page counts as that page's HOST (two producers
      that read one host are one source) -- read with `libs/research/source_provenance`, which
      this module only calls and never edits;
    * otherwise the producer's GENERATOR namespace: `miner:` dropped, the first `:` segment kept
      (`orthogonal_sweep:pca_residual` and `orthogonal_sweep:turn_of_month` are one generator),
      and the per-cell `ext_<ground>_...` names folded onto their ground, so `ext_reddit_...` and
      `miner:reddit` are one source.

AGREEMENT IS COUNTED ON THE MECHANISM-ON-INSTRUMENT (symbol, family), the unit two unrelated
sources can actually agree on (they almost never name the same parameter vector). The exact-cell
count is published beside it. Rows whose (symbol, family) has 2+ independent roots are the ones
`research/judge_docket_order.priority_tilt` favours -- in ORDER only; no gate reads this.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlparse

from libs.research import source_provenance as SP

#: Rows with this many independent roots or more are favoured in the ordering.
AGREEMENT_MIN = 2


def root_of(name: str) -> str:
    """The independence root of one producer name."""
    s = str(name or "").strip().lower()
    if s.startswith("miner:"):
        s = s[len("miner:"):]
    m = re.match(r"ext_([a-z]+)_", s)
    if m:
        return m.group(1)
    if s.startswith("gold_hour_sweep"):
        return "gold_hour_sweep"
    return s.split(":", 1)[0] or "?"


def roots_of(row: Mapping[str, Any]) -> set[str]:
    """Every independence root a docket row names."""
    roots: set[str] = set()
    url = SP.source_url_of(row)
    if SP.is_external_url(url):
        host = (urlparse(str(url).strip()).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            roots.add(f"host:{host}")
    own = root_of(str(row.get("source") or row.get("producer") or ""))
    if not roots and own:
        roots.add(own)
    for key in ("contributing_sources", "agreeing_sources"):
        vals = row.get(key)
        if isinstance(vals, list):
            for v in vals:
                r = root_of(str(v))
                if r and r != "?":
                    roots.add(r)
    roots.discard("")
    return roots or {"?"}


def mechanism_key(row: Mapping[str, Any]) -> str:
    return f"{str(row.get('symbol') or row.get('sym') or '').upper()}|{row.get('family') or ''}"


class CrossSource:
    """`observe` every docket row, then read `n_mechanism(row)` / `n_cell(cell_key)`."""

    def __init__(self) -> None:
        self.by_mech: dict[str, set[str]] = {}
        self.by_cell: dict[str, set[str]] = {}

    def observe(self, row: Mapping[str, Any], cell_key: str) -> None:
        r = roots_of(row)
        self.by_mech.setdefault(mechanism_key(row), set()).update(r)
        self.by_cell.setdefault(cell_key, set()).update(r)

    def n_mechanism(self, row: Mapping[str, Any]) -> int:
        return len(self.by_mech.get(mechanism_key(row), ()))

    def n_cell(self, cell_key: str) -> int:
        return len(self.by_cell.get(cell_key, ()))


def report(cs: CrossSource, per_row: Iterable[tuple[int, int, int]]) -> dict[str, Any]:
    """CROSS_SOURCE.json from (n_mechanism, n_cell, compiler's n_independent_sources) per row."""
    rows = list(per_row)
    hist_m: dict[str, int] = {}
    hist_c: dict[str, int] = {}
    named_gt_root = 0
    def _bin(n: int) -> str:
        return "6+" if n >= 6 else str(n)

    for nm, nc, named in rows:
        hist_m[_bin(nm)] = hist_m.get(_bin(nm), 0) + 1
        hist_c[_bin(nc)] = hist_c.get(_bin(nc), 0) + 1
        named_gt_root += int(named > nc)
    agree = sum(1 for nm, _nc, _ in rows if nm >= AGREEMENT_MIN)
    top = sorted(((len(v), k, sorted(v)) for k, v in cs.by_mech.items() if len(v) >= AGREEMENT_MIN),
                 key=lambda t: (-t[0], t[1]))[:50]
    return {
        "law": "H4: independent sources agreeing on each docket row, by declared independence "
               "roots (external host, else generator namespace); rows at 2+ are favoured in the "
               "judge's warm ORDER only, never in a gate.",
        "n_rows": len(rows),
        "agreement_min": AGREEMENT_MIN,
        "rows_with_agreement": agree,
        "share_with_agreement": round(agree / len(rows), 6) if rows else None,
        "mechanisms": len(cs.by_mech),
        "mechanisms_with_agreement": sum(1 for v in cs.by_mech.values()
                                         if len(v) >= AGREEMENT_MIN),
        "histogram_mechanism": dict(sorted(hist_m.items())),
        "histogram_cell": dict(sorted(hist_c.items())),
        "compiler_count_exceeds_independent_roots": named_gt_root,
        "top_agreements": [{"mechanism": k, "n_independent": n, "roots": r} for n, k, r in top],
        "rule": {"root": "external http(s) host via source_provenance.source_url_of, else the "
                         "producer's generator namespace (miner: dropped, first ':' segment, "
                         "ext_<ground>_* -> ground)",
                 "unit": "mechanism-on-instrument (symbol, family); exact cell published beside"},
    }
