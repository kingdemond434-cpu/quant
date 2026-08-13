#!/usr/bin/env python3
"""Existing GPT Hunter with unified transcript, extreme, strategy and elite-intelligence missions.

Acquires changed public sources, truthfully attempts transcripts, and uses the configured GPT seat
for structured extraction.  One run/state/ledger serves video transcripts, extreme-return claims
and public systematic strategies.  It neither replaces Kimi nor creates three agents.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
from libs.llm.effort import reasoning_payload  # noqa: E402
from libs.research.public_strategy_hunter import load_sources, run  # noqa: E402

SOURCES = ROOT / "docs" / "research" / "GPT_HUNTER_SOURCES.json"
STATE = ROOT / "data" / "intelligence" / "gpt_hunter_state.json"
OUT = ROOT / "data" / "intelligence" / "public_strategy_items.json"
CORPUS = ROOT / "data" / "intelligence" / "gpt_practitioner_corpus.jsonl"
SECRETS = ROOT / "data" / "secrets" / "llm_panel.json"
MODEL = "openai/gpt-5.6-terra"


def _read(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _credentials() -> tuple[str, str]:
    secret = _read(SECRETS, {})
    if not isinstance(secret, dict):
        secret = {}
    key = str(
        secret.get("api_key") or secret.get("key") or os.environ.get("OPENROUTER_API_KEY", "")
    )
    base = str(secret.get("base_url") or "https://openrouter.ai/api/v1")
    if not key:
        raise RuntimeError("OpenRouter key unavailable; acquisition can retry without losing state")
    return base, key


def _ask(prompt: str) -> str:
    base, key = _credentials()
    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 8000,
            "temperature": 0.2,
            "reasoning": reasoning_payload(MODEL),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        OBJECTIVE_PREAMBLE + "\n"
                        "Extract only retrieved public evidence. You have zero capital, promotion or threshold "
                        "authority. Return the requested JSON and use null rather than inference."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=240, context=ssl.create_default_context()
    ) as response:
        payload = json.loads(response.read())
    message = payload["choices"][0]["message"]
    return str(message.get("content") or message.get("reasoning") or "")


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
