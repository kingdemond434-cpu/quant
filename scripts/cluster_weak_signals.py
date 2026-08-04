#!/usr/bin/env python3
"""READ THE WEAK-SIGNAL REGISTRY AND CLUSTER IT -- the caller libs/hypmax/emergence never had.

WHY IT EXISTS. `docs/research/weak_signal_registry.md` has accumulated WS-001..WS-005 under
Charter §23, whose promotion rule is explicit: two or more weak signals from INDEPENDENT discovery
paths converging on the same direction auto-promote to hypothesis generation. `libs/hypmax/
emergence.py` implements exactly that clustering -- and its own docstring says the registry "is
read by NO code", calling it a genuine miss. It stayed unread, so convergence was checked by
whoever happened to remember, which is the same as not being checked.

Individually weak observations are precisely what a per-observation significance bar destroys by
construction. A cluster's strength is SUPER-ADDITIVE in member count because independent observers
converging on one direction is qualitatively different from one observer repeating themselves --
that is the whole argument for retaining them, and it only pays if something actually looks.

Read-only over docs/. Writes one artifact. No network, no keys.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hypmax.emergence import Observation, WeakSignalRegistry  # noqa: E402

REGISTRY = ROOT / "docs/research/weak_signal_registry.md"
REPORT = ROOT / "data/weak_signal_clusters.json"

#: `### WS-003 something                    [observations: 4]`
_HEAD = re.compile(r"^###\s+(WS-\d+)\s+(.*?)\s*(?:\[observations:\s*(\d+)\])?\s*$")
_FIELD = re.compile(r"^(first-seen|latest|direction|status):\s*(.*)$", re.I)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def parse(path: Path) -> list[Observation]:
    """Registry markdown -> observations. A malformed block is skipped, never guessed at.

    Tags come from the WS id AND from the `direction:` line's significant words, so two entries
    pointing the same way cluster even when nobody thought to tag them alike -- which is the
    convergence the §23 rule is about and the part a human reader reliably misses.
    """
    if not path.exists():
        return []
    out: list[Observation] = []
    cur: dict[str, str] = {}
    for raw in path.read_text("utf-8", errors="ignore").splitlines():
        m = _HEAD.match(raw.strip())
        if m:
            if cur.get("id"):
                out.append(_to_obs(cur))
            cur = {"id": m.group(1), "text": m.group(2), "n": m.group(3) or "1"}
            continue
        f = _FIELD.match(raw.strip())
        if f and cur.get("id"):
            cur[f.group(1).lower()] = f.group(2)
    if cur.get("id"):
        out.append(_to_obs(cur))
    return out


# STOPWORDS MATTER MORE HERE THAN IN ORDINARY TEXT WORK. The first run clustered on "when" and
# "desk" -- filler that appears in every entry, so it converges by construction and reports a
# cluster where no two observations agree about anything. A convergence detector that fires on
# grammar is worse than none: it produces exactly the confident-looking output nobody checks.
_STOP = {
    "the", "a", "an", "of", "to", "is", "in", "and", "that", "for", "on", "it", "as", "are",
    "was", "be", "not", "but", "with", "this", "its", "by", "from", "at", "or", "when", "then",
    "than", "into", "over", "under", "each", "them", "they", "their", "there", "here", "what",
    "which", "while", "have", "has", "had", "been", "were", "will", "would", "does", "did",
    "desk", "signal", "weak", "more", "most", "some", "only", "also", "such", "very", "much",
    "same", "other", "another", "about", "after", "before", "because", "being", "both", "even",
}


def _to_obs(d: dict[str, str]) -> Observation:
    words = re.findall(r"[a-z]{4,}", d.get("direction", "").lower())
    tags = tuple({d["id"], *[w for w in words if w not in _STOP][:6]})
    n = max(1, int(d.get("n", "1") or 1))
    return Observation(
        text=f"{d['id']} {d.get('text', '')}".strip(), tags=tags,
        source=d.get("first-seen", ""),
        # Observation count raises strength SUBLINEARLY: a registry entry seen five times is
        # stronger than one seen once, and nowhere near five times stronger -- the same reason
        # cluster strength uses sqrt(n) rather than n.
        strength=min(0.9, 0.3 * (n ** 0.5)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--min-size", type=int, default=2,
                    help="Charter §23: two independent paths converging is the promotion bar")
    a = ap.parse_args()

    src = Path(a.registry) if a.registry else REGISTRY
    obs = parse(src)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not obs:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO OBSERVATIONS",
            "reason": f"{_rel(src)} absent or contains no parsable WS-<n> blocks",
        }, indent=1), "utf-8")
        print(f"weak-signals: nothing parsable in {_rel(src)}")
        return 0

    reg = WeakSignalRegistry()
    for o in obs:
        reg.add(o)
    clusters = reg.clusters(min_size=a.min_size)
    tags = reg.tag_counts()

    out = {
        "ts": datetime.now(tz=UTC).isoformat(), "source": _rel(src),
        "observations": len(obs), "min_size": a.min_size,
        "clusters": clusters,
        "top_tags": dict(tags.most_common(12)),
        "note": ("Charter §23: two weak signals from INDEPENDENT discovery paths converging on one "
                 "direction auto-promote to hypothesis generation. Cluster strength is "
                 "super-additive in member count -- independent observers converging is "
                 "qualitatively different from one observer repeating themselves."),
        "authority": "NONE. Surfaces convergence; pre-registers and promotes nothing.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"weak-signals: {len(obs)} observations from {_rel(src)} -> {len(clusters)} "
          f"converging cluster(s) at min_size={a.min_size}")
    for c in clusters[:8]:
        tag = c.get("tag", "?")
        print(f"  {tag!s:<22} n={c.get('n', 0):<3} strength {float(c.get('strength', 0)):.2f}")
    if not clusters:
        print("  no convergence yet -- correct and expected while entries point different ways")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
