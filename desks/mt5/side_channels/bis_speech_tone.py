"""BIS central-bankers' speech corpus -> dated per-currency policy-tone series.

WHY THIS EXISTS. `central_bank_miner.py` produces dated ATTENTION (a pointer to a document)
but no BODY, so nothing it emits can become the macro STATE series that the desk's absent
`macro_conditional` family needs. The body layer has been owed since 2026-08-26. Fetching 215
landing pages one at a time was the assumed route; it is not the cheapest one.

THE ROUTE (probed live 2026-08-28). The BIS publishes a pre-compiled full-text extract of every
central banker speech it has collected since 1996 -- https://www.bis.org/speeches/speeches.zip,
one CSV, 20,728 dated rows, ~18k characters of text each, url/title/description/date/text/author.
It is offered explicitly "to assist researchers" and its terms allow noncommercial use; the path
`/speeches/` carries no robots bar. This is the free-frontier answer to a body layer that looked
like a 215-request crawl: one request, 30 years, every central bank at once.

  §13 NOTE, and a real defect in the wired miner: `central_bank_miner.FEEDS["BIS"]` points at
  https://www.bis.org/doclist/cbspeeches.rss, and bis.org/robots.txt carries `Disallow: /doclist/`.
  That feed is barred and the miner has been reading it. BIS's own RSS path redirects to the
  allowed listing page, whose only content link is this download. Repair is in the same change.

COVERAGE THIS OPENS. RBA (AUD) has been a dead leg since 2026-08-26 (edge-blocked 403 on both
published feeds) and SNB (CHF) had no feed at all -- both currencies were UNCOVERED, and an
uncovered currency is a named gap, never a clean verdict (WS-005). Both central banks speak in
this corpus, so the gap closes by route, not by retrying a blocked one.

WHAT IT PRODUCES, AND WHAT IT DOES NOT. A per-(date, currency) tone reading: counts of hawkish
and dovish lexicon hits and a net tone in [-1, 1]. It is a STATE SERIES -- attention, not a
verdict -- and it applies no threshold in either direction; the canonical ten gates decide
(LAWS L1.60). Tone is a lexicon count, not a claim about what the speaker meant.

POINT-IN-TIME. The row is stamped with the speech's own delivery date and nothing else; there is
no field on it that a later revision could change. A consumer must still LAG it by its own
availability assumption -- the BIS collects speeches with a delay, so same-day availability is
NOT implied and must never be assumed by a backtest reading this file.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "central_banks"
ZIP = OUT / "bis_speeches" / "speeches.zip"

#: SEED, not a boundary (LAWS §1 anti-hardcode): institution phrases -> the currency whose policy
#: the speaker sets. Adding a central bank is adding a row. Matched against title+description,
#: which is where the BIS names the speaker's institution; `author` is a person, never an org.
BANKS: dict[str, tuple[str, str]] = {
    "federal reserve": ("Fed", "USD"),
    "board of governors of the federal reserve": ("Fed", "USD"),
    "european central bank": ("ECB", "EUR"),
    "bank of japan": ("BoJ", "JPY"),
    "bank of england": ("BoE", "GBP"),
    "reserve bank of australia": ("RBA", "AUD"),
    "bank of canada": ("BoC", "CAD"),
    "swiss national bank": ("SNB", "CHF"),
    "reserve bank of new zealand": ("RBNZ", "NZD"),
}

#: Policy-direction lexicon. Phrases, not single words: "tightening" alone is as likely to be
#: describing someone else's policy as announcing one, while these read as a stance.
HAWKISH = (
    "tighten", "tightening", "raise interest rates", "raising interest rates", "rate increase",
    "restrictive", "upside risks to inflation", "inflationary pressures", "overheating",
    "normalisation of monetary policy", "normalization of monetary policy", "withdraw stimulus",
    "price stability is at risk", "second-round effects", "curb inflation", "combat inflation",
)
DOVISH = (
    "accommodative", "accommodation", "easing", "ease monetary policy", "lower interest rates",
    "rate cut", "cutting rates", "stimulus", "downside risks to growth", "economic slack",
    "weak demand", "deflation", "deflationary", "support the recovery", "asset purchases",
    "quantitative easing",
)


def classify_bank(text: str) -> tuple[str, str] | None:
    """Longest phrase wins, so 'board of governors of the federal reserve' is not decided by
    'federal reserve' appearing later in the same sentence. Returns None when no listed bank is
    named -- an unattributed speech is DROPPED, never assigned to a default currency (the
    'USDUSD' class of defect this corpus was built to replace)."""
    low = text.lower()
    hits = [(len(k), v) for k, v in BANKS.items() if k in low]
    if not hits:
        return None
    return max(hits)[1]


def score_tone(text: str) -> tuple[int, int]:
    low = text.lower()
    return (
        sum(low.count(p) for p in HAWKISH),
        sum(low.count(p) for p in DOVISH),
    )


def iter_speeches(zip_path: Path) -> Any:
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))


def build(zip_path: Path, max_date: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return (per-speech rows, drop counts). Drops are COUNTED and reported, never silent."""
    rows: list[dict[str, Any]] = []
    drops = {"no_bank": 0, "no_date": 0, "future_dated": 0, "no_text": 0}
    for rec in iter_speeches(zip_path):
        date = (rec.get("date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            drops["no_date"] += 1
            continue
        if date > max_date:
            # The corpus carries rows dated ahead of its own publication (2 rows in 2027 as of
            # 2026-08-28). A future-dated observation in a PIT series is a look-ahead, so it goes.
            drops["future_dated"] += 1
            continue
        text = rec.get("text") or ""
        if not text.strip():
            drops["no_text"] += 1
            continue
        who = classify_bank(f"{rec.get('title', '')} {rec.get('description', '')}")
        if who is None:
            drops["no_bank"] += 1
            continue
        bank, ccy = who
        hawk, dove = score_tone(text)
        rows.append({
            "date": date, "bank": bank, "currency": ccy,
            "hawk": hawk, "dove": dove,
            "chars": len(text),
            "url": rec.get("url", ""), "title": (rec.get("title") or "")[:300],
        })
    return rows, drops


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (date, currency). net_tone is None -- not 0.0 -- when a day's speeches contain
    no lexicon hit at all: 'no directional language' and 'balanced language' are different facts
    and the consumer must not collapse them (L1.28a)."""
    agg: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"n_speeches": 0, "hawk": 0, "dove": 0, "banks": set()}
    )
    for r in rows:
        a = agg[(r["date"], r["currency"])]
        a["n_speeches"] += 1
        a["hawk"] += r["hawk"]
        a["dove"] += r["dove"]
        a["banks"].add(r["bank"])
    out = []
    for (date, ccy), a in sorted(agg.items()):
        tot = a["hawk"] + a["dove"]
        out.append({
            "date": date, "currency": ccy, "banks": sorted(a["banks"]),
            "n_speeches": a["n_speeches"], "hawk": a["hawk"], "dove": a["dove"],
            "net_tone": round((a["hawk"] - a["dove"]) / tot, 4) if tot else None,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", default=str(ZIP))
    ap.add_argument("--max-date", default="2026-08-28",
                    help="drop rows dated after this (look-ahead guard); pass the run date")
    args = ap.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        print(f"corpus absent: {zip_path} -- UNMEASURED, not empty (L1.28a)", file=sys.stderr)
        return 2

    rows, drops = build(zip_path, args.max_date)
    series = aggregate(rows)

    per_speech = OUT / "bis_speech_tone.jsonl"
    with per_speech.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    series_path = OUT / "cb_tone_series.jsonl"
    with series_path.open("w", encoding="utf-8") as fh:
        for r in series:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_ccy: dict[str, int] = defaultdict(int)
    for r in rows:
        by_ccy[r["currency"]] += 1
    print(f"scored {len(rows)} speeches -> {len(series)} (date,currency) rows")
    print("drops:", drops)
    print("coverage:", dict(sorted(by_ccy.items(), key=lambda kv: -kv[1])))
    print(f"-> {per_speech}\n-> {series_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
