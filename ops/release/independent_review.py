#!/usr/bin/env python3
"""The independent-review job: a model reviewer reads the PR's whole diff against
ops/release/review_rubric.md and returns a verdict. The job succeeds only on PASS.

Runs from the BASE checkout; the PR's code is never executed here (the diff is fetched as text
through the API). Fails closed: no key, a diff too large to read whole, a head that moved, a
refusal, a malformed answer, or any concern flagged as risk or control is a FAIL.

    ANTHROPIC_API_KEY=... GH_TOKEN=... python -I ops/release/independent_review.py \
        --repo o/r --pr 7 --head <sha>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5-5"
#: Above this the diff is not reviewed in part: the PR fails and takes the manual path.
MAX_DIFF_CHARS = 600_000
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "risk_increasing": {"type": "boolean"},
        "touches_control": {"type": "boolean"},
        "findings": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["verdict", "risk_increasing", "touches_control", "findings", "summary"],
    "additionalProperties": False,
}


def _gh(*args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True, env=env, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"gh api {args[0]}: {p.stderr.strip()[:300]}")
    return p.stdout


def decide(answer: dict[str, Any]) -> tuple[bool, str]:
    """PASS needs the reviewer's PASS and neither flag."""
    if answer.get("risk_increasing") is not False:
        return False, "the reviewer flagged a risk increase"
    if answer.get("touches_control") is not False:
        return False, "the reviewer flagged a change to control machinery"
    if answer.get("verdict") != "PASS":
        return False, "the reviewer did not pass it"
    return True, "PASS"


def review(diff: str, files: list[str], client: Any) -> dict[str, Any]:
    rubric = (HERE / "review_rubric.md").read_text(encoding="utf-8")
    user = (
        "Files changed:\n"
        + "\n".join(files)
        + "\n\n<diff>\n"
        + diff
        + "\n</diff>\n\nReview the whole diff against the rubric and answer with the JSON."
    )
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=rubric,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        return {"verdict": "FAIL", "risk_increasing": True, "touches_control": True,
                "findings": ["the reviewer declined"], "summary": "refusal"}  # fmt: skip
    if msg.stop_reason != "end_turn":
        raise RuntimeError(f"the review stopped early ({msg.stop_reason})")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("FAIL: REVIEWER_API_KEY is not configured for this repository")
        return 1
    diff = _gh(f"repos/{a.repo}/pulls/{a.pr}", "-H", "Accept: application/vnd.github.diff")
    pr = json.loads(_gh(f"repos/{a.repo}/pulls/{a.pr}"))
    if pr["head"]["sha"] != a.head:
        print("FAIL: the head moved while the diff was read; the new head gets its own review")
        return 1
    if len(diff) > MAX_DIFF_CHARS:
        print(f"FAIL: the diff is {len(diff)} characters, too large to review whole")
        return 1
    files = [
        f["filename"]
        for page in json.loads(
            _gh(f"repos/{a.repo}/pulls/{a.pr}/files?per_page=100", "--paginate", "--slurp")
        )
        for f in page
    ]
    import anthropic

    answer = review(diff, files, anthropic.Anthropic())
    ok, why = decide(answer)
    print(json.dumps(answer, indent=2))
    print(f"independent review @ {a.head[:9]}: {'PASS' if ok else 'FAIL'} ({why})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
