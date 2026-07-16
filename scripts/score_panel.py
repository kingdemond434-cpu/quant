"""Score each advisory-panel provider by validated hit-rate -> data/panel_scorecard.json.

Makes the panel SELF-PRUNING: models whose findings repeatedly validate earn trust and higher
triage priors; models that produce noise get down-weighted and eventually dropped from
data/secrets/llm_panel.json (saving cost + inbox clutter). Run at monthly governance.

Inputs:
  data/external_panel_log.jsonl  -- every response (auto, per run): {ts, mission, provider, ...}
  data/panel_verdicts.jsonl      -- the CRO records ONE line per triaged finding during weekly
                                    triage: {ts, provider, mission, finding, verdict, outcome}
       verdict  in implement_now | queue | flag | reject
       outcome  in validated | falsified | pending   (filled when the gauntlet/forward evidence
                                                       lands; implemented+validated = the win)

hit_rate = validated / (validated + falsified)   -- pending findings don't count yet.
Providers with < _MIN_SCORED scored findings show hit_rate=null (not enough evidence).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

_LOG = Path("data/external_panel_log.jsonl")
_VERDICTS = Path("data/panel_verdicts.jsonl")
_OUT = Path("data/panel_scorecard.json")
_MIN_SCORED = 5


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def main() -> None:
    responses = _read_jsonl(_LOG)
    verdicts = _read_jsonl(_VERDICTS)
    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"responses": 0, "actioned": 0, "validated": 0, "falsified": 0, "rejected": 0})
    for r in responses:
        if "response" in r:
            stats[r.get("provider", "?")]["responses"] += 1
    for v in verdicts:
        s = stats[v.get("provider", "?")]
        if v.get("verdict") in ("implement_now", "queue"):
            s["actioned"] += 1
        if v.get("verdict") == "reject":
            s["rejected"] += 1
        if v.get("outcome") == "validated":
            s["validated"] += 1
        elif v.get("outcome") == "falsified":
            s["falsified"] += 1
    board = {}
    for prov, s in sorted(stats.items()):
        scored = s["validated"] + s["falsified"]
        board[prov] = {**s, "scored": scored,
                       "hit_rate": round(s["validated"] / scored, 3)
                       if scored >= _MIN_SCORED else None}
    out = {"updated": datetime.now(tz=UTC).isoformat(),
           "policy": (f"hit_rate = validated/(validated+falsified); null until >= {_MIN_SCORED} "
                      "scored findings. Down-weight/drop persistent low scorers at monthly "
                      "governance; consensus-across-models still outranks any single provider."),
           "providers": board}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    ranked = [(p, b["hit_rate"]) for p, b in board.items() if b["hit_rate"] is not None]
    ranked.sort(key=lambda kv: -(kv[1] or 0))
    print(f"panel scorecard -> {_OUT} ({len(board)} providers; "
          f"{len(ranked)} with enough evidence to rank)")
    for p, hr in ranked:
        print(f"  {p:16s} hit_rate {hr}")


if __name__ == "__main__":
    main()
