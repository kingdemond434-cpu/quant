#!/usr/bin/env python3
"""PRINCIPAL DROP -- the one route into sources the desk structurally CANNOT reach itself.

WHY THIS EXISTS, measured rather than assumed. The miner surfaces 60-115 candidate rows per run,
six times a day, across Bilibili, Juejin and WeChat. `libs.research.conversion_max` reports
`mined_research` total 14 -- FOURTEEN items have ever been READ in the desk's history. The chain is

    mine -> rank -> [ NOBODY READS ] -> hypothesis -> screen -> survivor

and it breaks at the read step, which is why the Chinese miner has produced no screens and no
survivors despite working correctly. It is a DISCOVERY organ and the desk has no reading organ.

The read step is blocked differently per source, and the difference matters (L1.54 clause 6 --
name the ROUTE, never the source):

  BILIBILI / YOUTUBE   genuinely blocked. Measured 0 of 14 quant videos expose a subtitle track to
                       an unauthenticated request, and every YouTube caption path is blocked from
                       this IP. The desk can rank these and cannot read them, and says so.
  JUEJIN               article pages are client-rendered: a plain GET returns a 2,397-byte JS
                       shell. Chromium is present in this environment, so this is a COST, not a
                       blocker -- and it is the next thing to build, not something to write off.
  CLOSED GROUPS        WeChat 群, Telegram channels, Discord servers, paid substacks, private
                       Feishu/Notion docs. No amount of engineering reaches these: they require a
                       membership, and membership is a person, not a credential.

THAT LAST CLASS IS WHAT THIS FILE IS FOR, and it is where the material is best. Closed Chinese
quant groups are where practitioners post live results and argue about them, precisely because the
group is closed. A desk that indexes only the open web is reading the marketing layer of a field
whose working layer is private.

PROVENANCE IS LOAD-BEARING AND NON-NEGOTIABLE. Every row carries source="principal_drop" with the
originating channel the principal names. Three reasons, and each is a defect this desk has already
paid for once:

  1. ATTRIBUTION. A finding that came from a private group is not reproducible by the desk's own
     organs. It must never be mistaken for something the miners found, or a future audit will look
     for a collector that does not exist.
  2. ACCESS IS NOT PERMANENT. A membership can lapse. Rows tagged with their channel let the desk
     see, later, which lanes went quiet -- exactly what `unproven_sources` does for probed sources.
  3. IT IS THE PRINCIPAL'S TIME. The blind-spot ledger scores principal-found gaps as the FAILURE
     signal (L2.5, L1.52 clause 2). Material the principal had to supply by hand is the same
     class: worth having, and worth counting, so the desk can see how much of its intake depends
     on a human doing what its organs cannot.

NOTHING HERE PROMOTES ANYTHING. A dropped file becomes a scored QUEUE ROW and nothing more. It
enters the identical path as every miner row -- triage ranker, then a human or an organ decides
whether it is worth a hypothesis. Zero promotion authority, no gate touched, no bar moved. The
ranker is the same `libs.research.video_triage.score_title` the miners use, so principal-supplied
material is held to exactly the same bar as anything the desk found on its own.

    python scripts/ingest_principal_drop.py [--dir data/inbox] [--channel NAME] [--json]

Drop plain text, Markdown, JSON or saved HTML into data/inbox/. Filenames may name the channel:
`wechat-群名-2026-08-05.txt` is tagged wechat. Processed files move to data/inbox/.done/ so a
re-run is idempotent and nothing is scored twice.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.video_triage import score_title  # noqa: E402

INBOX = _ROOT / "data/inbox"
OUT = _ROOT / "reports/principal_drop.json"

#: Channel hints recognised in a filename. Deliberately a small, explicit map rather than a guess:
#: a wrong channel tag is worse than none, because it claims a provenance the desk cannot check.
#: Matched on DELIMITER BOUNDARIES, never as bare substrings. The first version included "x"
#: for Twitter/X and matched the ".txt" SUFFIX, so every plain-text drop was tagged as coming from
#: Twitter -- a confidently wrong provenance on material whose provenance is the entire point.
#: "x" is gone rather than special-cased: a one-letter token cannot be matched safely, and
#: "twitter" already covers the case.
_CHANNELS = ("wechat", "telegram", "discord", "qq", "feishu", "substack", "twitter",
             "zhihu", "xueqiu", "bilibili", "juejin", "youtube", "reddit", "slack", "email")

_TEXT_SUFFIXES = {".txt", ".md", ".json", ".htm", ".html", ".csv"}

#: Below this a "document" is a filename someone saved by accident, not material.
_MIN_CHARS = 40


def _channel_of(name: str) -> str:
    """The channel a filename names, or "unspecified".

    Boundary-matched: a channel token counts only when delimited by a separator or the ends of
    the stem, so ".txt" cannot supply a channel and "wechatlike" cannot claim to be WeChat. A
    WRONG tag is worse than none -- it asserts a provenance the desk cannot check, and provenance
    it cannot check is exactly what this organ exists to preserve.
    """
    stem = Path(name).stem.lower()
    tokens = {t for t in re.split(r"[^a-z0-9]+", stem) if t}
    for c in _CHANNELS:
        if c in tokens:
            return c
    return "unspecified"


def _text_of(path: Path) -> str:
    """Readable text from a dropped file, or "".

    HTML is tag-stripped and entity-decoded in THAT ORDER -- decoding first would turn an encoded
    `&lt;p&gt;` into a real tag the stripper then eats, which is the same defect fixed in the CN
    parsers on 2026-08-05. JSON is flattened to its string leaves so a chat export works whatever
    shape the exporter chose, since there is no standard for those and never will be.
    """
    try:
        raw = path.read_text("utf-8", errors="ignore")
    except OSError:
        return ""
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(raw)
        except ValueError:
            return raw
        out: list[str] = []

        def walk(o: Any) -> None:
            if isinstance(o, str):
                out.append(o)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(doc)
        return "\n".join(out)
    if path.suffix.lower() in {".htm", ".html"}:
        return _html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return raw


def _blocks(text: str) -> list[str]:
    """Split a drop into scoreable units.

    Chat exports are line-per-message and articles are paragraph-per-idea, so blank-line blocks
    with a single-line fallback covers both without needing to detect which one this is. Scoring
    a whole 40KB export as ONE unit would let a single strong phrase carry the entire document,
    which is the shape in which junk enters a ranked queue.
    """
    parts = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(parts) <= 1:
        parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [p for p in parts if len(p) >= _MIN_CHARS]


def ingest(inbox: Path, *, channel_override: str = "", threshold: float = 3.0,
           move: bool = True) -> dict[str, Any]:
    inbox.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in inbox.iterdir()
                   if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    processed: list[str] = []
    for path in files:
        channel = channel_override or _channel_of(path.name)
        text = _text_of(path)
        blocks = _blocks(text)
        kept = 0
        for b in blocks:
            score, hits = score_title(b)
            if score < threshold:
                continue
            key = b[:120]
            if key in seen:
                continue
            seen.add(key)
            kept += 1
            rows.append({
                # SOURCE IS ALWAYS principal_drop, never the channel. The channel says WHERE it
                # came from; the source says the desk did NOT obtain it, and that is the fact a
                # later reader must not be able to lose.
                "source": "principal_drop",
                "channel": channel,
                "file": path.name,
                "score": round(score, 1),
                "why": hits,
                "text": b[:600],
                "ingested_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            })
        processed.append(f"{path.name} ({len(blocks)} block(s), {kept} above {threshold})")
        if move:
            # DERIVED FROM THE INBOX PASSED IN, not the module default. A module-level DONE
            # ignored --dir entirely, so a run against any other directory moved its files into
            # the DEFAULT inbox's .done -- material relocated somewhere the operator did not put
            # it and would not look, which for hand-supplied private content is the worst
            # possible place for a surprise.
            done = inbox / ".done"
            done.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(done / path.name))
    rows.sort(key=lambda r: -float(r["score"]))
    by_channel: dict[str, int] = {}
    for r in rows:
        by_channel[str(r["channel"])] = by_channel.get(str(r["channel"]), 0) + 1
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "inbox": str(inbox),
        "n_files": len(files),
        "files": processed,
        "n_rows": len(rows),
        "threshold": threshold,
        "by_channel": by_channel,
        "rows": rows,
        "provenance_note": (
            "source=principal_drop on every row. This material was supplied BY HAND because the "
            "desk's organs cannot reach it -- a closed group, a paid channel, a login-walled "
            "page. It is held to the SAME triage bar as miner output and carries ZERO promotion "
            "authority. The channel tag exists so a lapsed membership shows up as a lane going "
            "quiet, exactly as unproven_sources does for probed sources."),
        "why_this_organ_exists": (
            "conversion_max reports mined_research total 14 -- fourteen mined items have ever "
            "been read, against a miner surfacing 60-115 rows six times a day. The chain breaks "
            "at the READ step. Video is genuinely unreadable here (0 of 14 expose captions "
            "unauthenticated); Juejin bodies need browser rendering (a cost, Chromium is "
            "present); closed groups need a membership, which is a person and not a credential. "
            "This organ covers only the third case, and says so."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=str(INBOX))
    ap.add_argument("--channel", default="", help="override the channel tag for every file")
    ap.add_argument("--threshold", type=float, default=3.0)
    ap.add_argument("--keep", action="store_true", help="do not move processed files to .done/")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = ingest(Path(args.dir), channel_override=args.channel,
                 threshold=args.threshold, move=not args.keep)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        print(f"principal drop: {rep['n_files']} file(s) -> {rep['n_rows']} row(s) "
              f"above {rep['threshold']}")
        if not rep["n_files"]:
            print(f"  inbox empty. Drop .txt/.md/.json/.html into {args.dir} -- filenames may "
                  "name the channel, e.g. wechat-<group>-2026-08-05.txt")
        for f in rep["files"]:
            print(f"  read {f}")
        for r in rep["rows"][:12]:
            print(f"  {r['score']:5.1f}  [{r['channel']}] {r['text'][:76]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
