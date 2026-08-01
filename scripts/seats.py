"""Resolve LOGICAL seat requests against the LIVE panel roster.

WHY THIS EXISTS (the defect it closes): six organs -- meta_architect, breadth_expander,
llm_blind_researcher, hypothesis_generator, collector_author, llm_code_auditor -- hardcoded
literal model IDs in git and then looked them up in data/secrets/llm_panel.json by EXACT STRING.
The moment the roster upgraded a seat, `provs.get(seat)` returned None and the organ SILENTLY
dropped that model (`continue`, no log in most of them). A three-seat organ could degrade to one
seat, or to zero, without a single line of output. That made roster upgrades the single most
dangerous thing the desk could do to its own organs -- exactly backwards, since upgrades are
supposed to be an improvement.

THE FIX: hardcoded IDs become PREFERENCES, not requirements. A preferred model that is still
seated is used unchanged (no behaviour change on a stable roster -- this is a no-op until an
upgrade actually happens). A preferred model that is GONE is replaced from the live roster,
preferring the SAME LAB (the substitute most likely to have the same blind spots the seat was
chosen for), then any unused lab. Every substitution is printed AND paged, because a silent
substitution is the same failure class as a silent drop -- the organ must never quietly change
what it is without the desk knowing.

DIVERSITY IS PRESERVED BY CONSTRUCTION: `distinct_labs=True` (the default) guarantees the
returned seats span distinct labs, which is the property every one of these organs was designed
around ("deliberately DIVERSE labs -- shared training data would defeat the purpose").

Pure + testable: `resolve_ids` takes plain data and returns plain data, so the substitution
logic is unit-tested without keys, network, or a roster file on disk.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data/secrets/llm_panel.json"
_LOG = ROOT / "data/seat_substitutions.jsonl"


def lab(model_id: str) -> str:
    """Lab (vendor) prefix of an OpenRouter model id: 'x-ai/grok-4.3' -> 'x-ai'."""
    return str(model_id).split("/", 1)[0].lower()


def load_roster(path: Path | None = None) -> list[dict[str, Any]]:
    """Live provider records from the panel roster; [] when the file is absent (manual mode)."""
    p = path or KEYS
    if not p.exists():
        return []
    try:
        provs = json.loads(p.read_text("utf-8")).get("providers", [])
    except (json.JSONDecodeError, OSError):
        return []
    return [x for x in provs if isinstance(x, dict) and x.get("model")]


def resolve_ids(preferred: list[str], roster_ids: list[str], n: int | None = None,
                *, distinct_labs: bool = True) -> tuple[list[str], list[tuple[str, str | None]]]:
    """PURE core: map preferred ids onto what is actually seated.

    Returns (chosen_ids, substitutions) where each substitution is (wanted, got-or-None).
    Rules, in order:
      1. A preferred id still in the roster is KEPT (stable roster => exact old behaviour).
      2. A missing preferred id is replaced from the SAME LAB first (closest cognitive match),
         else from any lab not already represented.
      3. `distinct_labs` never lets a replacement duplicate a lab already chosen -- the panel's
         whole value is uncorrelated lineages, and a substitution must not quietly collapse that.
      4. If nothing can replace it, the seat is reported as lost (wanted, None) rather than
         silently dropped. Callers decide whether to run short-handed or abort.
    """
    live = list(dict.fromkeys(roster_ids))
    chosen: list[str] = []
    subs: list[tuple[str, str | None]] = []
    used_labs: set[str] = set()

    def _take(mid: str) -> None:
        chosen.append(mid)
        used_labs.add(lab(mid))

    for want in preferred:
        if n is not None and len(chosen) >= n:
            break
        if want in live and want not in chosen and not (distinct_labs and lab(want) in used_labs):
            _take(want)
            continue
        if want in chosen:
            continue
        pool = [m for m in live if m not in chosen
                and not (distinct_labs and lab(m) in used_labs)]
        same_lab = [m for m in pool if lab(m) == lab(want)]
        pick = (same_lab or pool)
        if pick:
            _take(pick[0])
            subs.append((want, pick[0]))
        else:
            subs.append((want, None))

    # top up to n from any remaining distinct lab (a caller asking for 3 gets 3 when possible)
    if n is not None:
        for m in live:
            if len(chosen) >= n:
                break
            if m in chosen or (distinct_labs and lab(m) in used_labs):
                continue
            _take(m)
    return chosen, subs


def _page(msg: str) -> None:
    """Best-effort ntfy page; never raises into the caller (an organ must not die on telemetry)."""
    try:
        cfg = json.loads((ROOT / "data/secrets/ntfy.json").read_text("utf-8"))
        topic = cfg.get("topic") or cfg.get("ntfy_topic")
        if not topic:
            return
        subprocess.run(["curl", "-fsS", "-m", "10", "-H", "Title: SEATS",
                        "-d", msg, f"https://ntfy.sh/{topic}"],
                       check=False, capture_output=True, timeout=15)
    except Exception:
        return


def resolve(preferred: list[str], n: int | None = None, *, distinct_labs: bool = True,
            role: str = "", roster: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Provider records for a logical seat request, substituting for upgraded-away models.

    `role` is a human label used in the substitution log/page so the principal can see WHICH
    organ changed shape, not just that something did.
    """
    provs = roster if roster is not None else load_roster()
    by_id = {str(p["model"]): p for p in provs}
    chosen, subs = resolve_ids(preferred, list(by_id), n, distinct_labs=distinct_labs)
    if subs:
        lines = [f"{w} -> {g or 'LOST (no substitute)'}" for w, g in subs]
        print(f"  seats[{role or '?'}]: roster changed -- " + "; ".join(lines))
        try:
            _LOG.parent.mkdir(parents=True, exist_ok=True)
            with _LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"role": role, "preferred": preferred,
                                    "chosen": chosen,
                                    "subs": [[w, g] for w, g in subs]}) + "\n")
        except OSError:
            pass
        if any(g is None for _, g in subs):
            _page(f"seat LOST in {role or 'organ'}: " + "; ".join(lines))
    return [by_id[m] for m in chosen]
