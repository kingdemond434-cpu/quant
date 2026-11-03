#!/usr/bin/env python3
"""Turn mined YouTube transcripts into discovery rows for the canonical discovery->cell compiler.

Input: the output folder of scripts/mine_channel_transcripts.py (ledger.jsonl + transcripts/).
Each FULL transcript not yet processed is chunked and sent to the free OpenRouter rotation
(libs/ops/openrouter_free; :free models only, never paid) with one instruction: list every
CONCRETE, TESTABLE mechanism (signal, feature, sizing, risk, execution) with an exact rule.
Every extracted mechanism becomes one discovery row in
desks/mt5/data/intelligence/youtube_transcripts/discoveries_<ts>.json, written through the one
provenance door (side_channels.discovery_io.write_discoveries). The discovery compiler
(desks/mt5/research/discovery_compiler.py) interprets, dedupes (novelty gate) and compiles them into
gauntlet cells. NOTHING here judges, promotes or sizes: the gauntlet decides.

Coverage: every processed video gets a row in <out>/extraction_ledger.jsonl with
mechanisms_extracted (0 is a valid, recorded answer), so "mined" is provable per video id.

    python scripts/extract_video_cells.py --mined <path-to-video_mining_out> [--max-videos 50]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from libs.ops import openrouter_free as orf  # noqa: E402

OUT_DIR = ROOT / "desks" / "mt5" / "data" / "intelligence" / "youtube_transcripts"
#: Per-run summary (videos, mechanisms, key source name): the organ's own artifact.
REPORT = ROOT / "desks" / "mt5" / "reports" / "VIDEO_CELLS.json"
CHUNK = 14000
KINDS = ("signal", "feature", "sizing", "risk", "execution", "validation")

PROMPT = """You are extracting TESTABLE trading mechanisms from a video transcript for a systematic
desk that trades MT5 CFDs (FX majors/crosses, XAUUSD, indices, crypto CFDs) on M1-D1 bars.
Return ONLY a JSON array (possibly empty). One object per distinct mechanism ACTUALLY STATED in
the transcript (never invent; skip pure opinion, motivation, career talk, sponsor reads):
{"kind": one of %s,
 "mechanism": short name,
 "rule": exact, codeable rule: inputs, lookbacks, thresholds, entry, exit, stop/target, sizing,
 "universe": instruments/timeframe stated (or "unspecified"),
 "claimed_evidence": what the speaker claims as evidence (backtest stats, sample, period) or "none",
 "quote": a verbatim phrase (<=25 words) from the transcript that states it,
 "translatable_to_mt5": true/false}
Transcript title: %s
Transcript:
%s"""


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_ledger(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r["video_id"]] = r
    return rows


def parse_array(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except ValueError:
        return []
    return [a for a in arr if isinstance(a, dict) and a.get("rule")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mined", required=True, help="video_mining_out folder")
    ap.add_argument("--max-videos", type=int, default=50)
    args = ap.parse_args()
    mined = Path(args.mined)
    ledger = latest_ledger(mined / "ledger.jsonl")
    xl_path = mined / "extraction_ledger.jsonl"
    done = set(latest_ledger(xl_path))

    key, key_src = orf.resolve_key()
    if not key:
        print("no OpenRouter key resolvable; nothing extracted (recorded, not silent)")
        _report({"ts": now_iso(), "videos": 0, "mechanisms": 0, "state": "NO_KEY"})
        return 2
    models = orf.free_models(key)
    models = models[0] if isinstance(models, tuple) else models
    state = orf.load_state()

    rows_out: list[dict] = []
    n = 0
    with xl_path.open("a", encoding="utf-8") as xl:
        for vid, r in ledger.items():
            if r.get("status") != "FULL" or vid in done:
                continue
            if n >= args.max_videos:
                break
            tpath = mined / "transcripts" / r["channel"].lstrip("@") / f"{vid}.txt"
            if not tpath.exists():
                continue
            text = tpath.read_text("utf-8")
            plain = re.sub(r"\[\d+:\d+\] ", "", text)
            found: list[dict] = []
            errors = []
            for i in range(0, len(plain), CHUNK):
                msg = PROMPT % (", ".join(KINDS), r.get("title", ""), plain[i:i + CHUNK])
                out, model, err = orf.complete([{"role": "user", "content": msg}], key=key,
                                               models=list(models), state=state)
                if err:
                    errors.append(err)
                    continue
                for m in parse_array(out):
                    if m.get("quote") and m["quote"].lower()[:40] not in plain.lower():
                        m["quote_unverified"] = True      # never trust an unquoted claim
                    m["model"] = model
                    found.append(m)
            if errors and not found:
                print(f"{vid}: LLM errors {errors[:1]}; left for next pass")
                if any("429" in e or "daily" in e.lower() for e in errors):
                    break
                continue
            avail = r.get("upload_date")
            avail_iso = (f"{avail[:4]}-{avail[4:6]}-{avail[6:8]}T00:00:00Z"
                         if avail and len(avail) == 8 else r.get("ts"))
            for j, m in enumerate(found):
                rows_out.append({
                    "source": "youtube_transcripts", "kind": "mechanism_claim",
                    "title": f"{m.get('mechanism', '')[:120]}",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "text": f"[{m.get('kind')}] {m.get('rule')} | universe: {m.get('universe')}"
                            f" | evidence: {m.get('claimed_evidence')}",
                    "symbols": [], "found_at": now_iso(), "available_time": avail_iso,
                    "channel": r["channel"], "video_id": vid, "video_title": r.get("title"),
                    "mechanism_kind": m.get("kind"), "quote": m.get("quote"),
                    "quote_unverified": bool(m.get("quote_unverified")),
                    "translatable_to_mt5": m.get("translatable_to_mt5"),
                    "extractor_model": m.get("model"), "idx": j,
                    "access_label": "PUBLIC_WITH_TERMS", "terms_note": "creator captions; no redistribution",
                })
            xl.write(json.dumps({"video_id": vid, "channel": r["channel"], "ts": now_iso(),
                                 "mechanisms_extracted": len(found),
                                 "chunks": (len(plain) // CHUNK) + 1}) + "\n")
            xl.flush()
            n += 1
            print(f"{vid} {r['channel']}: {len(found)} mechanisms")
    if rows_out:
        from side_channels.discovery_io import write_discoveries
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")
        write_discoveries(OUT_DIR / f"discoveries_{ts}.json", rows_out)
    res = {"ts": now_iso(), "videos": n, "mechanisms": len(rows_out), "key_source": key_src,
           "state": "OK"}
    _report(res)
    print(json.dumps(res))
    return 0


def _report(res: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
