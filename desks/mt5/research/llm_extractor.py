#!/usr/bin/env python3
"""LLM-NATIVE EXTRACTION for the vaulted pages the shape parsers cannot read -- validated row by row.

WHERE IT SITS. `asia_collector` vaults the bytes, `source_fixer` repairs dead routes and
`asia_parser` reads every payload whose SHAPE carries a series (tables, JSON islands, CSV, XLSX,
zip members). What is left is prose: a release written as sentences, a PDF bulletin, a portal page
whose numbers sit in paragraphs. `asia_parser` files those NO_TABLE, NO_TEXT or `pdf_text`, and
nothing downstream reads them. This organ gives each one to a language model and asks for rows,
then trusts none of them: `extraction_validator` checks every row against the source text and
rejects it with a reason code. Only accepted rows are written, point-in-time stamped with the
registry's own publication lag, to `data/lake/series/<id>__llm.parquet` -- and, when the source
has no canonical frame yet, to `<id>.parquet`, which is where `pack_cells` (direct cells) and
`world_cells` (gated cells, allocation state) already look.

THE SEAT. `collector_author` stays dark until an OpenRouter key exists, and so does every seat on
this desk: `llm_seat`, `deepseek_cycle`, `kimi_hunter` and `proposer_seat` all resolve the same
credential (an exported key or `data/secrets/llm_panel.json`). This organ uses `llm_seat` -- the
one door -- and when it returns no seat the whole pass is UNMEASURED with that reason. It never
falls back to a heuristic dressed as extraction, and never writes a row nobody extracted.

FREE TIER. `llm_seat.chat` enforces the daily request budget the free tier shares; this organ
also stops while `RESERVE_CALLS` remain, so the seats that hunt hypotheses are never starved by it.

    python research/llm_extractor.py                 # one pass
    python research/llm_extractor.py --dry-run       # which documents it would send, no calls
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from extraction_validator import validate  # noqa: E402

UNMEASURED = "UNMEASURED"
PARSER_REPORT = DESK / "reports" / "ASIA_PARSER.json"
SERIES = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "LLM_EXTRACTION.json"
CURSOR = DESK / "data" / "llm_extractor_cursor.json"

#: The parser verdicts this organ exists for: prose the shape bank could not turn into a series.
TARGET_STATUSES = frozenset({"NO_TABLE", "NO_TEXT"})
TARGET_KINDS = frozenset({"pdf_text"})
#: Documents sent per pass. Pacing, not a ceiling: the cursor resumes, so every document is sent.
DOCS_PER_PASS = 5
#: Seconds one call may take; DOCS_PER_PASS x this stays inside the leg's budget.
CALL_TIMEOUT_S = 150.0
#: Characters of source text sent per document. A statistics release states its headline
#: numbers early; the whole of a 40-page bulletin would spend the free tier on one document.
MAX_CHARS = 14_000
#: Free-tier calls left untouched for the hypothesis seats.
RESERVE_CALLS = 150
#: A document re-sent only after this long: its bytes may have been re-vaulted since.
RESEND_AFTER_H = 72.0

SYSTEM = ("You extract statistics from official publications. Return ONLY JSON. Never invent a "
          "number: every row must quote, verbatim, the words of the source that state it.")
PROMPT = """From the SOURCE below, extract every numeric statistic the publisher states for a
dated period (a day, month, quarter or year). Return a JSON object {{"rows": [...]}} where each
row is {{"period": "YYYY-MM-DD" | "YYYY-MM" | "YYYYQn" | "YYYY", "variable": short english
snake_case name, "value": number, "unit": text, "quote": the exact words of the source (copied
character for character, 8 to 160 characters) that contain the number}}. Skip forecasts, targets
and anything you cannot quote. If there are none, return {{"rows": []}}.

SOURCE ({source_id}, {url}):
{text}"""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def candidates(parser_doc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The parser's rows this organ is for, in a stable order."""
    rows = (parser_doc or {}).get("rows") or []
    out = [r for r in rows if isinstance(r, dict) and r.get("id")
           and (r.get("status") in TARGET_STATUSES or r.get("kind") in TARGET_KINDS)]
    return sorted(out, key=lambda r: str(r["id"]))


