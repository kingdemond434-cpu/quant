"""TRANSLINGUAL DIFFUSION LAG: how long a country's own-language press leads English coverage.

THE MECHANISM. GDELT 2.0 codes the world's news every 15 minutes in two streams: English, and a
translingual stream of 65 machine-translated languages. Both streams write a MENTIONS file that
names each event (GlobalEventID) an article mentioned in that quarter hour. So for one event the
first slot with a local-language mention and the first slot with an English mention are both on
the public record, and their difference is the minutes the story sat in the local press before
the English wires carried it. The payer is the FX or index dealer who reads English wires: while
a story about Japan exists only in Japanese, it is not in his price. The constraint is language
and volume, not secrecy.

WHAT IS EMITTED. At fixed UTC snapshot hours, per region, the count of events that are (a) located
in the region, (b) first reported in the region's own languages, and (c) STILL without one
English mention, split by how long they have been waiting. EACH WAITING-TIME BUCKET IS ITS OWN
COLUMN AND SO ITS OWN CHARGED TRIAL. Two context columns ride along: the share of the day's
covered events the local press led, and the median realised lag of the ones English picked up.

POINT-IN-TIME, BY CONSTRUCTION. A snapshot at slot T reads only files named T or earlier, and a
file named T holds what GDELT processed in the quarter hour BEFORE T. "No English mention yet" is
a fact as of T; a later pickup changes a later snapshot, never this one. The walk is forward-only
and chronological: nothing is backfilled out of order.

HONEST LIMITS, STATED UP FRONT.
  * 15-minute resolution: a lead shorter than one slot reads as zero.
  * The build container cannot reach data.gdeltproject.org, so the column layout is the GDELT 2.0
    codebook's, tested on fixtures; live yield is UNMEASURED until the box runs it. Whether the
    two streams share GlobalEventIDs is the load-bearing assumption: `info["matched"]` counts
    the local-led events English later picked up, and a box that reads zero there for days has
    falsified the assumption, not found calm.
  * No history: a full day is ~380 files, so the series accrues forward from the first pass.
  * A language is read from MentionDocTranslationInfo (`srclc:<iso639-3>`); a translingual
    mention with no readable tag counts for no region and is reported in `info["untagged"]`.

This module fetches nothing by itself. `advance` is handed `fetch(url) -> bytes | None` (None =
the file does not exist) that the caller has ALREADY put behind the fail-closed robots gate and
the hard-stop rules; any exception it raises stops the walk with the cursor on the unread slot.
"""
from __future__ import annotations

import io
import math
import statistics
import time
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

BASE = "http://data.gdeltproject.org/gdeltv2/"
#: file key -> name suffix after the 14-digit slot id.
FILES: dict[str, str] = {
    "export": ".export.CSV.zip", "tl_export": ".translation.export.CSV.zip",
    "mentions": ".mentions.CSV.zip", "tl_mentions": ".translation.mentions.CSV.zip"}
#: Waiting-time buckets in minutes, [lo, hi). One column, one charged trial, each.
BUCKETS: tuple[tuple[int, int], ...] = ((15, 60), (60, 240), (240, 720), (720, 1440))
SNAP_HOURS: tuple[int, ...] = (0, 6, 12, 21)
HORIZON_MIN = 1440                 # an event is followed for a day after GDELT first coded it
PUBLISH_LAG_MIN = 30               # a slot is asked for only this long after its name
START_BACK_MIN = HORIZON_MIN + 120  # first pass starts here, so the first snapshot is a day in
MAX_BEHIND_MIN = 3 * 1440          # further behind than this: the walk restarts, and says so
SLOTS_PER_PASS = 12
MAX_MISSING_SLOTS = 8              # of the 96 before a snapshot; more and it is not emitted
MIN_LOCAL_MENTIONS = 2             # an open event counts once two local articles carry it
MIN_COVERED = 20                   # below this many covered events the share is not a number


