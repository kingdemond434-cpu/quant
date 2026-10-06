"""NLP EVENT/POLICY FACTORS -- the desk's collected text as a PIT daily panel per country.

    python desks/mt5/research/nlp_event_factors.py [--llm-max 60] [--dry-run]

WHAT IT READS (everything already collected; this organ fetches nothing):

  news_event_stream.collect_items   the moat's normalised store, the news desk's captures and the
                                    twelve news intelligence seats (central banks, BIS, investing,
                                    forexfactory, earnings, shipping, weather, china, asia, korea,
                                    world, sec_edgar) -- the fast lane's own intake, reused
  central_banks/cb_documents.jsonl  the central banks' press-release RSS titles
  central_banks/bis_speech_tone.jsonl  8,000+ BIS central-banker speech titles back to 1996

WHAT IT WRITES -- one signal, three uses (the principal's direct / indirect / allocation split):

  indirect   desks/mt5/data/axes/nlp_events.json    the axis door: `series[id].points [{d, v}]`
             with `d` the KNOWABLE date, which `axis_proposer`, `world_model` and
             `representation_forge` read as conditioning variables for every existing family
  direct     desks/mt5/data/lake/series/nlp_events_<CC>.parquet   one frame per country with an
             `available_time` column, which `family_exogenous_conditioner` loads by name -- the
             cells `nlp_social_cells` donates point at these
  allocation desks/mt5/reports/NLP_EVENTS_ALLOCATION_INTEL.json   per-instrument policy context
             the allocator MAY read; it sizes nothing and no allocator code is touched

POINT IN TIME. A news item enters on the UTC day it was FIRST SEEN by the desk (stamped once in
`data/text_store/nlp_events/first_seen.json` and never overwritten); a historical corpus with no
first-seen stamp enters one full day after its publication (a BIS review's date is parsed from its
own `rYYMMDD` URL, which is when the BIS published it -- often weeks after the speech). A day's row
is available at the following 00:00 UTC.

TWO TIERS. The lexicon tier always runs. The LLM tier (`libs.research.event_factors_llm`, the
desk's one seat, free tier by default) tags at most `--llm-max` recent untagged documents per pass
and publishes its own series beside the lexicon's; with no key it is UNMEASURED and the lexicon
carries the pass.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import asia_alt_digest  # noqa: E402
from libs.research import event_factors as ef  # noqa: E402
from libs.research import event_factors_llm as efl  # noqa: E402

#: NOT under `data/intelligence/` (the compiler globs that tree as seat output); gitignored.
STORE = DESK / "data" / "text_store" / "nlp_events"
FIRST_SEEN = STORE / "first_seen.json"
LLM_CACHE = STORE / "llm_cache.jsonl"
AXIS_OUT = DESK / "data" / "axes" / "nlp_events.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "NLP_EVENTS.json"
INTEL = DESK / "reports" / "NLP_EVENTS_ALLOCATION_INTEL.json"
CB_DOCS = DESK / "data" / "intelligence" / "central_banks" / "cb_documents.jsonl"
BIS_TITLES = DESK / "data" / "intelligence" / "central_banks" / "bis_speech_tone.jsonl"

SOURCE = "nlp_event_factors"
HIST_LAG = timedelta(days=1)
DRIFT_SPAN = 20
#: Days of history the AXIS file carries. The lake frame keeps the whole history; the axis door is
#: read whole into memory by `axis_proposer` (32 MB budget) and `world_model`, so it carries the
#: recent window and only the two columns a conditioner reads -- drift and intensity.
AXIS_DAYS = 750
AXIS_COLUMNS = ("_drift", "_intensity")
MAX_NEWS_ITEMS = 2000
LLM_RECENT_DAYS = 7
UNMEASURED = "UNMEASURED"

#: The roster rows for the grounds this organ reads (written to the shared roster by hand-off).
READS: tuple[dict[str, Any], ...] = (
    {"id": "nlp_news_event_stream_intake", "name": "news_event_stream intake (moat store, "
     "news captures, 12 news seats)", "url": "desks/mt5/data/intelligence/<seat>/",
     "region": "GLOBAL", "language": "en/ja/zh/ko", "cadence": "hourly",
     "source_culture": "GLOBAL/multi", "participant_structure": ["institutional",
                                                                "policy_driven"],
     "crowding_prior": "high"},
    {"id": "nlp_cb_press_rss", "name": "central-bank press RSS titles",
     "url": "desks/mt5/data/intelligence/central_banks/cb_documents.jsonl", "region": "G10",
     "language": "en", "cadence": "hourly", "source_culture": "G10/en",
     "participant_structure": ["policy_driven", "institutional"], "crowding_prior": "high"},
    {"id": "nlp_bis_review_titles", "name": "BIS central bankers' speeches (titles)",
     "url": "https://www.bis.org/review/", "region": "GLOBAL", "language": "en",
     "cadence": "daily", "source_culture": "GLOBAL/en",
     "participant_structure": ["policy_driven"], "crowding_prior": "high"},
)


# ------------------------------------------------------------------------------------ helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _ts(v: Any) -> datetime | None:
    if not v or v == UNMEASURED:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


_BIS_URL = re.compile(r"/r(\d{2})(\d{2})(\d{2})[a-z]*\.(?:pdf|htm)")


def bis_published(url: str) -> datetime | None:
    """The BIS review's own publication date from its `rYYMMDD` URL; None if it carries none."""
    m = _BIS_URL.search(str(url or ""))
    if not m:
        return None
    yy, mm, dd = (int(x) for x in m.groups())
    year = 1900 + yy if yy >= 90 else 2000 + yy
    try:
        return datetime(year, mm, dd, tzinfo=UTC)
    except ValueError:
        return None


