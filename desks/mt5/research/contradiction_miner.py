"""THE CONTRADICTION MINER: two sources that disagree about one instrument are one testable cell.

WHY THIS EXISTS (N9 item 11, unknown-unknown engine; classification 2026-11-10)

The deep forest mines verbatim claims in a dozen languages, and each claim carries the words it
used for direction (`做多`, `下跌`, `yükselecek`, `short`) and for what the move does (`延续`
continuation, `反弹` rebound). Nothing on the desk ever put two claims about the same instrument
side by side. When one ground says gold continues and another says it reverts, at most one of
them is right on the desk's own data, and the desk can find out which for the price of two
cells. A disagreement is the cheapest unknown unknown there is: the field has already split on
it, so neither side is consensus and neither is priced as settled. `committee_engine.
contradictions` finds committees of THIS desk that disagree; this finds SOURCES that do.

WHAT IT DOES. One pass over `deep_forest_claims.jsonl` and the deep forest's top claims. Each
claim's direction words are read through a multilingual lexicon into a SIGN (+1 up / long,
-1 down / short, 0 when it says both or neither) and a REGIME (continuation or reversal, or
neither). Claims are grouped per instrument analogue. A group holds a contradiction when:

  SIGN    claims from at least two distinct sources say +1 and -1;
  REGIME  claims from at least two distinct sources say continuation and reversal.

Each side must carry a source the other side lacks: a disagreement inside one source is that
source's own hedging, not a contradiction. A claim that names both directions at once, or trades
a spread, a pair or a cross-sectional factor, says nothing about one instrument's own direction
and is set aside (`claims_relative`).

THE CONSUMER. Each contradiction donates the two cells that settle it, one trend-following and
one reverting registered price-only family on that instrument, to
`data/intelligence/contradiction_miner/discoveries_<stamp>.json`, the shape the candidate
compiler reads as STRUCTURED_HYPOTHESIS. The same contradiction on the same evidence is donated
once (`data/contradiction_miner_seen.json`); new evidence on either side donates it again. The
report keeps every claim hash on each side, so a verdict can be traced back to who was right.

    python desks/mt5/research/contradiction_miner.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
if str(BASE / "research") not in sys.path:
    sys.path.insert(0, str(BASE / "research"))

import unseen_frontier as uf  # noqa: E402

REPORT = BASE / "reports" / "CONTRADICTIONS.json"
DONATIONS = BASE / "data" / "intelligence" / "contradiction_miner"
SEEN = BASE / "data" / "contradiction_miner_seen.json"

#: The two registered price-only families that settle a split: one follows, one fades.
FOLLOW_FAMILY = "trend_ma_cross"
FADE_FAMILY = "range_reversion"
MIN_SOURCES_PER_SIDE = 1
MAX_EVIDENCE = 12
MAX_SEEN = 20_000

# Lowercased; matched as whole tokens for Latin scripts and as substrings for CJK, where a
# word boundary does not exist. Longer phrases are checked before their parts.
UP = ("long", "buy", "bull", "bullish", "up", "upside", "rise", "rising", "rally", "higher",
      "increase", "positive", "gain", "做多", "多头", "上涨", "涨", "走强", "买入", "看涨",
      "上行", "偏强", "ロング", "買い", "上昇", "上がる", "yüksel", "yükseliş", "yukarı", "alım",
      "alta", "compra", "subir", "sube", "largo", "рост", "лонг", "покупка", "상승", "매수")
DOWN = ("short", "sell", "bear", "bearish", "down", "downside", "fall", "falling", "drop",
        "lower", "decrease", "negative", "decline", "做空", "空头", "下跌", "跌", "走弱",
        "卖出", "看跌", "下行", "偏弱", "ショート", "売り", "下落", "下がる", "düş", "düşüş",
        "aşağı", "satış", "baixa", "venda", "cair", "baja", "corto", "падение", "шорт", "продажа", "하락", "매도")
CONTINUE = ("continuation", "continue", "trend", "momentum", "follow", "breakout", "延续",
            "趋势", "突破", "顺势", "継続", "トレンド", "devam", "trend takibi", "продолжение")
REVERT = ("reversal", "revert", "reversion", "rebound", "bounce", "fade", "mean reversion",
          "反弹", "回归", "回歸", "反转", "逆势", "戻る", "反発", "dönüş", "geri", "разворот",
          "отскок", "반등")
# A claim about a SPREAD, a pair or a cross-sectional factor (long the winners, short the losers)
# says nothing about one instrument's own direction or regime: cross-sectional momentum and
# time-series reversal are not opposites. Such a claim is set aside on both axes.
RELATIVE = ("pairs", "pair", "factor", "cross-sectional", "cross sectional", "spread",
            "relative value", "arbitrage", "stat arb", "价差", "套利", "对冲", "配对",
            "スプレッド", "裁定", "鞘取り", "спред", "арбитраж")


def _cjk(term: str) -> bool:
    return any(ord(ch) > 0x2E80 for ch in term)


def _hits(words: Iterable[str], lexicon: tuple[str, ...]) -> bool:
    for w in words:
        low = str(w).strip().lower()
        if not low:
            continue
        toks = set(low.replace("-", " ").replace("_", " ").split())
        for term in lexicon:
            if (_cjk(term) and term in low) or term == low or term in toks \
                    or (" " in term and term in low) or (not _cjk(term) and len(term) >= 4
                                                         and low.startswith(term)):
                return True
    return False


def is_relative(direction: Any, quantities: Any = None) -> bool:
    """True when the claim trades a spread or a cross-section, or names both sides at once."""
    words = direction if isinstance(direction, list | tuple) else [direction]
    if _hits(words, UP) and _hits(words, DOWN):
        return True
    return _hits(quantities if isinstance(quantities, list | tuple) else [quantities], RELATIVE)


def read_sign(direction: Any) -> int:
    words = direction if isinstance(direction, list | tuple) else [direction]
    up, down = _hits(words, UP), _hits(words, DOWN)
    return 1 if up and not down else -1 if down and not up else 0


def read_regime(direction: Any, quantities: Any = None) -> str | None:
    words = [*(direction if isinstance(direction, list | tuple) else [direction]),
             *(quantities if isinstance(quantities, list | tuple) else [])]
    cont, rev = _hits(words, CONTINUE), _hits(words, REVERT)
    return "continuation" if cont and not rev else "reversal" if rev and not cont else None


def claims(note: dict[str, str]) -> Iterator[dict[str, Any]]:
    for row in uf._iter_jsonl(uf.CLAIMS, note, uf.MAX_JSONL_LINES):
        yield row
    doc = uf._read_json(uf.DEEP_FOREST, note)
    for row in (doc.get("top_claims") or []) if isinstance(doc, dict) else []:
        if isinstance(row, dict):
            yield row


def _analogues(row: dict[str, Any]) -> list[str]:
    inst = row.get("instruments")
    raw = inst.get("analogues") if isinstance(inst, dict) else row.get("symbols")
    return [str(s) for s in raw if isinstance(s, str) and s] if isinstance(raw, list) else []


def _source(row: dict[str, Any]) -> str:
    return str(row.get("source") or row.get("ground") or uf.UNKNOWN)


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {"claim_hash": row.get("claim_hash"), "source": _source(row),
            "ground": row.get("ground"), "lang": row.get("lang") or row.get("language"),
            "direction": row.get("direction"), "url": row.get("url")}


def find(rows: Iterable[dict[str, Any]], stats: dict[str, int]) -> list[dict[str, Any]]:
    """Every contradiction in `rows`, one per (instrument, axis), with both sides' evidence."""
    sides: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list))
    for row in rows:
        stats["claims_read"] = stats.get("claims_read", 0) + 1
        if is_relative(row.get("direction"), row.get("quantities")):
            stats["claims_relative"] = stats.get("claims_relative", 0) + 1
            continue
        sign = read_sign(row.get("direction"))
        regime = read_regime(row.get("direction"), row.get("quantities"))
        if not sign and not regime:
            stats["claims_without_a_reading"] = stats.get("claims_without_a_reading", 0) + 1
            continue
        for sym in _analogues(row):
            if sign:
                sides[(sym, "SIGN")]["up" if sign > 0 else "down"].append(row)
            if regime:
                sides[(sym, "REGIME")][regime].append(row)
    out: list[dict[str, Any]] = []
    for (sym, axis), by in sorted(sides.items()):
        a, b = ("up", "down") if axis == "SIGN" else ("continuation", "reversal")
        src_a = {_source(r) for r in by.get(a, [])}
        src_b = {_source(r) for r in by.get(b, [])}
        # Each side needs a source the other side lacks: one source hedging, or one source on
        # both sides plus a single ally, is not two sources disagreeing.
        if not (src_a - src_b) or not (src_b - src_a):
            continue
        ev = {side: [_evidence(r) for r in by[side][:MAX_EVIDENCE]] for side in (a, b)}
        hashes = sorted(str(r.get("claim_hash")) for side in (a, b) for r in by[side])
        out.append({
            "instrument": sym, "axis": axis,
            "sides": {a: {"n_claims": len(by[a]), "sources": sorted(src_a)},
                      b: {"n_claims": len(by[b]), "sources": sorted(src_b)}},
            "evidence": ev,
            "evidence_key": hashlib.blake2b("|".join(hashes).encode("utf-8"),
                                            digest_size=8).hexdigest(),
            "settled_by": [FOLLOW_FAMILY, FADE_FAMILY],
        })
    return out


