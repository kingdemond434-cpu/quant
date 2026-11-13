#!/usr/bin/env python3
"""Existing GPT Hunter with unified transcript, extreme, strategy and elite-intelligence missions.

Acquires changed public sources, truthfully attempts transcripts, and uses the configured GPT seat
for structured extraction.  One run/state/ledger serves video transcripts, extreme-return claims
and public systematic strategies.  It neither replaces Kimi nor creates three agents.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
from libs.ops import llm_seat  # noqa: E402
from libs.research.public_strategy_hunter import load_sources, run  # noqa: E402

SOURCES = ROOT / "docs" / "research" / "GPT_HUNTER_SOURCES.json"
STATE = ROOT / "data" / "intelligence" / "gpt_hunter_state.json"
OUT = ROOT / "data" / "intelligence" / "public_strategy_items.json"
CORPUS = ROOT / "data" / "intelligence" / "gpt_practitioner_corpus.jsonl"
#: FREE CHAIN ONLY (2026-11-04). The seat named `openai/gpt-5.6-terra`, a paid id, so
#: `libs.ops.openrouter_guard` refused every request and the seat wrote 0 rows. The desk runs
#: :free models only; the chain walks down on any failure so one rate-limited id never zeroes a
#: day. MODEL stays as the first id for callers that read it.
MODEL_CHAIN: tuple[str, ...] = (
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-235b-a22b:free",
    "moonshotai/kimi-k2:free",
)
MODEL = MODEL_CHAIN[0]


def _read(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


_SYSTEM = (
    OBJECTIVE_PREAMBLE + "\n"
    "Extract only retrieved public evidence. You have zero capital, promotion or threshold "
    "authority. Return the requested JSON and use null rather than inference."
)


def _ask(prompt: str) -> str:
    """One extraction through `libs.ops.llm_seat`, walking the :free chain.

    THROUGH THE SEAT, NOT A RAW urllib CALL (2026-11-11). A bypass wrote no row to
    `data/llm_spend.jsonl`, so this seat's tokens were invisible to the per-job token report, and
    it skipped the seat's free-tier daily budget check, which protects every other organ on the
    same key. The seat's own guard still refuses any non-free id.
    """
    base_seat = llm_seat.primary_seat()
    if base_seat is None:
        raise RuntimeError("OpenRouter key unavailable; acquisition can retry without losing state")
    last = "no model tried"
    for model in MODEL_CHAIN:
        text, err = llm_seat.chat(prompt, system=_SYSTEM, seat=replace(base_seat, model=model),
                                  max_tokens=8000, temperature=0.2)
        if not err and text.strip():
            return text
        last = f"{model}: {err or 'empty reply'}"
    raise RuntimeError(f"every free model failed; last: {last}")


def main() -> int:
    state = _read(STATE, {})
    state = state if isinstance(state, dict) else {}
    sources = load_sources(SOURCES, state.get("discovered_sources", []))
    report = run(sources, state, _ask)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    STATE.write_text(json.dumps(report["state"], indent=1), "utf-8")
    # Append every attempt, including failures: unavailable transcripts and duplicate-heavy
    # sources are economic source evidence and must not vanish from ROI accounting.
    with CORPUS.open("a", encoding="utf-8") as handle:
        for item in report["items"]:
            handle.write(json.dumps(item, default=str) + "\n")
    print(
        f"gpt-hunter: {len(report['items'])} new items, {len(report['failures'])} failures; "
        "missions=transcript/extreme-return/public-strategy/global-capability; "
        "discovered sources are promoted into the next sweep; Kimi unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
