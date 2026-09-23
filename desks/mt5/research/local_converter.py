"""Convert mined rows into structured candidates LOCALLY, with no seat and no network.

WHY THIS EXISTS. The deepening worker turns prose into hypotheses with an external model, and
that path is now working -- but it costs ~60-70s a row on the free tier, and the queue is
28,564 deep against 1,154,511 mined rows. Measured 2026-09-11: at that rate the queue alone is
~476 hours. A model is the right tool for a paragraph of trader prose; it is an absurd tool for
a row that already NAMES its symbol, its family and its session and needs only to be recognised.

THE COMPILER ALREADY ACCEPTS STRUCTURE. A row shaped

    {"kind": "hypothesis", "family": <registered price-only family>, "symbols": [...]}

compiles as STRUCTURED_HYPOTHESIS with the family's defaults, and declared instruments are read
BEFORE the prose. So anything this module can resolve deterministically never needs a seat at
all, and the seat's whole budget goes to rows that genuinely need judgement.

WHAT IT WILL NOT DO, and this is the point of the design. It never guesses. A family must match
a name the desk can actually execute (`FAMILY_REGISTRY`, `ORTHOGONAL_FAMILIES`, hunt16), a
symbol must exist in the universe registry, and a session must be one of the armed window
labels. A row that does not carry all of a family and a symbol is passed over and left for the
model -- it is not padded with a default, because a candidate invented here would be an
untested claim wearing a certificate's clothing. The dashboard's own verdict is the standard:
"two writeups naming the same session-range breakout differently are one discovery", so output
is deduplicated by economic exposure (family, symbol, session) and never by title.

    python desks/mt5/research/local_converter.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(ROOT))

OUT = DESK / "data" / "hypotheses" / "local_candidates.json"
SOURCES = [ROOT / "data" / "intelligence", DESK / "data" / "intelligence"]

#: The translation layer between how people write and how the desk names things. DATA, not code:
#: a new alias or mechanism phrase is a one-line edit to this file and needs no release.
VOCAB_PATH = DESK / "data" / "converter_vocabulary.json"

#: How many distinct symbols one row may produce candidates for. A row that names eight
#: instruments is usually a market wrap rather than a claim about any one of them, so the cap is
#: a relevance filter and not a resource one -- the dedup key already stops repeats.
MAX_SYMBOLS_PER_ROW = int(os.environ.get("LOCAL_CONVERT_MAX_SYMBOLS", "4"))


def _load_vocab() -> tuple[list[tuple[Any, str]], list[tuple[str, Any]]]:
    """(alias phrase -> ticker, family -> mechanism phrase) as compiled, longest-first matchers.

    LONGEST FIRST IN BOTH MAPS, for the same reason the literal family matcher sorts that way:
    "crude oil" must win over "oil", and "s&p 500" over "s&p". Sorting by length is what makes a
    flat dict behave like a proper alternation without hand-ordering the file.

    A MISSING OR MALFORMED FILE DEGRADES TO THE LITERAL MATCHERS and says so, rather than
    throwing: this is an enrichment on a free hourly job, and losing it costs yield, never
    correctness. An empty return reproduces the pre-2026-09-12 behaviour byte for byte.
    """
    try:
        doc = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"converter vocabulary unreadable ({exc}); literal matching only")
        return [], []
    aliases = doc.get("symbol_aliases") or {}
    fams = doc.get("family_keywords") or {}
    al = [(re.compile(r"\b" + re.escape(str(k).lower()) + r"\b"), str(v))
          for k, v in sorted(aliases.items(), key=lambda kv: len(kv[0]), reverse=True)]
    fp: list[tuple[str, Any]] = []
    for fam, phrases in fams.items():
        for ph in (phrases or []):
            fp.append((str(fam), str(ph).lower()))
    fp.sort(key=lambda t: len(t[1]), reverse=True)
    return al, [(f, re.compile(r"\b" + re.escape(p) + r"\b")) for f, p in fp]


_ALIASES, _FAM_PHRASES = _load_vocab()

#: Window labels the gateway actually arms. A session word outside this set is not a session.
SESSIONS = ("asia", "london_am", "london", "afternoon", "ny", "overlap", "ny_open")


def _known_symbols() -> set[str]:
    """Every symbol the desk can trade, from the universe registry -- never a literal list."""
    out: set[str] = set()
    reg = DESK / "data" / "universe" / "universe.json"
    if reg.exists():
        try:
            d = json.loads(reg.read_text(encoding="utf-8"))
            rows = d.get("symbols") or d.get("universe") or d
            if isinstance(rows, dict):
                out |= {str(k).upper() for k in rows}
            elif isinstance(rows, list):
                for r in rows:
                    s = r.get("symbol") if isinstance(r, dict) else r
                    if s:
                        out.add(str(s).upper())
        except (OSError, ValueError):
            pass
    # the parquet universe is the other authority on what has bars
    uni = DESK / "data" / "universe"
    if uni.exists():
        for p in uni.glob("*_H1.parquet"):
            out.add(p.name.split("_")[0].upper())
    return {s for s in out if s.isalnum() and 3 <= len(s) <= 12}


def _known_families() -> set[str]:
    """Families with a constructor on this tree, across all three populations."""
    out: set[str] = set()
    try:
        from mt5desk import executables as X
        for fam in list(X.hunt16_families()):
            out.add(str(fam))
    except Exception:
        pass
    try:
        from mt5desk.families import FAMILY_REGISTRY
        out |= {str(k) for k in FAMILY_REGISTRY}
    except Exception:
        pass
    try:
        from mt5desk import families_orthogonal as fo
        out |= {str(k) for k in fo.ORTHOGONAL_FAMILIES}
    except Exception:
        pass
    return out


def _iter_rows(limit: int) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for root in SOURCES:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl")):
            if len(rows) >= limit:
                return rows
            miner = p.parent.name
            try:
                if p.suffix == ".jsonl":
                    with p.open(encoding="utf-8", errors="replace") as fh:
                        for ln in fh:
                            ln = ln.strip()
                            if not ln:
                                continue
                            with contextlib.suppress(ValueError):
                                rows.append((miner, json.loads(ln)))
                            if len(rows) >= limit:
                                return rows
                else:
                    doc = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                    got = doc if isinstance(doc, list) else (
                        doc.get("rows") or doc.get("discoveries") or doc.get("items") or [])
                    if isinstance(got, dict):
                        got = list(got.values())
                    for r in got:
                        if isinstance(r, dict):
                            rows.append((miner, r))
                        if len(rows) >= limit:
                            return rows
            except (OSError, ValueError):
                continue
    return rows


def _text_of(row: dict) -> str:
    parts = []
    for k in ("title", "body", "text", "summary", "content", "mechanism", "claim", "name"):
        v = row.get(k)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


def convert(limit: int) -> tuple[list[dict], Counter]:
    symbols = _known_symbols()
    families = _known_families()
    # longest family names first, so "session_range_breakout" wins over "breakout"
    fam_sorted = sorted(families, key=len, reverse=True)
    fam_words = {f: re.compile(r"\b" + re.escape(f.replace("_", r"[\s_-]?")) + r"\b", re.I)
                 for f in fam_sorted}
    sym_re = re.compile(r"\b(" + "|".join(sorted(symbols, key=len, reverse=True)) + r")\b") \
        if symbols else None

    stats: Counter = Counter()
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []

    for miner, row in _iter_rows(limit):
        stats["rows_read"] += 1
        # a row may already BE structured; take it as-is when it is
        fam = str(row.get("family") or "")
        # `symbols` arrives as a list, a bare string, or a dict keyed by symbol depending on
        # which miner wrote the row; normalise before indexing rather than assuming a shape.
        raw = row.get("symbols") or row.get("instruments") or []
        if isinstance(raw, str):
            syms = [raw]
        elif isinstance(raw, dict):
            syms = [str(k) for k in raw]
        elif isinstance(raw, (list, tuple)):
            syms = [str(x) for x in raw if isinstance(x, (str, int))]
        else:
            syms = []
        sym = str((syms[0] if syms else "") or row.get("symbol") or "").upper()

        text = _text_of(row)
        if not fam:
            for f, rx in fam_words.items():
                if rx.search(text):
                    fam = f
                    break
        if fam and fam not in families:
            stats["family_not_executable"] += 1
            fam = ""
        if not sym and sym_re and text:
            m = sym_re.search(text.upper())
            if m:
                sym = m.group(1)
        if sym and sym not in symbols:
            stats["symbol_not_in_universe"] += 1
            sym = ""

        # ---------------------------------------------------------------- THE VOCABULARY PASS
        # PEOPLE DO NOT WRITE IN THE DESK'S IDENTIFIERS, and until 2026-09-12 that was the whole
        # yield story. The two matchers above look for `session_range_breakout` and `XAUUSD`
        # LITERALLY; a trader writes "gold breaks the Asian range". Measured over the whole
        # corpus: 215,073 rows in, 206,508 left_for_the_model, 31,751 with a symbol that was
        # found but is not a registry ticker, 88 converted -- 0.04%.
        #
        # So a translation layer runs when the literal pass fails, never before it: an explicit
        # ticker or an explicit `family` field always wins, and this only ever fills a blank.
        # `converter_vocabulary.json` holds both maps as DATA so the desk's vocabulary grows
        # without a code change (the deep-forest grounds work the same way).
        #
        # BEING GENEROUS HERE IS CORRECT, and it is worth saying why rather than assuming it.
        # A converted row is a HYPOTHESIS, not a position: it goes to the ten-gate gauntlet, and
        # a mapping that read the prose wrongly produces a cell that fails. The cost of a wrong
        # mapping is therefore one gauntlet cell -- and because the multiple-testing charge is
        # FIXED at 597 trials (gate_policy.charged_trial_count), that cell raises no other
        # candidate's bar. Breadth here is genuinely free, which is the property the principal
        # has insisted on and which `test_the_trial_charge_is_fixed_and_never_taxes_breadth`
        # now pins.
        alias_syms: list[str] = []
        if not sym and text:
            low_all = text.lower()
            for phrase, ticker in _ALIASES:
                if ticker in symbols and phrase.search(low_all):
                    alias_syms.append(ticker)
            if alias_syms:
                stats["symbol_by_alias"] += 1
        if not fam and text:
            low_all = text.lower()
            for f, rx in _FAM_PHRASES:
                if f in families and rx.search(low_all):
                    fam = f
                    stats["family_by_keyword"] += 1
                    break

        # EVERY SYMBOL THE ROW NAMES, not just the first. A row saying "gold and oil both gap on
        # Monday" is two testable exposures and was previously at most one: `syms[0]` took the
        # head of the list and the regex took the first match. The dedup key below still collapses
        # a repeat of the same (family, symbol, session), so this widens the yield without
        # duplicating a test.
        found = [s for s in ([sym] if sym else []) + alias_syms if s in symbols]
        if not found and sym_re and text:
            found = [m for m in sym_re.findall(text.upper()) if m in symbols]
        found = list(dict.fromkeys(found))[:MAX_SYMBOLS_PER_ROW]

        if not fam or not found:
            stats["left_for_the_model"] += 1
            continue

        sess = ""
        low = text.lower()
        for s in SESSIONS:
            if re.search(r"\b" + re.escape(s) + r"\b", low):
                sess = s
                break

        for sym in found:
            key = (fam, sym, sess)
            if key in seen:
                stats["duplicate_exposure"] += 1
                continue
            seen.add(key)
            out.append({
                "kind": "hypothesis",
                "family": fam,
                "symbols": [sym],
                "selector": sess or None,
                "source": f"local_converter/{miner}",
                "evidence": (text[:400] or None),
                "converted_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "why": ("resolved deterministically against the universe registry, the "
                        "executable family set and converter_vocabulary.json; no model "
                        "judgement was used and none is claimed"),
            })
            stats["converted"] += 1
    return out, stats


#: The gauntlet's own docket. Candidates that do not reach it are not candidates for anything.
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"


def feed_docket(cands: list[dict]) -> tuple[int, int]:
    """Merge converted candidates into the gauntlet's docket. Returns (added, docket size).

    THE WIRE THAT WAS NEVER THERE (found 2026-09-12). `local_candidates.json` had exactly two
    readers in the entire repository: this file, which writes it, and `organ_contract.py`, which
    checks its age. NOTHING consumed it. The converter ran hourly, resolved the corpus against the
    universe registry, wrote its candidates -- and every one of them sat in a file no organ opened.
    Conversion yield was being debated while the output went nowhere at all, which is III.16 in its
    purest form: built, scheduled, leaving an artifact, and unwired.

    DEDUPED ON THE EXECUTABLE SPEC so the hourly cadence cannot grow the docket without bound: the
    same (symbol, family, params) is the same test whoever proposed it.

    NO PERFORMANCE IS CLAIMED. A converted row is a claim that somebody ASSERTED an edge, never
    evidence that it exists -- so n=0 and every metric is null, and the gauntlet attaches the only
    numbers that will ever be attached. Inventing a backtest record here would be a fabricated
    claim wearing a survivor's shape.
    """
    try:
        docket = json.loads(DOCKET.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        docket = []
    if not isinstance(docket, list):
        return 0, 0

    def key(sym: str, fam: str, params: dict) -> str:
        return json.dumps([sym, fam, params], sort_keys=True, default=str)

    seen = {key(str(r.get("symbol") or ""), str(r.get("family") or ""), r.get("params") or {})
            for r in docket if isinstance(r, dict)}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    added = []
    for c in cands:
        sym = (c.get("symbols") or [None])[0]
        fam = c.get("family")
        if not sym or not fam:
            continue
        # The session rides as a PARAM, not as a name, so two sessions of one mechanism are two
        # cells rather than one cell with a label the builder cannot read.
        params = {"selector": c["selector"]} if c.get("selector") else {}
        if key(str(sym), str(fam), params) in seen:
            continue
        added.append({
            "symbol": sym, "family": fam, "params": params,
            "n": 0, "exp_r": None, "max_dd_r": None, "t_stat": None,
            "profit_factor": None, "win_rate": None,
            "source": str(c.get("source") or "local_converter"),
            "url": None, "producer": "desks/mt5/research/local_converter.py",
            "first_seen": now, "pit_stamp": now,
            "evidence": c.get("evidence"),
            "why": "converted deterministically from the mined corpus; no performance claimed",
        })
    if added:
        docket.extend(added)
        tmp = DOCKET.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(docket), encoding="utf-8")
        tmp.replace(DOCKET)
    return len(added), len(docket)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0,
                    help="rows to read; 0 = the whole corpus (the DEEPEN_LIMIT convention)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-feed", action="store_true",
                    help="write local_candidates.json but do NOT merge into the gauntlet docket")
    a = ap.parse_args(argv)

    cands, stats = convert(a.limit if a.limit > 0 else 10_000_000)
    print(f"symbols known : {len(_known_symbols())}")
    print(f"families known: {len(_known_families())}")
    for k, v in stats.most_common():
        print(f"  {k:<26} {v:,}")
    print(f"\ncandidates (deduped by family x symbol x session): {len(cands):,}")
    if cands:
        by_fam = Counter(c["family"] for c in cands)
        print("  top families:")
        for f, n in by_fam.most_common(8):
            print(f"    {f:<34} {n:,}")
    if a.dry_run:
        print("--dry-run: nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"built_at": datetime.now(UTC).isoformat(timespec="seconds"),
         "source": "desks/mt5/research/local_converter.py",
         "stats": dict(stats), "candidates": cands}, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")
    if not a.no_feed:
        added, total = feed_docket(cands)
        print(f"docket: +{added} new cell(s), now {total} row(s) -> {DOCKET.name}")
        if not added:
            print("  (every candidate already in the docket -- the feed is idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