# ------------------------------------------------------------------------------------ collect
def collect_docs(now: datetime, *, first_seen: dict[str, str], news_limit: int = MAX_NEWS_ITEMS,
                 cb_path: Path = CB_DOCS, bis_path: Path = BIS_TITLES,
                 news: bool = True) -> tuple[list[ef.Doc], dict[str, Any]]:
    """Every document with the moment the desk could first have read it. Mutates `first_seen`
    only by ADDING ids never seen before -- an id's first stamp is never moved."""
    docs: list[ef.Doc] = []
    notes: list[str] = []
    by: dict[str, int] = {}
    if news:
        try:
            import news_event_stream as nes  # type: ignore[import-not-found]
            items = nes.collect_items(news_limit, notes)
        except Exception as exc:
            items = []
            notes.append(f"news_event_stream intake unavailable: {type(exc).__name__}: {exc}")
        for it in items:
            stamp = first_seen.get(it.item_id)
            if stamp is None:
                seen = _ts(it.seen_at) or now
                stamp = min(seen, now).isoformat()
                first_seen[it.item_id] = stamp
            at = _ts(stamp) or now
            know = _ts(it.knowable_at)
            if know is not None and know > at:
                at = know                      # never before the world could know it either
            docs.append(ef.Doc(doc_id=it.item_id, text=f"{it.title}. {it.text}"[:1200],
                               available_at=at, source=f"news:{it.origin}"))
            by["news_event_stream"] = by.get("news_event_stream", 0) + 1
    for row in _jsonl(cb_path):
        pub = _ts(row.get("published_utc"))
        title = str(row.get("title") or "")
        if pub is None or not title:
            continue
        docs.append(ef.Doc(doc_id=str(row.get("link") or title)[:200], text=title,
                           available_at=pub + HIST_LAG, source="cb_press",
                           country_hint=ef.country_hint_for_currency(str(row.get("currency")))))
        by["cb_press"] = by.get("cb_press", 0) + 1
    for row in _jsonl(bis_path):
        title = str(row.get("title") or "")
        pub = bis_published(str(row.get("url") or "")) or _ts(row.get("date"))
        if pub is None or not title:
            continue
        docs.append(ef.Doc(doc_id=str(row.get("url") or title)[:200], text=title,
                           available_at=pub + HIST_LAG, source="bis_review",
                           country_hint=ef.country_hint_for_currency(str(row.get("currency")))))
        by["bis_review"] = by.get("bis_review", 0) + 1
    return docs, {"by_source": by, "notes": notes[:10]}


