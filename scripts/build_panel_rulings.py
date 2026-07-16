"""Panel finding-memory -> docs/research/panel_rulings.md (the panel's graveyard).

Cross-run memory so a finding already ruled on isn't re-triaged every cycle (wasted judgment).
Digests data/panel_verdicts.jsonl (the CRO records one line per triaged finding) into a compact
running ledger, emphasising REJECTED rulings (don't re-raise without NEW evidence) and
IMPLEMENTED ones (don't re-propose). The CRO reads this at triage STEP 3 BEFORE evaluating new
panel output -- exactly like checking the alpha graveyard before testing a hypothesis. A new
finding matching a prior REJECT with no new evidence -> skip, log "already ruled".

    python scripts/build_panel_rulings.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_VERDICTS = Path("data/panel_verdicts.jsonl")
_OUT = Path("docs/research/panel_rulings.md")
_ACTIVE = {"reject": "REJECTED", "implement_now": "IMPLEMENTED", "queue": "QUEUED",
           "flag": "FLAGGED"}


def main() -> None:
    rows = []
    if _VERDICTS.exists():
        for line in _VERDICTS.read_text("utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    # newest first; a later ruling on the same finding supersedes an earlier one
    rows.reverse()
    seen: set[str] = set()
    by_verdict: dict[str, list[dict]] = {v: [] for v in _ACTIVE.values()}
    for r in rows:
        finding = str(r.get("finding", "")).strip()
        keyv = finding.lower()[:80]
        if not finding or keyv in seen:
            continue
        seen.add(keyv)
        label = _ACTIVE.get(str(r.get("verdict", "")))
        if label:
            by_verdict[label].append(r)
    parts = [
        "# Panel rulings -- cross-run finding memory (the panel's graveyard)",
        f"Updated {datetime.now(tz=UTC).date().isoformat()}. CHECK THIS BEFORE triaging new "
        "panel output: a finding matching a prior REJECT with no NEW evidence is already ruled "
        "-- skip it, log 'already ruled', do not re-litigate. Supersede a ruling only with new "
        "code/market evidence.", ""]
    for label in ("REJECTED", "IMPLEMENTED", "QUEUED", "FLAGGED"):
        items = by_verdict[label]
        parts.append(f"## {label} ({len(items)})")
        for r in items:
            why = f" -- {r.get('reason')}" if r.get("reason") else ""
            parts.append(f"- [{r.get('provider', '?')}/{r.get('mission', '?')}] "
                         f"{r.get('finding', '')}{why}")
        parts.append("")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(parts), "utf-8")
    n = sum(len(v) for v in by_verdict.values())
    print(f"panel rulings -> {_OUT} ({n} distinct rulings; "
          f"{len(by_verdict['REJECTED'])} rejected)")


if __name__ == "__main__":
    main()