def slot_id(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def _minute(t: datetime) -> int:
    return int(t.timestamp() // 60)


def _when(minute: int) -> datetime:
    return datetime.fromtimestamp(minute * 60, tz=UTC)


def urls(slot: str) -> dict[str, str]:
    return {k: f"{BASE}{slot}{suffix}" for k, suffix in FILES.items()}


def _rows(body: bytes | None, min_cols: int) -> Iterator[list[str]]:
    """Tab-separated rows of one GDELT file (zipped or plain) whose first column is an id."""
    if not body:
        return
    raw = body
    if body[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                names = zf.namelist()
                raw = zf.read(names[0]) if names else b""
        except (zipfile.BadZipFile, OSError):
            return
    for line in raw.decode("utf-8", errors="replace").splitlines():
        cols = line.split("\t")
        if len(cols) >= min_cols and cols[0].isdigit():
            yield cols


def parse_export(body: bytes | None) -> dict[str, str]:
    """Events export -> {GlobalEventID: ActionGeo_CountryCode (FIPS 10-4)}. Column 53 of 61."""
    return {c[0]: c[53].strip() for c in _rows(body, 60) if c[53].strip()}


def parse_mentions(body: bytes | None) -> dict[str, dict[str, int]]:
    """Mentions -> {GlobalEventID: {source language: articles}}. Column 14 of 16 is
    MentionDocTranslationInfo (`srclc:jpn;eng:...`); it is blank in the English stream, which
    reads here as language ""."""
    out: dict[str, dict[str, int]] = {}
    for c in _rows(body, 14):
        info = c[14].strip() if len(c) > 14 else ""
        lang = ""
        for part in info.split(";"):
            if part.strip().startswith("srclc:"):
                lang = part.strip()[6:].strip().lower()
        by = out.setdefault(c[0], {})
        by[lang] = by.get(lang, 0) + 1
    return out


def _lookup(regions: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, str], dict[str, set[str]]]:
    fips = {str(f).upper(): name for name, r in regions.items() for f in r.get("fips") or []}
    langs = {name: {str(x).lower() for x in r.get("langs") or []} for name, r in regions.items()}
    return fips, langs


def step(st: dict[str, Any], minute: int, files: Mapping[str, bytes | None],
         regions: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Fold one slot into the open-event table. `st["events"]` maps GlobalEventID ->
    [region, first coded, first local mention, first English mention, local articles before
    English] (minutes since the epoch; None = not yet). Slots must arrive in time order."""
    ev: dict[str, list[Any]] = st.setdefault("events", {})
    fips, langs = _lookup(regions)
    counts = {"new": 0, "untagged": 0, "matched": 0}
    for key in ("export", "tl_export"):
        for eid, code in parse_export(files.get(key)).items():
            region = fips.get(code.upper())
            if region and eid not in ev:
                ev[eid] = [region, minute, None, None, 0]
                counts["new"] += 1
    for eid, by in parse_mentions(files.get("tl_mentions")).items():
        counts["untagged"] += by.get("", 0)
        e = ev.get(eid)
        if e is None:
            continue
        n = sum(v for lang, v in by.items() if lang in langs.get(e[0], ()))
        if n:
            if e[2] is None:
                e[2] = minute
            if e[3] is None:
                e[4] += n
    for eid in parse_mentions(files.get("mentions")):
        e = ev.get(eid)
        if e is not None and e[3] is None:
            e[3] = minute
            if e[2] is not None and e[2] < minute:
                counts["matched"] += 1
    for eid in [k for k, e in ev.items() if e[1] < minute - HORIZON_MIN]:
        del ev[eid]
    return counts


def snapshot(st: Mapping[str, Any], minute: int, regions: Mapping[str, Mapping[str, Any]],
             buckets: Sequence[tuple[int, int]] = BUCKETS) -> dict[str, dict[str, float]]:
    """Per region, what the local press is carrying at `minute` that English has not."""
    out: dict[str, dict[str, float]] = {}
    acc: dict[str, dict[str, Any]] = {
        name: {"open": [0] * len(buckets), "covered": 0, "led": 0, "lags": []}
        for name in regions}
    for e in (st.get("events") or {}).values():
        region, _, local, eng, n = e
        a = acc.get(region)
        if a is None or (local is None and eng is None):
            continue
        a["covered"] += 1
        if local is None or (eng is not None and eng <= local):
            continue
        a["led"] += 1
        if eng is not None:
            a["lags"].append(eng - local)
        elif n >= MIN_LOCAL_MENTIONS:
            age = minute - local
            for i, (lo, hi) in enumerate(buckets):
                if lo <= age < hi:
                    a["open"][i] += 1
    for name, a in acc.items():
        row = {f"open_{lo}_{hi}": float(a["open"][i]) for i, (lo, hi) in enumerate(buckets)}
        enough = a["covered"] >= MIN_COVERED
        row["led_share_24h"] = a["led"] / a["covered"] if enough else math.nan
        row["median_lag_24h"] = float(statistics.median(a["lags"])) if a["lags"] else math.nan
        row["covered_24h"] = float(a["covered"])
        out[name] = row
    return out


def advance(st: dict[str, Any], fetch: Callable[[str], bytes | None], now: datetime,
            regions: Mapping[str, Mapping[str, Any]], *,
            snap_hours: Sequence[int] = SNAP_HOURS,
            buckets: Sequence[tuple[int, int]] = BUCKETS, per_pass: int = SLOTS_PER_PASS,
            deadline: float | None = None) -> dict[str, Any]:
    """Read the next slots in order and append any snapshot they close to `st["snaps"]`
    (dicts: region, at (ISO, the slot time), then the columns). Returns what the pass did.

    A slot all four of whose files are absent is MISSING and counted against the snapshot's
    gap allowance; a slot with some files absent is read with those parts empty and counted in
    `partial`. An exception from `fetch` propagates with the cursor still on that slot."""
    info: dict[str, Any] = {"slots": 0, "missing": 0, "partial": 0, "new": 0, "untagged": 0,
                            "matched": 0, "snapshots": 0}
    last = _minute(now) - PUBLISH_LAG_MIN
    last -= last % 15
    cur = st.get("cursor")
    if cur is None or cur < last - MAX_BEHIND_MIN:
        if cur is not None:
            info["restarted_from"] = _when(cur).isoformat()
        st["events"], st["gaps"] = {}, []
        cur = last - START_BACK_MIN
        cur -= cur % 15
        st["run_start"] = cur
    gaps: list[int] = st.setdefault("gaps", [])
    snaps: list[dict[str, Any]] = st.setdefault("snaps", [])
    while cur <= last and info["slots"] < per_pass:
        if deadline is not None and time.monotonic() > deadline:
            info["stopped"] = "budget reached: the remaining slots are owed to the next pass"
            break
        files = {k: fetch(u) for k, u in urls(slot_id(_when(cur))).items()}
        absent = sum(v is None for v in files.values())
        if absent == len(files):
            gaps.append(cur)
            info["missing"] += 1
        else:
            info["partial"] += int(absent > 0)
            for k, v in step(st, cur, files, regions).items():
                info[k] += v
        gaps[:] = [g for g in gaps if g > cur - HORIZON_MIN]
        t = _when(cur)
        if t.minute == 0 and t.hour in snap_hours:
            if cur - int(st["run_start"]) < HORIZON_MIN:
                info["accruing"] = "less than a day read since the walk started"
            elif len(gaps) > MAX_MISSING_SLOTS:
                info["skipped_for_gaps"] = t.isoformat()
            else:
                for region, row in snapshot(st, cur, regions, buckets).items():
                    snaps.append({"region": region, "at": t.isoformat(), **row})
                    info["snapshots"] += 1
        cur += 15
        st["cursor"] = cur
        info["slots"] += 1
    st["cursor"] = cur
    info["cursor"] = _when(cur).isoformat()
    info["behind_min"] = max(0, last - cur + 15)
    info["open_events"] = len(st.get("events") or {})
    return info


def frame_rows(snaps: Sequence[Mapping[str, Any]], region: str, hour: int
               ) -> list[dict[str, Any]]:
    """The snapshots of one region at one UTC hour, one row per day (`date`), oldest first.
    The same day read twice keeps its first reading: a snapshot is never restated."""
    seen: dict[str, dict[str, Any]] = {}
    for s in snaps:
        at = datetime.fromisoformat(str(s["at"]))
        if s.get("region") == region and at.hour == hour:
            day = at.date().isoformat()
            if day not in seen:
                seen[day] = {"date": day, **{k: v for k, v in s.items()
                                             if k not in ("region", "at")}}
    return [seen[d] for d in sorted(seen)]