def source_text(row: Mapping[str, Any], *, series_dir: Path | None = None) -> str | None:
    """The visible text of the document: the parser's own .txt for a PDF, else the vaulted
    HTML with scripts and tags stripped. None when neither is on disk."""
    sid = str(row["id"])
    base = series_dir or SERIES
    txt = base / f"{sid}.txt"
    if row.get("kind") == "pdf_text" and txt.exists():
        return txt.read_text("utf-8", errors="replace")
    try:
        from asia_parser import _blobs
        from deep_forest_miner import html_text
    except Exception:                                     # noqa: BLE001
        return None
    got = _blobs().get(sid)
    if got is None:
        return None
    try:
        body = gzip.decompress(got[0].read_bytes()).decode("utf-8", errors="replace")
    except Exception:                                     # noqa: BLE001
        return None
    return html_text(body)


def parse_reply(text: str) -> list[dict[str, Any]] | None:
    """The rows of a model reply; None when the reply is not the JSON asked for."""
    s = (text or "").strip()
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        doc = json.loads(m.group(0))
    except ValueError:
        return None
    rows = doc.get("rows") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def write_series(sid: str, accepted: list[dict[str, Any]], *, fetched_utc: str | None,
                 lag_days: int, series_dir: Path | None = None) -> dict[str, Any]:
    """Accepted rows as a wide frame (period x variable), PIT-stamped, in the lake."""
    import pandas as pd

    from libs.data import pit_stamp
    base = series_dir or SERIES
    base.mkdir(parents=True, exist_ok=True)
    df = (pd.DataFrame(accepted).pivot_table(index="period", columns="variable", values="value",
                                             aggfunc="last").reset_index())
    df.columns = [str(c) for c in df.columns]
    out, meta = pit_stamp.stamp_frame(df, lag_days=int(lag_days), observed_at=fetched_utc,
                                      source_id=sid, vintage_fallback=True)
    if meta.get("status") != "STAMPED":
        return {"written": False, "why": f"pit: {meta.get('why') or meta.get('status')}"}
    path = base / f"{sid}__llm.parquet"
    out.to_parquet(path, index=False)
    canonical = next((base / f"{sid}{s}" for s in (".parquet", ".csv")
                      if (base / f"{sid}{s}").exists()), None)
    alias = None
    if canonical is None:
        alias = base / f"{sid}.parquet"
        out.to_parquet(alias, index=False)
    return {"written": True, "file": path.name, "canonical_alias": alias.name if alias else None,
            "rows": int(len(out)), "variables": [c for c in df.columns if c != "period"]}


Chat = Callable[..., tuple[str, str | None]]


