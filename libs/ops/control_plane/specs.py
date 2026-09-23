"""THE COMPONENT SPEC -- what must be true about one executable organ, declared once.

WHY A SPEC IS MANDATORY. Every recurring operational defect on this desk came from a fact nobody
had written down: what an organ consumes, what it owns, who reads it, how often it must run, how
long silence may last before silence is a fault, what "progress" means for it, and what to do when
it stops. Each of those was rediscovered by hand, one incident at a time, and each rediscovery
grew its own fixer. A spec is the alternative: ONE declaration the reconciler reads, and a birth
fence (`scripts/check_component_registry.py`) that refuses an executable without one.

MAX SILENCE IS DERIVED, NEVER FLAT. The clock fixer carried `4 * 3600` for every resident --
identical for a department whose pass may legitimately take three hours and for a moat swarm whose
pass is capped at thirty-one minutes. One number cannot be right for both: it is far too tight for
the first and useless for the second, which is why a dead swarm could sit unnoticed for hours.
`derive_max_silence` computes it from the component's own cadence and timeout instead.

UNMEASURED IS A VALUE. A field this repo does not know is the string `UNMEASURED`, by name, and it
never becomes a default that reads like a measurement (L1.28a). A spec with `cadence_s=None` says
"nothing here declares when this runs" -- which is a finding, not a pass.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

#: The one string for "this tree does not know". Never a zero, never an empty string.
UNMEASURED = "UNMEASURED"

#: The universal state model (LAWS.md 7). Only the external reconciler assigns HEALTHY.
STATES: tuple[str, ...] = ("DECLARED", "STARTING", "HEALTHY", "DEGRADED", "STALE", "STALLED",
                           "BROKEN", "REPAIRING", "QUARANTINED", "RETIRED")

#: A required component's failure makes the reconciler red and its process exit non-zero; an
#: optional one DEGRADES with a named reason. There is no third value: "sort of required" is how
#: a fence stops being a fence.
CRITICALITY: tuple[str, ...] = ("required", "optional")

#: Where a component runs. `box` is the Windows trading box (Task Scheduler), `vps` the Hetzner
#: research host (systemd user timers); `any` is a library-grade executable with no host claim.
HOSTS: tuple[str, ...] = ("box", "vps", "any")

#: The kinds of executable organ this desk has. The birth fence does not care which; the
#: scheduler generator does (only `task` and `timer` kinds own a schedule row).
#: `library` is an executable file (it has a main()) that a CLOCKED organ imports: it runs every
#: time that organ runs, so it is reached rather than scheduled, and it is never "unclocked".
KINDS: tuple[str, ...] = ("leg", "daily_step", "task", "timer", "resident", "actuator",
                          "federation_worker", "executable", "library")

#: The floor under a derived max_silence. Below this, ordinary scheduler jitter and a slow disk
#: read as a fault, and a fixer that restarts healthy organs is worse than no fixer at all.
MIN_SILENCE_S = 300


def derive_max_silence(cadence_s: int | None, timeout_s: int | None = None) -> int | None:
    """How long this component may be silent before silence is a DEFECT.

    Two clocks bound it and the larger wins:

      * 2x cadence -- a component that has missed two consecutive firings is not late, it is
        stopped. This is the general rule and it is what the brief names.
      * timeout + cadence -- for a component whose single pass may run far longer than its
        trigger repeats (every 24/7 resident: a ten-minute keep-alive around a three-hour pass),
        2x cadence would declare a perfectly healthy long pass dead every twenty minutes.

    UNMEASURED cadence yields None, which the reconciler reports as UNMEASURED rather than
    inventing a window. An undeclared cadence is a finding about the registry, not about the
    organ, and filling it in here would hide exactly the thing the registry exists to surface.
    """
    if cadence_s is None or cadence_s <= 0:
        return None
    by_cadence = 2 * cadence_s
    by_pass = (timeout_s + cadence_s) if timeout_s and timeout_s > 0 else 0
    return max(MIN_SILENCE_S, by_cadence, by_pass)


@dataclass(frozen=True)
class ComponentSpec:
    """The mandatory declaration for one executable organ.

    Every field the principal's spec names is here. Unknown ones carry `UNMEASURED` (strings) or
    `None` (numbers) -- present and named, never absent and never silently zero.
    """

    component_id: str
    kind: str = "executable"
    host: str = "any"
    #: Repo-relative paths whose content IS this component. The birth fence matches an executable
    #: file to a spec through this list, and `code_identity` hashes exactly these.
    code_paths: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    #: Seconds between firings. None = this repo does not declare a cadence for it.
    cadence_s: int | None = None
    #: Seconds of silence after which silence is a fault. Derived, never written by hand.
    max_silence_s: int | None = None
    #: The name of the monotone counter that proves WORK, not liveness: `sources_scanned`,
    #: `trial_id`, `last_bar_seen`, `book_generation`, `epoch_id`.
    progress_metric: str = UNMEASURED
    #: The argv this component is run with in production (never a test's `--dry-run`).
    production_args: tuple[str, ...] = ()
    expected_artifact_schema: str = UNMEASURED
    owner: str = UNMEASURED
    #: What the reconciler runs to repair it, as an actuator name (see `actuators.py`).
    restart_action: str = UNMEASURED
    timeout_s: int | None = None
    criticality: str = "optional"
    #: {"memory_mb": int|None, "cpu": str, "budget_s": int|None} -- what one pass may take.
    resource_budget: Mapping[str, Any] = field(default_factory=dict)
    #: The clock that fires it: a box task name, a VPS timer unit, or `hourly_cycle:<leg>`.
    schedule: str = UNMEASURED
    #: The artifact class for the freshness lease (see `lease.TTL_BY_CLASS`).
    artifact_class: str = UNMEASURED
    notes: str = ""

    def __post_init__(self) -> None:
        if self.criticality not in CRITICALITY:
            raise ValueError(f"{self.component_id}: criticality {self.criticality!r} "
                             f"not one of {CRITICALITY}")
        if self.kind not in KINDS:
            raise ValueError(f"{self.component_id}: kind {self.kind!r} not one of {KINDS}")
        if self.host not in HOSTS:
            raise ValueError(f"{self.component_id}: host {self.host!r} not one of {HOSTS}")
        if self.max_silence_s is None and self.cadence_s is not None:
            object.__setattr__(self, "max_silence_s",
                               derive_max_silence(self.cadence_s, self.timeout_s))

    @property
    def scheduled(self) -> bool:
        """Does anything in this repo declare when it runs? UNMEASURED is not a schedule."""
        return bool(self.schedule) and self.schedule != UNMEASURED

    @property
    def detection_sla_s(self) -> int | None:
        """How long the desk may take to NOTICE this component has stopped."""
        return self.max_silence_s

    @property
    def repair_sla_s(self) -> int | None:
        """How long the repair itself may take: the actuator's window plus one cadence for the
        restarted pass to prove itself by advancing its watermark."""
        if self.cadence_s is None:
            return None
        return int(self.cadence_s + (self.timeout_s or 0))

    @property
    def sla_s(self) -> int | None:
        """detection + repair, the published objective. None where the cadence is UNMEASURED."""
        d, r = self.detection_sla_s, self.repair_sla_s
        return None if d is None or r is None else int(d + r)

    def config_hash(self) -> str:
        """A stable hash of the DECLARATION. A spec edit changes it; a code edit does not."""
        payload = json.dumps(self.to_dict(with_identity=False), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def code_sha(self, root: Path | None = None) -> str:
        """sha256 over this component's declared code, in path order. UNMEASURED when it names
        no file that exists -- a spec pointing at a deleted script is a finding."""
        base = root or ROOT
        h = hashlib.sha256()
        seen = 0
        for rel in sorted(self.code_paths):
            p = base / rel
            try:
                h.update(p.read_bytes())
                seen += 1
            except OSError:
                continue
        return h.hexdigest()[:16] if seen else UNMEASURED

    def code_identity(self, root: Path | None = None) -> dict[str, str]:
        """{code_sha, config_hash} -- the pair a lease stamps so a verdict can tell a code change
        from a configuration one."""
        return {"code_sha": self.code_sha(root), "config_hash": self.config_hash()}

    def to_dict(self, with_identity: bool = True, root: Path | None = None) -> dict[str, Any]:
        d = asdict(self)
        d["resource_budget"] = dict(self.resource_budget)
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)
        if with_identity:
            d["code_identity"] = self.code_identity(root)
            d["detection_sla_s"] = self.detection_sla_s
            d["repair_sla_s"] = self.repair_sla_s
            d["sla_s"] = self.sla_s
        return d


class Registry:
    """Every component this desk declares, indexed by id and by the code it owns.

    NOT A LIST SOMEONE MAINTAINS. `desks/mt5/ops/components.py` DERIVES the rows from the places
    the desk already declares work -- the hourly cycle's legs, the daily cycle's steps, the box
    task manifest, the department/forest/moat residents, the federation roster -- so a new leg
    arrives in the registry the moment it arrives on a clock, and the registry cannot drift from
    the schedule by being forgotten.
    """

    def __init__(self, specs: Iterable[ComponentSpec] = ()) -> None:
        self._by_id: dict[str, ComponentSpec] = {}
        for s in specs:
            self.add(s)

    def add(self, spec: ComponentSpec, replace: bool = False) -> ComponentSpec:
        if spec.component_id in self._by_id and not replace:
            raise ValueError(f"duplicate component_id {spec.component_id!r}")
        self._by_id[spec.component_id] = spec
        return spec

    def add_all(self, specs: Iterable[ComponentSpec], replace: bool = False) -> None:
        for s in specs:
            self.add(s, replace=replace)

    def get(self, component_id: str) -> ComponentSpec | None:
        return self._by_id.get(component_id)

    def ids(self) -> list[str]:
        return sorted(self._by_id)

    def all(self) -> list[ComponentSpec]:
        return [self._by_id[k] for k in sorted(self._by_id)]

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self) -> Iterator[ComponentSpec]:
        return iter(self.all())

    def __contains__(self, component_id: object) -> bool:
        return component_id in self._by_id

    def by_kind(self, kind: str) -> list[ComponentSpec]:
        return [s for s in self.all() if s.kind == kind]

    def required(self) -> list[ComponentSpec]:
        return [s for s in self.all() if s.criticality == "required"]

    def owners_of(self, rel_path: str) -> list[ComponentSpec]:
        """Which components claim this repo-relative file. Zero means the birth fence fires."""
        rel = rel_path.replace("\\", "/")
        return [s for s in self.all() if rel in s.code_paths]

    def claimed_paths(self) -> set[str]:
        return {p for s in self.all() for p in s.code_paths}

    def problems(self, root: Path | None = None) -> list[str]:
        """Structural lies in the registry itself, in the order a reader should fix them."""
        base = root or ROOT
        out: list[str] = []
        for s in self.all():
            for rel in s.code_paths:
                if not (base / rel).exists():
                    out.append(f"{s.component_id}: code_path {rel} does not exist")
            if s.criticality == "required" and not s.scheduled:
                out.append(f"{s.component_id}: required but no schedule declared")
            if s.criticality == "required" and s.max_silence_s is None:
                out.append(f"{s.component_id}: required but max_silence is UNMEASURED "
                           f"(cadence undeclared)")
            if s.cadence_s is not None and s.max_silence_s is not None \
                    and s.max_silence_s < s.cadence_s:
                out.append(f"{s.component_id}: max_silence {s.max_silence_s}s is shorter than "
                           f"its cadence {s.cadence_s}s")
        return out

    def census(self, root: Path | None = None) -> dict[str, Any]:
        specs = self.all()
        scheduled = [s for s in specs if s.scheduled]
        return {
            "components": len(specs),
            "by_kind": {k: sum(1 for s in specs if s.kind == k) for k in KINDS},
            "by_criticality": {c: sum(1 for s in specs if s.criticality == c)
                               for c in CRITICALITY},
            "scheduled": len(scheduled),
            "unscheduled": len(specs) - len(scheduled),
            "with_progress_metric": sum(1 for s in specs if s.progress_metric != UNMEASURED),
            "problems": self.problems(root),
        }

    def to_json(self, root: Path | None = None) -> list[dict[str, Any]]:
        return [s.to_dict(root=root) for s in self.all()]


def spec(component_id: str, **kw: Any) -> ComponentSpec:
    """Sequence-tolerant constructor: lists become tuples so the spec stays hashable/frozen."""
    fixed: dict[str, Any] = {}
    for k, v in kw.items():
        if k != "resource_budget" and isinstance(v, (list, Sequence)) and not isinstance(v, str):
            fixed[k] = tuple(v)
        else:
            fixed[k] = v
    return ComponentSpec(component_id=component_id, **fixed)
