"""BLIND-SPOT MAXIMISER -- the four mechanically-findable classes of unknown-unknown.

The existing stack (blind_spot, blindspot_prober, info_class_map, feature coverage) finds KNOWN
unknowns: empty cells in a map the desk drew. This finds dimensions that were never mapped, using
only what the desk already owns, with no LLM and no credit.

FOUR CLASSES, in ascending order of how invisible they are:

 1 UNREAD FIELDS      data collected, never referenced by any code. (in unobserved.py; summarised
                      here for one complete picture)
 2 UNMODELLED ENTITIES values that APPEAR in collected data but exist in no universe, config or
                      analysis -- protocols, chains, assets the desk records and never considers.
                      An entity in your own files that you have never named is invisible twice.
 3 UNCROSSED PAIRS    N collectors admit N(N-1)/2 joins. A pair no script has ever referenced
                      together is a relationship nobody has looked for. Fusion is where weak
                      signals become strong, so an uncrossed pair is an unexamined interaction.
 4 UNCONDITIONED SLICES  hour-of-day, day-of-week, regime. If no analysis ever groups by them, a
                      relationship that exists only inside one slice is invisible at the mean --
                      and the mean is the only thing this desk has ever computed.

WHY 3 AND 4 ARE THE DEEPEST. A missing dataset is a known gap you can name. An unexamined
INTERACTION between two datasets you already have cannot be named, because nobody wrote it down
as a thing that could exist. The same is true of a conditional relationship: averaging over a
slice does not merely miss the effect, it actively hides it behind a null.

Read-only. No LLM, no network.
"""
from __future__ import annotations

import itertools
import json
import pathlib
from collections import Counter
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/blindspot_max.json"

_PLUMBING = {"ts", "date", "timestamp", "time", "updated", "id", "pool", "src", "note", "kind",
             "status", "period", "src_ts", "row_id", "provenance", "name", "event", "mock", "seat"}
_ENTITY_FIELDS = ("symbol", "asset", "project", "chain", "protocol", "venue", "exchange")
_SLICES = {
    "hour_of_day": ("hour", ".hour", "groupby('hour", 'groupby("hour', "hourly"),
    "day_of_week": ("weekday", "dayofweek", "day_of_week"),
    "regime": ("regime", "crypto_regime", "vol_state", "trend_state"),
    "session": ("asia", "london", "new_york", "session"),
}


def _code() -> str:
    out = ""
    for d in ("scripts", "libs"):
        for p in (ROOT / d).rglob("*.py"):
            out += p.read_text("utf-8", errors="ignore")
    return out