# ------------------------------------------------------------------------------------ publish
def _series(rows: Sequence[ef.PanelRow]) -> dict[str, dict[str, list[tuple[str, str, float]]]]:
    """country -> column -> [(day, available_time, value)] with a drift column per factor."""
    import pandas as pd

    out: dict[str, dict[str, list[tuple[str, str, float]]]] = {}
    frame = pd.DataFrame([r.__dict__ for r in rows])
    if frame.empty:
        return out
    days = sorted(frame["day"].unique())
    for (country, factor), grp in frame.groupby(["country", "factor"]):
        g = grp.set_index("day").reindex(days)
        known = [(d + "T00:00:00+00:00") for d in days]
        known = [(datetime.fromisoformat(k) + timedelta(days=1)).isoformat() for k in known]
        count = g["count"].fillna(0.0)
        inten = g["intensity"]
        drift = inten.ewm(span=DRIFT_SPAN, ignore_na=True).mean().ffill()
        cols = out.setdefault(str(country), {})
        for name, s in ((f"{factor}_count", count), (f"{factor}_intensity", inten),
                        (f"{factor}_drift", drift)):
            cols[name] = [(d, k, float(v)) for d, k, v in zip(days, known, s.to_numpy(),
                                                            strict=True) if v == v]
    return out


def axis_doc(series: dict[str, dict[str, list[tuple[str, str, float]]]], tier: str,
             now: datetime) -> dict[str, Any]:
    """The axis door's shape: `series[id].points [{d, v}]`, `d` = the KNOWABLE date."""
    block: dict[str, Any] = {}
    floor = (now - timedelta(days=AXIS_DAYS)).isoformat()
    for country, cols in series.items():
        if country not in ef.COUNTRY_INSTRUMENTS and country != ef.GLOBAL:
            continue
        for col, pts0 in cols.items():
            pts = [p for p in pts0 if p[1] >= floor] if col.endswith(AXIS_COLUMNS) else []
            if not pts:
                continue
            sid = f"{tier}.{country}.{col}"
            block[sid] = {"what": f"{col} for {country}, {tier} tier", "n": len(pts),
                          "first": pts[0][1][:10], "last": pts[-1][1][:10],
                          "points": [{"d": k[:10], "v": round(v, 6), "available_time": k,
                                      "period": d} for d, k, v in pts]}
    return {"axis": "event_policy", "id": "nlp_events", "source": SOURCE,
            "at": now.isoformat(timespec="seconds"), "n_series": len(block),
            "shape": "series[id].points [{d = knowable date, v, available_time, period}]",
            "pit": "a day's value is knowable at the following 00:00 UTC; d is that date",
            "series": block}


def write_lake(series: dict[str, dict[str, list[tuple[str, str, float]]]],
               series_dir: Path = SERIES_DIR) -> dict[str, int]:
    """One `nlp_events_<CC>.parquet` per country with `available_time` + one column per stat."""
    import pandas as pd

    written: dict[str, int] = {}
    for country, cols in series.items():
        rows: dict[str, dict[str, Any]] = {}
        for col, pts in cols.items():
            for d, k, v in pts:
                rows.setdefault(k, {"available_time": k, "period": d})[col] = v
        if not rows:
            continue
        ordered = [rows[k] for k in sorted(rows)]          # keys ARE the available_time stamps
        frame = pd.DataFrame(ordered)
        series_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(series_dir / f"nlp_events_{country}.parquet", index=False)
        written[country] = len(frame)
    return written


def allocation_intel(series: dict[str, dict[str, list[tuple[str, str, float]]]],
                     now: datetime) -> dict[str, Any]:
    """Per-instrument policy context as of `now`: the latest KNOWABLE drift per factor, oriented
    onto the instrument's own axis, and the last 7 days' document count. Advisory only."""
    cut = now.isoformat()
    inst: dict[str, dict[str, Any]] = {}
    for country, per in ef.COUNTRY_INSTRUMENTS.items():
        cols = series.get(country)
        if not cols:
            continue
        for symbol, orient in per.items():
            row = inst.setdefault(symbol, {"factors": {}})
            for factor in ef.FACTORS:
                pts = [p for p in cols.get(f"{factor}_drift", []) if p[1] <= cut]
                cnt = [p for p in cols.get(f"{factor}_count", []) if p[1] <= cut
                       and p[1] >= (now - timedelta(days=7)).isoformat()]
                if not pts:
                    continue
                d, k, v = pts[-1]
                row["factors"].setdefault(factor, []).append(
                    {"country": country, "day": d, "available_time": k, "drift": round(v, 4),
                     "orientation": orient, "drift_on_instrument": round(orient * v, 4),
                     "docs_7d": int(sum(p[2] for p in cnt))})
    for row in inst.values():
        mt = row["factors"].get("monetary_tone") or []
        tone = sum(x["drift_on_instrument"] for x in mt)
        row["policy_tone_on_instrument"] = round(tone, 4)
        row["regime_tone"] = ("supportive" if tone > 0.25 else "adverse" if tone < -0.25
                              else "neutral")
    return {"generated_at": now.isoformat(timespec="seconds"), "source": SOURCE,
            "use": "allocation_intel", "authority": "none -- advisory context, sizes nothing",
            "orientation": ("drift_on_instrument = the country's factor drift times the "
                            "currency-leg sign (a quoting convention, never a forecast)"),
            "instruments": inst}


