"""CROSS-ACCOUNT DIVERGENCE: one signal, several accounts, compared on realised R -- and cut.

WHY (2026-11-20). FTMO's gold_asia copy of E8's signal ran n=8 at -0.073R while E8's own fills of
the same signal ran +0.164R, and nothing noticed: the allocator sized FTMO from E8's certificate
and FTMO's cost surface, never from FTMO's own fills of the copy. A copy can lose what its source
earns for reasons no certificate sees -- a late follow, a fill rule that adversely selects, a wider
spread, a different clock -- so every account that trades a signal another account also trades is
measured here against that reference on realised R, and its risk fraction is cut by what it has
actually shown.

THE MULTIPLIER (pure, `multiplier`). The account's mean R is shrunk toward the reference's with a
prior of PRIOR_N trades (few fills move it little; many move it to what they show):

    shrunk = (n * acc_mean + PRIOR_N * ref_mean) / (n + PRIOR_N)
    mult   = clip(shrunk / ref_mean, 0, 1)

It never raises a fraction (mult <= 1), it is 1 while the account has fewer than MIN_ACC fills or
the reference fewer than MIN_REF, and it is 1 when the reference itself is not positive (that is
the allocator's question about the signal, not a divergence between accounts). Measured
2026-11-20: n=8 at -0.073R against +0.164R gives shrunk +0.059R, mult 0.36. An account that
catches up recovers its fraction by the same formula, with no manual reset.

FLAG. `diverged` is True when n >= MIN_ACC and the account's mean R is more than FLAG_GAP_R below
the reference's: a row for the hourly pass and the morning brief.

SOURCES. Closed fills from the desk's ledgers (`LEDGERS`), each row naming its account (`book`
or `account_kind`/`server`), its signal (`sleeve` or `cert_key`) and its R (`r_multiple` or
`r`). `COPIES` names each copied signal's reference account. `report()` writes
reports/CROSS_ACCOUNT_DIVERGENCE.json for every sleeve seen on more than one account.

    python mt5desk/account_divergence.py      write the report and print it
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LEDGERS = (DESK / "data" / "live_ledger_prop.jsonl", DESK / "data" / "live_ledger.jsonl")
REPORT = DESK / "reports" / "CROSS_ACCOUNT_DIVERGENCE.json"
#: (account, sleeve) -> the reference account whose own fills of the same signal it copies.
COPIES: dict[tuple[str, str], str] = {("ftmo", "gold_asia"): "e8"}
PRIOR_N = 10
MIN_ACC = 3
MIN_REF = 10
FLAG_GAP_R = 0.25


def multiplier(acc_rs: list[float], ref_rs: list[float], *, prior_n: int = PRIOR_N,
               min_acc: int = MIN_ACC, min_ref: int = MIN_REF) -> tuple[float, str]:
    """(fraction multiplier in [0, 1], why). Pure."""
    n, m = len(acc_rs), len(ref_rs)
    if m < min_ref:
        return 1.0, f"reference has {m} fills (< {min_ref}): unmeasured, no cut"
    ref = sum(ref_rs) / m
    if n < min_acc:
        return 1.0, f"account has {n} fills (< {min_acc}): no cut yet (reference {ref:+.3f}R)"
    if not ref > 0:
        return 1.0, f"reference mean {ref:+.3f}R is not positive: the signal's question, no cut"
    acc = sum(acc_rs) / n
    shrunk = (n * acc + prior_n * ref) / (n + prior_n)
    mult = min(1.0, max(0.0, shrunk / ref))
    return mult, (f"account {acc:+.3f}R over {n} vs reference {ref:+.3f}R over {m}: shrunk "
                  f"{shrunk:+.3f}R -> x{mult:.2f}")


def _account(row: dict[str, Any]) -> str | None:
    for k in ("book", "account", "lane_account", "server"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            v = v.strip().lower()
            return "e8" if v.startswith("e8") else "ftmo" if v.startswith("ftmo") else v
    return None


def _r(row: dict[str, Any]) -> float | None:
    for k in ("r_multiple", "r"):
        v = row.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return float(v)
    return None


def load_rs(paths: Iterable[Path] | None = None) -> dict[tuple[str, str], list[float]]:
    """{(account, sleeve): [R, ...]} over every readable closed row; unreadable lines skipped.
    `paths` None reads LEDGERS at call time."""
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for p in (LEDGERS if paths is None else paths):
        try:
            lines = Path(p).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            acc, sleeve, r = _account(row), row.get("sleeve") or row.get("cert_key"), _r(row)
            if acc and isinstance(sleeve, str) and r is not None:
                out[(acc, sleeve)].append(r)
    return dict(out)


def copy_multiplier(*, account: str, sleeve: str,
                    rs: dict[tuple[str, str], list[float]] | None = None) -> tuple[float, str]:
    """The multiplier for `account`'s copy of `sleeve` against its COPIES reference."""
    ref_acc = COPIES.get((account, sleeve))
    if ref_acc is None:
        return 1.0, f"{account}/{sleeve} copies no reference account"
    rs = load_rs() if rs is None else rs
    return multiplier(rs.get((account, sleeve), []), rs.get((ref_acc, sleeve), []))


def compare(rs: dict[tuple[str, str], list[float]]) -> list[dict[str, Any]]:
    """One row per (sleeve, account) where the sleeve trades on more than one account; the
    reference is COPIES' when declared, else the account with the most fills."""
    by_sleeve: dict[str, dict[str, list[float]]] = defaultdict(dict)
    for (acc, sleeve), r in rs.items():
        by_sleeve[sleeve][acc] = r
    rows = []
    for sleeve, accs in sorted(by_sleeve.items()):
        if len(accs) < 2:
            continue
        for acc, r in sorted(accs.items()):
            ref_acc = COPIES.get((acc, sleeve)) or max(accs, key=lambda a: len(accs[a]))
            if ref_acc == acc:
                continue
            ref = accs.get(ref_acc, [])
            mult, why = multiplier(r, ref)
            gap = (sum(r) / len(r) - sum(ref) / len(ref)) if r and ref else None
            rows.append({"sleeve": sleeve, "account": acc, "reference": ref_acc,
                         "n": len(r), "n_ref": len(ref),
                         "mean_r": round(sum(r) / len(r), 4) if r else None,
                         "ref_mean_r": round(sum(ref) / len(ref), 4) if ref else None,
                         "gap_r": None if gap is None else round(gap, 4),
                         "diverged": bool(gap is not None and len(r) >= MIN_ACC
                                          and gap < -FLAG_GAP_R),
                         "multiplier": round(mult, 4), "why": why})
    return rows


def report(path: Path = REPORT) -> dict[str, Any]:
    doc = {"at": datetime.now(UTC).isoformat(timespec="seconds"),
           "rule": "mt5desk/account_divergence.py", "rows": compare(load_rs())}
    doc["diverged"] = [f"{r['account']}/{r['sleeve']}" for r in doc["rows"] if r["diverged"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(path)
    return doc


if __name__ == "__main__":
    print(json.dumps(report(), indent=1))
    sys.exit(0)
