"""THE DESIRED-STATE CONTROL PLANE -- one reconciliation system for the whole desk.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

The desk had several working definitions of "wired" -- imported, scheduled, started, returned
zero, left a file -- and that is why stale, silent and unconsumed organs kept reappearing and why
each one grew its own fixer. LAWS.md 7 replaced all of them with one law:

    WIRED = scheduled AND executed AND progressed AND produced owned output
            AND consumer acknowledged it
    CLOSED LOOP = every required edge's producer -> consumer observed inside valid
                  freshness leases

This package is that law's machinery, and nothing here decides its own health:

    specs        the ComponentSpec every executable organ must carry (the registry's shape)
    watermarks   PROGRESS heartbeats -- a PID is not health, a moving work counter is
    lease        FRESHNESS as a lease with a TTL and an artifact envelope, never a file mtime
    edges        the mandatory producer -> consumer edges and the lineage store that proves them
    actuators    repairs that must prove a POSTCONDITION; a return code of 0 is never proof
    scheduler_gen  the schedule GENERATED from the registry, so "built but never clocked" cannot
    fingerprints operational negative knowledge: a defect seen twice owes an invariant test
    reconciler   the one organ that observes, assigns state and plans the repair work

Only the reconciler may assign HEALTHY. A component cannot certify itself.
"""
from __future__ import annotations

from libs.ops.control_plane.specs import (
    CRITICALITY,
    STATES,
    UNMEASURED,
    ComponentSpec,
    Registry,
    derive_max_silence,
)

__all__ = ["CRITICALITY", "STATES", "UNMEASURED", "ComponentSpec", "Registry",
           "derive_max_silence"]