def run(now: datetime | None = None, *, llm_max: int = efl.DEFAULT_MAX_DOCS,
        dry_run: bool = False, news: bool = True, chat: efl.ChatFn | None = None,
        paths: dict[str, Path] | None = None) -> dict[str, Any]:
    now = now or _now()
    p = {"store": STORE, "axis": AXIS_OUT, "series": SERIES_DIR, "report": REPORT,
         "intel": INTEL, "cb": CB_DOCS, "bis": BIS_TITLES, "digest": asia_alt_digest.DIGEST,
         **(paths or {})}
    first_seen_path = p["store"] / "first_seen.json"
    cache_path = p["store"] / "llm_cache.jsonl"
    first_seen: dict[str, str] = _read_json(first_seen_path, {}) or {}
    docs, meta = collect_docs(now, first_seen=first_seen, cb_path=p["cb"], bis_path=p["bis"],
                              news=news)
    lex_rows = ef.build_panel(docs)
    cache = {str(r.get("hash")): r for r in _jsonl(cache_path) if r.get("hash")}
    recent = [d for d in docs if d.available_at >= now - timedelta(days=LLM_RECENT_DAYS)]
    tags, llm_status = efl.llm_tags(recent, max_docs=llm_max, cache=cache, chat=chat)
    llm_rows = ef.build_panel([d for d in docs if d.doc_id in tags], tags=tags, tier="llm")
    series_lex = _series(lex_rows)
    series_llm = _series(llm_rows)
    doc = axis_doc(series_lex, "lexicon", now)
    doc["series"].update(axis_doc(series_llm, "llm", now)["series"])
    doc["n_series"] = len(doc["series"])
    intel = allocation_intel(series_lex, now)
    report = {"generated_at": now.isoformat(timespec="seconds"), "n_docs": len(docs),
              "docs_by_source": meta["by_source"], "notes": meta["notes"],
              "panel_rows": {"lexicon": len(lex_rows), "llm": len(llm_rows)},
              "countries": sorted(series_lex), "n_axis_series": doc["n_series"],
              "llm_tier": {k: v for k, v in llm_status.items() if k != "new_cache"},
              "outputs": {"indirect": str(p["axis"]), "direct": str(p["series"]),
                          "allocation_intel": str(p["intel"])},
              "dry_run": dry_run}
    if not dry_run:
        _atomic(first_seen_path, json.dumps(first_seen, sort_keys=True))
        if llm_status.get("new_cache"):
            with cache_path.open("a", encoding="utf-8") as fh:
                for r in llm_status["new_cache"]:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        _atomic(p["axis"], json.dumps(doc))
        report["lake_rows"] = write_lake(series_lex, p["series"])
        _atomic(p["intel"], json.dumps(intel, indent=1))
        _atomic(p["report"], json.dumps(report, indent=1, default=str))
        by_src = report["docs_by_source"] or {}
        asia_alt_digest.publish(SOURCE, asia_alt_digest.section(
            at=report["generated_at"], status="MEASURED" if report["n_docs"] else UNMEASURED,
            rows=int(report["panel_rows"]["lexicon"]),
            measured=[k for k, v in by_src.items() if v], unmeasured=[k for k, v in
                                                                       by_src.items() if not v],
            gain={}, countries=report["countries"], n_docs=report["n_docs"],
            llm_tier=str(report["llm_tier"].get("state") or UNMEASURED),
            gain_tested_by="nlp_social_cells"), p["digest"])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--llm-max", type=int, default=efl.DEFAULT_MAX_DOCS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(llm_max=a.llm_max, dry_run=a.dry_run)
    print(f"nlp_event_factors: {rep['n_docs']} docs {rep['docs_by_source']}; "
          f"panel {rep['panel_rows']}; {rep['n_axis_series']} axis series; "
          f"llm tier {rep['llm_tier'].get('state')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