def main() -> None:
    code = _code()
    scripts = {p.stem: p.read_text("utf-8", errors="ignore")
               for p in (ROOT / "scripts").glob("*.py")}
    files = sorted((ROOT / "data").glob("*.jsonl"))

    samples, entities = {}, {}
    for f in files:
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                rows = [json.loads(ln) for i, ln in enumerate(fh) if ln.strip() and i < 300]
        except Exception:  # blind-except intentional (BLE001)
            continue
        rows = [r for r in rows if isinstance(r, dict)]
        if rows:
            samples[f.name] = rows
            ent = Counter()
            for r in rows:
                for k in _ENTITY_FIELDS:
                    v = r.get(k)
                    if isinstance(v, str) and 1 < len(v) < 32:
                        ent[v] += 1
            entities[f.name] = ent

    print("=== BLIND-SPOT MAXIMISER -- four mechanical classes of unknown-unknown ===\n")

    # ---- 2 UNMODELLED ENTITIES
    unmodelled = []
    for fn, ent in entities.items():
        for v, cnt in ent.items():
            if code.count(v) == 0:
                unmodelled.append({"file": fn, "entity": v, "rows": cnt})
    print(f"2. UNMODELLED ENTITIES -- appear in our data, named nowhere in our code: "
          f"{len(unmodelled)}")
    for r in sorted(unmodelled, key=lambda x: -x["rows"])[:12]:
        print(f"     {r['entity']:<24} {r['rows']:>4} rows in {r['file']}")
    if unmodelled:
        print("     An entity recorded in your own files that you have never named is invisible")
        print("     twice: absent from every universe, and absent from every gap list.")

    # ---- 3 UNCROSSED PAIRS
    live = [f for f in samples if len(samples[f]) >= 30]
    pairs, crossed = [], 0
    for a, b in itertools.combinations(sorted(live), 2):
        together = any(a in s and b in s for s in scripts.values())
        if together:
            crossed += 1
        else:
            pairs.append((a, b))
    tot = crossed + len(pairs)
    print(f"\n3. UNCROSSED COLLECTOR PAIRS -- {len(pairs)} of {tot} possible joins never examined "
          f"({crossed/max(tot,1)*100:.1f}% crossed)")
    for a, b in pairs[:10]:
        print(f"     {a}  x  {b}")
    print("     Fusion is where weak signals become strong. A pair no script has referenced")
    print("     together is an interaction nobody has looked for -- and unlike a missing dataset,")
    print("     it cannot be named as a gap because nobody wrote it down as possible.")

    # ---- 4 UNCONDITIONED SLICES
    print("\n4. UNCONDITIONED SLICES -- dimensions no analysis ever groups by:")
    slice_rows = []
    for name, kws in _SLICES.items():
        hits = sum(code.count(k) for k in kws)
        used = hits > 2
        slice_rows.append({"slice": name, "code_hits": hits, "conditioned": used})
        print(f"     {name:<14} {'CONDITIONED' if used else 'NEVER CONDITIONED'}  "
              f"({hits} code references)")
    never = [r["slice"] for r in slice_rows if not r["conditioned"]]
    if never:
        print(f"     {len(never)} dimension(s) never conditioned on. A relationship that exists")
        print("     only inside one slice is invisible at the mean -- and the mean is the only")
        print("     thing this desk has ever computed. Averaging does not miss the effect, it")
        print("     HIDES it behind a null.")

    # ---- 1 UNREAD FIELDS (summary)
    unread = 0
    for _fn, rows in samples.items():
        keys = Counter()
        for r in rows:
            keys.update(r.keys())
        for k, cnt in keys.items():
            if k in _PLUMBING or cnt < len(rows) * 0.5:
                continue
            if code.count(f'"{k}"') + code.count(f"'{k}'") <= 2:
                unread += 1

    print("\n=== TOTAL MECHANICALLY-FINDABLE BLIND SPOTS ===")
    print(f"  1 unread fields          {unread}")
    print(f"  2 unmodelled entities    {len(unmodelled)}")
    print(f"  3 uncrossed pairs        {len(pairs)}")
    print(f"  4 unconditioned slices   {len(never)}")
    print(f"  TOTAL                    {unread + len(unmodelled) + len(pairs) + len(never)}")
    print("\n  None of these is an edge. Each is a QUESTION NOBODY ASKED, and every one enters")
    print("  Stage-A screening like anything else. What distinguishes them is that the")
    print("  acquisition cost is already paid -- this is the cheapest frontier the desk has.")
    print("\n  WHAT REMAINS UNREACHABLE MECHANICALLY: a dimension absent from the data entirely.")
    print("  No amount of introspection finds a source you never collected. That is the hunter's")
    print("  job, and it needs credit.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "unread_fields": unread, "unmodelled_entities": unmodelled[:200],
                               "uncrossed_pairs": [list(p) for p in pairs[:300]],
                               "slices": slice_rows,
                               "total": unread + len(unmodelled) + len(pairs) + len(never)},
                              indent=1), "utf-8")
    # SECOND FAMILY (L1.33, principal 2026-07-31 "gpt n claude work together on these families"):
    # a blind-spot hunter that only ever thinks in ONE model's priors has the exact defect it
    # exists to detect. Ask the independent family what THIS run missed, and record the verdict
    # honestly -- SOLO when the partner is unavailable, never silently passed off as confirmed.
    # R0114: the ask/merge/record pattern itself lives in ONE shared helper
    # (libs/llm/second_opinion.py), so the prober and the sweep carry it without a per-organ copy.
    try:
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))   # run as `python scripts/...`: ROOT is not on sys.path
        from libs.llm.second_opinion import consult_second_family
        consult_second_family("blindspot_max",
                              {"unread": unread, "unmodelled": unmodelled[:20],
                               "pairs": pairs[:20], "never": never[:20]},
                              artifact=OUT)
    except Exception as exc:               # the partner must never break the organ
        print(f"  second family: SKIPPED ({exc})")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
