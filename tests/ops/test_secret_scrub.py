from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

from libs.ops.secret_scrub import REDACTED, scrub

ROOT = Path(__file__).resolve().parents[2]
# Fake key, built so no tracked file carries the literal shape.
FAKE_KEY = "AI" + "za" + "Q" * 35


def test_scrub_reaches_nested_strings_and_keys() -> None:
    payload = {
        "items": [{"text": f"key={FAKE_KEY}&q=gold", "tags": (FAKE_KEY, "ok")}],
        FAKE_KEY: 3,
        "n": 7,
    }
    out = scrub(payload)
    assert FAKE_KEY not in json.dumps(out)
    assert out["items"][0]["text"] == f"key={REDACTED}&q=gold"
    assert out["items"][0]["tags"] == (REDACTED, "ok")
    assert out[REDACTED] == 3 and out["n"] == 7


def test_scrub_leaves_ordinary_text_alone() -> None:
    text = "AIzaShort and a sentence about gold carry"
    assert scrub(text) == text


def test_alpha_frontier_producer_never_writes_a_key(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_alpha_frontier as producer

    monkeypatch.setattr(producer, "OUT", tmp_path / "daily_alpha_frontier.json")
    monkeypatch.setattr(producer, "build", lambda: {
        "practitioner_frontier": {"new_mechanisms": [f"see {FAKE_KEY}"]},
        "high_priority_residuals": [],
    })
    # The summary print may want fields the stub lacks; the write comes first.
    with contextlib.suppress(KeyError, TypeError):
        producer.main()
    assert FAKE_KEY not in (tmp_path / "daily_alpha_frontier.json").read_text("utf-8")
