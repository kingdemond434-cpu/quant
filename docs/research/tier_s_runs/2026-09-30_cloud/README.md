# Tier S hourly run, cloud container, 2026-09-30

A full `desks/mt5/research/tier_s.py` pass run on #55's head in a cloud container, committed so
the programme's outputs exist on a branch. It took 607 s with no organ errors.

**This is NOT box evidence and counts toward no layer's DONE.** `box_evidence.json` here records
host `vm` with `counts_toward_done: false`. A layer is DONE only on the evidence the trading box
(vmi3571445) writes to `desks/mt5/data/tier_s/box_evidence.json` and publishes through its own
sync (`desks/mt5/scripts/sync_shadow_to_git.ps1`) once #55 is adopted there. The cloud has no
terminal, no live book and a partial copy of the desk's state, so several organs read
UNMEASURED here that the box will measure.