def run(*, now: datetime | None = None, dry_run: bool = False, chat: Chat | None = None,
        seat_available: bool | None = None, paths: Mapping[str, Path] | None = None
        ) -> dict[str, Any]:
    now = now or _now()
    p = dict(paths or {})
    parser_doc = _read_json(p.get("parser", PARSER_REPORT))
    cands = candidates(parser_doc)
    cur = _read_json(p.get("cursor", CURSOR)) or {}
    sent: dict[str, str] = dict(cur.get("sent") or {})

    def _due(sid: str) -> bool:
        at = sent.get(sid)
        if not at:
            return True
        try:
            age = (now - datetime.fromisoformat(at)).total_seconds() / 3600.0
        except ValueError:
            return True
        return age >= RESEND_AFTER_H

    queue = [r for r in cands if _due(str(r["id"]))]
    queue.sort(key=lambda r: sent.get(str(r["id"]), ""))       # never-sent first, then oldest
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "parser_report": "MEASURED" if parser_doc is not None else UNMEASURED,
                           "candidates": len(cands), "due": len(queue), "docs": []}
    if parser_doc is None:
        doc.update(status=UNMEASURED, why="reports/ASIA_PARSER.json absent on this box")
        return doc
    if chat is None:
        try:
            from libs.ops import llm_seat
        except Exception as exc:                          # noqa: BLE001
            doc.update(status=UNMEASURED, why=f"llm_seat unimportable: {type(exc).__name__}")
            return doc
        if seat_available is None:
            seat_available = llm_seat.primary_seat() is not None
        if not seat_available:
            doc.update(status=UNMEASURED,
                       why=("no LLM seat has a key on this box (llm_seat, deepseek_cycle, "
                            "kimi_hunter and proposer_seat all resolve OPENROUTER_API_KEY or "
                            "data/secrets/llm_panel.json). Extraction is UNMEASURED, not zero, "
                            "and nothing was extracted by any other means."))
            return doc
        chat = llm_seat.chat
        try:
            left = llm_seat.free_budget_left() if llm_seat.free_tier_only() else None
        except Exception:                                 # noqa: BLE001
            left = None
        doc["free_calls_left"] = left
        if left is not None and left <= RESERVE_CALLS:
            doc.update(status="DEFERRED",
                       why=f"{left} free call(s) left today; {RESERVE_CALLS} reserved for the "
                           "hypothesis seats")
            return doc
    try:
        from asia_parser import _registry_rows
        registry = _registry_rows()
    except Exception:                                     # noqa: BLE001
        registry = {}
    try:
        from libs.data import pit_stamp
        lag_for: Callable[[Any], tuple[int, str]] = pit_stamp.lag_for
    except Exception:                                     # noqa: BLE001
        def lag_for(src: Any) -> tuple[int, str]:
            return 30, "fallback"
    totals = {"sent": 0, "rows_extracted": 0, "rows_accepted": 0, "rows_rejected": 0,
              "reason_codes": {}, "series_written": 0, "call_errors": 0}
    for row in queue[:DOCS_PER_PASS]:
        sid = str(row["id"])
        text = source_text(row, series_dir=p.get("series"))
        rec: dict[str, Any] = {"id": sid, "parser_status": row.get("status"),
                               "kind": row.get("kind")}
        if not text or len(text) < 40:
            rec.update(status="NO_SOURCE_TEXT")
            doc["docs"].append(rec)
            continue
        if dry_run:
            rec.update(status="WOULD_SEND", chars=min(len(text), MAX_CHARS))
            doc["docs"].append(rec)
            continue
        reply, err = chat(PROMPT.format(source_id=sid, url=row.get("url") or "",
                                        text=text[:MAX_CHARS]),
                          system=SYSTEM, max_tokens=4000, temperature=0.0,
                          timeout=CALL_TIMEOUT_S)
        totals["sent"] += 1
        sent[sid] = now.isoformat(timespec="seconds")
        if err:
            totals["call_errors"] += 1
            rec.update(status="CALL_ERROR", why=str(err)[:200])
            doc["docs"].append(rec)
            continue
        rows = parse_reply(reply)
        if rows is None:
            rec.update(status="UNPARSEABLE_REPLY", reply_head=(reply or "")[:120])
            doc["docs"].append(rec)
            continue
        fetched = None
        try:
            fetched = datetime.fromisoformat(str(row.get("fetched_utc")).replace("Z", "+00:00"))
        except ValueError:
            fetched = now
        if fetched is not None and fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        v = validate(rows, text[:MAX_CHARS], fetched_at=fetched)
        totals["rows_extracted"] += v["n"]
        totals["rows_accepted"] += v["n_accepted"]
        totals["rows_rejected"] += v["n_rejected"]
        for k, n in v["reason_codes"].items():
            totals["reason_codes"][k] = totals["reason_codes"].get(k, 0) + n
        rec.update(status="EXTRACTED", n=v["n"], accepted=v["n_accepted"],
                   acceptance_rate=v["acceptance_rate"], mean_score=v["mean_score"],
                   reason_codes=v["reason_codes"], rejected_sample=v["rejected"][:3])
        if v["accepted"]:
            lag, _why = lag_for(registry.get(sid) or registry.get(sid.split("__ep")[0]))
            try:
                w = write_series(sid, v["accepted"], fetched_utc=row.get("fetched_utc"),
                                 lag_days=lag, series_dir=p.get("series"))
            except Exception as exc:                      # noqa: BLE001
                w = {"written": False, "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
            rec["series"] = w
            totals["series_written"] += int(bool(w.get("written")))
        doc["docs"].append(rec)
    n = totals["rows_extracted"]
    doc.update(status="MEASURED" if not dry_run else "DRY_RUN", totals=totals,
               acceptance_rate=round(totals["rows_accepted"] / n, 4) if n else None)
    if not dry_run:
        _atomic_json(p.get("cursor", CURSOR), {"updated_at": doc["generated_at"], "sent": sent})
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    if not a.dry_run:
        _atomic_json(REPORT, doc)
    t = doc.get("totals") or {}
    print(f"llm_extractor: {doc['status']} -- {doc.get('candidates')} candidate document(s), "
          f"{t.get('sent', 0)} sent, {t.get('rows_accepted', 0)}/{t.get('rows_extracted', 0)} "
          f"rows accepted, {t.get('series_written', 0)} series written"
          + (f" ({doc.get('why')})" if doc.get("why") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
