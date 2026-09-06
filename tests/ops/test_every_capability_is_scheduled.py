"""Every capability names a scheduler, and that scheduler resolves to something that really runs.

WHY A SEPARATE FENCE FROM THE CEILING AUDITOR. The auditor derives a capability's STAGE from its
surfaces, so "SCHEDULED" there means a surface was NAMED. It cannot tell a named surface that
exists from a named surface that does not, and it cannot see a capability whose surface list is
empty because the lookup asked the wrong question. Both happened:

  P0.1  named its own ARTIFACT as owner -- the only row of 94 to do so -- so `scheduler_for`
        searched the schedulers for a cron line running `release_identity.json`, found none, and
        returned []. It WAS genuinely unscheduled, and `release_identity.py` had a main() that
        nothing on either machine ever called; but an empty list from a lookup that could never
        have succeeded is not evidence of that, and the report could not tell the two apart.

  24 more resolved only through `daily_cycle.py`, which is scheduled from INSIDE `hourly_cycle`
        rather than by any unit file -- so a fence that searched `ops/` alone would have called
        two dozen live capabilities unscheduled and taught everyone to ignore its output.

This test therefore checks the CONCLUSION -- something on some machine actually runs this -- over
the union of every scheduling mechanism the desk uses: systemd units, the crontab manifests, the
Windows task installers, and the Python cycles that schedule most of the desk from inside a loop.
A new capability that lands with no way to run is caught here, before anyone reads its absent
artifact as a quiet market.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

#: Every mechanism this desk uses to make something run. A surface counts as real if it is named
#: by any of them -- the desk is two machines with different schedulers and one list cannot be
#: authoritative for both.
CYCLES = (
    "desks/mt5/research/hourly_cycle.py",
    "desks/mt5/research/daily_cycle.py",
    "desks/mt5/research/nightly_catchup.py",
)
CRONTABS = (
    "ops/crontab.required",
    "ops/crontab.manifest",
    "ops/crontab.research.manifest",
)


def _blob(paths) -> str:
    out = []
    for rel in paths:
        p = ROOT / rel
        if p.exists():
            out.append(p.read_text("utf-8", errors="ignore"))
    return "\n".join(out)


@pytest.fixture(scope="module")
def surfaces() -> dict:
    units = {p.stem for p in (ROOT / "ops").glob("*.timer")}
    units |= {p.stem for p in (ROOT / "ops").glob("*.service")}
    return {
        "units": units,
        "cron": _blob(CRONTABS),
        "windows": "\n".join(p.read_text("utf-8", errors="ignore")
                             for p in (ROOT / "desks" / "mt5" / "scripts").rglob("*.ps1")),
        "cycles": _blob(CYCLES),
    }


@pytest.fixture(scope="module")
def capabilities() -> list[dict]:
    from blueprint import coverage
    caps = coverage.registry()["capabilities"]
    assert caps, "the blueprint registry produced no capabilities at all"
    return caps


def _runs_somewhere(named, surfaces: dict) -> bool:
    for entry in named or []:
        stem = str(entry).replace(".timer", "").replace(".service", "").split("/")[-1]
        if not stem:
            continue
        if stem in surfaces["units"]:
            return True
        if str(entry) in surfaces["cron"] or stem in surfaces["cron"]:
            return True
        if stem in surfaces["windows"] or stem in surfaces["cycles"]:
            return True
    return False


def test_every_capability_resolves_to_a_scheduler_that_exists(capabilities, surfaces) -> None:
    orphans = [(c["id"], c.get("scheduler")) for c in capabilities
               if not _runs_somewhere(c.get("scheduler"), surfaces)]
    assert not orphans, (
        "capabilities whose scheduler names nothing that exists -- each is a capability that "
        "cannot run, reported as though it merely has not produced yet:\n  "
        + "\n  ".join(f"{cid}: {named}" for cid, named in orphans)
    )


def test_no_capability_names_its_own_artifact_as_its_owner(capabilities) -> None:
    """A data file cannot be a producer, and naming one breaks every lookup keyed on the owner.

    This is how P0.1 hid: `scheduler_for` resolves the OWNER's stem against the schedulers, so an
    owner of `release_identity.json` made the search unanswerable rather than negative.
    """
    confused = [c["id"] for c in capabilities
                if (c.get("producer") or "").strip()
                and (c.get("producer") or "") in (c.get("artifacts") or [])]
    assert not confused, (
        "capabilities whose producer IS their artifact -- no lookup keyed on the owner can "
        f"succeed for these: {confused}"
    )


def test_the_release_identity_leg_is_actually_in_the_hourly_cycle() -> None:
    """The specific regression, pinned. P0.1 answers whether the code that is TRADING is the code
    that was sealed -- the assumption every other capability's evidence rests on -- and it was the
    one capability of 94 that nothing ran."""
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"release_identity"' in src, "the release-identity leg is not in the hourly cycle"
    assert "mt5desk/release_identity.py" in src, "the leg does not point at the producing module"
