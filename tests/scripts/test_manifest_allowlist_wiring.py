"""An allowlisted row that no manifest schedule matches is wiring theatre (gap-fixer 2026-08-26).

`run_manifest_dispatch` resurrects `ops/crontab.manifest` rows after root cron OOM-died on
2026-08-20. The allowlist only GATES which rows may fire; schedule and command are read LIVE
from the manifest. So a token that is allowlisted but has no manifest row -- or a row whose cron
never matches -- is counted as covered, removed from the backlog number, and never runs. That is
the exact shape of the failure this dispatcher exists to end, re-created one layer up.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.run_manifest_dispatch import ALLOWLIST, MANIFEST, TOKEN_RE, cron_matches


def _manifest_rows() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in MANIFEST.read_text("utf-8", errors="ignore").split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        m = TOKEN_RE.search(line)
        if m:
            rows.setdefault(m.group(0), " ".join(line.split()[:5]))
    return rows


def test_every_allowlisted_token_has_a_manifest_row():
    """Coverage claimed on a token the manifest does not carry is coverage that cannot fire."""
    rows = _manifest_rows()
    missing = sorted(t for t in ALLOWLIST if t not in rows)
    assert not missing, f"allowlisted but unschedulable: {missing}"


def test_every_allowlisted_token_fires_within_a_week():
    """A cron that never matches is the same silence as no row at all, and it is harder to see."""
    rows = _manifest_rows()
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    never = []
    for token in sorted(ALLOWLIST):
        spec = rows.get(token)
        if spec is None:
            continue  # covered by the test above
        if not any(cron_matches(spec, now + timedelta(minutes=i))
                   for i in range(1, 60 * 24 * 8)):
            never.append(f"{token} [{spec}]")
    assert not never, f"allowlisted but never fires within 8 days: {never}"


def test_every_allowlist_reason_is_a_real_sentence():
    """The reason is the audit trail. An entry justified by its own filename is a guess wearing
    a citation, and the next reader cannot tell it from a verified one."""
    thin = sorted(t for t, why in ALLOWLIST.items() if len(why) < 25)
    assert not thin, f"allowlist entries with no real justification: {thin}"