def donation_rows(found: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in found:
        key = f"{c['instrument']}|{c['axis']}|{c['evidence_key']}"
        if key in seen:
            continue
        seen.add(key)
        sides = " vs ".join(f"{s} ({v['n_claims']} claims, {len(v['sources'])} sources)"
                            for s, v in c["sides"].items())
        for family in c["settled_by"]:
            rows.append({
                "kind": "hypothesis", "family": family, "symbols": [c["instrument"]],
                "source": "contradiction_miner",
                "title": f"{c['instrument']}: sources split on {c['axis'].lower()} ({sides})",
                "text": (f"Sources disagree on {c['instrument']} ({c['axis'].lower()}: {sides}). "
                         f"{family} on {c['instrument']} is one half of the pair that settles "
                         "which side the desk's own data supports."),
                "contradiction": {"axis": c["axis"], "evidence_key": c["evidence_key"]},
            })
    return rows


def _load_seen() -> set[str]:
    try:
        doc = json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    keys = doc.get("keys") if isinstance(doc, dict) else None
    return {str(k) for k in keys} if isinstance(keys, list) else set()


def build() -> tuple[dict[str, Any], list[dict[str, Any]], set[str]]:
    note: dict[str, str] = {}
    stats: dict[str, int] = {}
    found = find(claims(note), stats)
    seen = _load_seen()
    before = len(seen)
    rows = donation_rows(found, seen)
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputs": note,
        "claims_read": stats.get("claims_read", 0),
        "claims_without_a_reading": stats.get("claims_without_a_reading", 0),
        "claims_relative": stats.get("claims_relative", 0),
        "contradictions": len(found),
        "by_axis": {ax: sum(1 for c in found if c["axis"] == ax) for ax in ("SIGN", "REGIME")},
        "new_this_pass": len(seen) - before,
        "cells_donated": len(rows),
        "found": found,
        "consumer": ("desks/mt5/research/miner_candidate_compiler.py (STRUCTURED_HYPOTHESIS) via "
                     "data/intelligence/contradiction_miner/"),
    }
    return report, rows, seen


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any], rows: list[dict[str, Any]], seen: set[str]) -> Path:
    if rows:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        _atomic_write(DONATIONS / f"discoveries_{stamp}.json",
                      json.dumps({"discoveries": rows}, indent=1, ensure_ascii=False))
    _atomic_write(SEEN, json.dumps({"keys": sorted(seen)[-MAX_SEEN:]}, indent=0))
    _atomic_write(REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return REPORT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="sources that disagree about one instrument")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    report, rows, seen = build()
    target = "DRY RUN (nothing written)" if args.dry_run else str(write(report, rows, seen))
    print(f"CONTRADICTIONS {report['at']}  claims {report['claims_read']} "
          f"(no reading {report['claims_without_a_reading']})  found {report['contradictions']} "
          f"{report['by_axis']}  new {report['new_this_pass']}  cells {report['cells_donated']}"
          f" -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
