#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/crypto_adapter.py")
src = p.read_text()

old = """def load_universe(
    timeframe: Timeframe = Timeframe.D1,
    *,
    limit: int | None = 30,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> tuple[list[str], DataProvider]:"""

new = """def load_universe(
    timeframe: Timeframe = Timeframe.D1,
    *,
    limit: int | None = 30,
    offset: int = 0,
    lake_root: str = _LAKE_ROOT,
    min_bars: int = _MIN_BARS,
) -> tuple[list[str], DataProvider]:"""

if old not in src:
    print("Signature not found")
    raise SystemExit(2)
src = src.replace(old, new)

old2 = """    eligible.sort(key=_adv, reverse=True)
    selected = eligible if limit is None else eligible[:limit]
    return selected, _provider_from_frames(frames, min_bars)"""

new2 = """    eligible.sort(key=_adv, reverse=True)
    selected = eligible if limit is None else eligible[offset: offset + limit]
    return selected, _provider_from_frames(frames, min_bars)"""

if old2 not in src:
    print("Selection not found")
    raise SystemExit(3)
src = src.replace(old2, new2)

# Update docstring with offset chunking note
old3 = """    ``limit=None`` keeps every symbol and is what the profiling above used; it is available for
    deliberate, resourced runs, not for the daily cycle.
    \"\"\""""
new3 = """    ``limit=None`` keeps every symbol and is what the profiling above used; it is available for
    deliberate, resourced runs, not for the daily cycle.

    ``offset`` slices the ranked universe for CHUNKED cycles (slice0..slice5 timers): the daily
    campaign runs 6 x 50-symbol chunks instead of one 30-symbol cap, so the whole lake is tested
    every hour instead of the top-30 only. Chunks share the SAME provider (all frames are read
    and cached once), so COT/producer/funding columns attach identically in every slice.
    \"\"\""""
if old3 not in src:
    print("Docstring not found")
    raise SystemExit(4)
src = src.replace(old3, new3)

p.write_text(src)
print("Added offset to load_universe")