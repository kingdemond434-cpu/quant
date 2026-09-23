"""THE PRODUCER CENSUS: every producer this tree contains, its clock, its last production, its
verdict -- and, in the SAME pass, the repair for every one that is dark.

WHY IT EXISTS, measured on the trading box 2026-09-23. `check_seat_health` read 105 seats and
returned 92 of them UNMEASURED for one reason: "no organ declared in SEAT_ORGANS, so no clock can
be looked up". Ninety-two real donation directories -- `aaii`, `academic`, `arxiv_qfin`,
`central_banks`, sixty more producing inside the hour -- were invisible to the fence not because
they were dark but because a HAND TABLE had never been filled in. A blind spot the size of the
census is worse than a red fence: it reports health it never looked at.

FIVE DIFFERENT CAUSES OF DARKNESS, all measured the same morning, and they have five different
remedies. This module exists because a single "dark" verdict with a single remedy would have
fixed at most one of them:

  1. A CLOCK ON THE WRONG MACHINE. `kimi` had `quant-kimi-hunter.timer` on the VPS and the
     credential on the box: the clock could fire forever without producing. Remedy: a clock where
     the credential is.
  2. A SEAT RETIRED WITHOUT AN INHERITOR. Three MQL5 seats were retired with their replacement
     named and a fourth, `mql5_reputation`, was left to read DARK forever. Remedy: the retirement
     ledger row, with the inheritor named.
  3. AN ENVIRONMENT PROVISIONED ON THE WRONG BOX. The federation's shared venv was built on the
     8 GB build box; the trading box with the data and the compute planned 13 systems runnable
     against 52 unmeasured. Remedy: provision where the compute is.
  4. A MAPPING TABLE NEVER FILLED IN -- the 92 above. Remedy: DERIVE the mapping (this module's
     `derive_seat_organs`) so a seat that lands tomorrow is covered tomorrow, not when somebody
     remembers to type it.
  5. AN EXECUTABLE THAT LANDED WITHOUT A LEG. Remedy: a leg, or a retirement with a reason.

THE LAW THIS SERVES (LAWS 7, "A REPORT IS NOT A REMEDY"): an organ that can close a gap closes it
on its own clock. So `relight()` is not a suggestion list -- it RUNS the repair, and the
postcondition is the producer's own output being NEWER than it was, never a zero exit code.

DERIVED, NEVER HAND-LISTED. The population comes from `desks/mt5/ops/components.py` (the birth
fence's own registry, so a component that lands today is in tomorrow's census), from the two
intelligence roots, and from the sandbox roster. Nothing here enumerates organs by name.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

LIVE = "LIVE"
SLOW = "SLOW"
DARK = "DARK"
RETIRED = "RETIRED"
UNMEASURED = "UNMEASURED"
UNMEASURED_HERE = "UNMEASURED_HERE"

#: THE DARK RATCHET. Producers allowed to read DARK before the census is a fence failure.
#:
#: IT MAY ONLY FALL (L1.50, pointed the only way a debt can ratchet). It is not a tolerance for
#: darkness: it is the measured residue on the day the census landed, so the fence is red for a
#: NEW dark producer immediately instead of being red for a backlog nobody in the session
#: created and therefore forced off within a day.
DARK_RATCHET = 0

#: Directories under an intelligence root that are not seats.
_NOT_SEATS: frozenset[str] = frozenset({"__pycache__", ".git"})

#: Roots scanned for the derived seat -> writer mapping. Tests and retired code are excluded on
#: purpose: a retired miner's path literal must never be able to claim a live seat.
_SCAN_ROOTS: tuple[str, ...] = ("libs", "scripts", "ops", "desks/mt5")
_SCAN_SKIP = re.compile(r"(^|[\\/])(tests?|_retired|\.venv|node_modules|__pycache__)([\\/]|$)")

#: `data/intelligence/<seat>` written as a path, in every shape the desk actually writes it.
_INTEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"intelligence[\\/]+([A-Za-z0-9_]+)"),
    re.compile(r"""["']intelligence["']\s*,\s*["']([A-Za-z0-9_]+)["']"""),
    re.compile(r"""["']intelligence["']\s*/\s*["']([A-Za-z0-9_]+)["']"""),
)

_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", re.M)
_STEM_RE = re.compile(r"(?<![\w.])([A-Za-z_][\w]{3,})\.py\b")

#: How many hops of "who runs the file that writes this seat" the derivation will walk.
#:
#: THREE, because that is what the tree measures: `quant-seed-miners.timer` runs
#: `seed_miners.py`, which imports `run_all_miners`, which imports `aaii_sentiment_miner`, which
#: is what actually writes `data/intelligence/aaii`. A one-hop derivation reports sixty live
#: seats as unmapped, which is the blindness this module exists to remove.
MAX_HOPS = 3


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def host() -> str:
    """Which machine this checkout is on. The box runs Windows; the VPS does not."""
    return "box" if os.name == "nt" else "vps"


#: One measurement of "do this checkout's clocks live HERE" per process.
_RUNTIME_CACHE: dict[str, bool | None] = {}

_TASK_NAME = re.compile(r'^TASK\s+name="([^"]+)"', re.M)


def runs_clocks_here(root: Path | None = None, *,
                     probe: Callable[[str], bool] | None = None) -> bool | None:
    """Does THIS checkout hold the clocks, or is it a mirror of the machine that does?

    THE DISTINCTION THE OLD FENCE COULD NOT MAKE, and it is the whole difference between a
    verdict and a false alarm. `os.name` says "Windows", which is true of the trading box AND of
    every build box a session runs on; a build box's `data/intelligence` is a GIT MIRROR whose
    newest file is as old as the last pull, so judging it reports a hundred healthy seats DARK
    for work that is happening correctly on another machine.

    So it is MEASURED, not inferred: on Windows, whether the box's own scheduled tasks are
    registered here; on Linux, whether the desk's systemd user units are installed. An
    unreadable scheduler is None -- UNMEASURED, published with the reason, never a silent pass
    in either direction.
    """
    base = root or ROOT
    key = str(base.resolve())
    if key in _RUNTIME_CACHE:
        return _RUNTIME_CACHE[key]
    verdict: bool | None
    try:
        if os.name == "nt":
            names = _TASK_NAME.findall(_read(base / "desks" / "mt5" / "ops" / "box_tasks.manifest"))
            if not names:
                verdict = None
            elif probe is not None:
                verdict = any(probe(n) for n in names[:6])
            else:
                import subprocess
                verdict = False
                for name in names[:6]:
                    r = subprocess.run(["schtasks", "/Query", "/TN", name],
                                       capture_output=True, text=True, timeout=20, check=False)
                    if r.returncode == 0:
                        verdict = True
                        break
        else:
            units = Path.home() / ".config" / "systemd" / "user"
            verdict = units.is_dir() and any(units.glob("quant-*.timer"))
    except Exception:                                        # pragma: no cover - probe guard
        verdict = None
    _RUNTIME_CACHE[key] = verdict
    return verdict


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _newest_mtime(paths: Iterable[Path]) -> float:
    """The newest mtime under these paths, walking one level into directories. 0.0 when nothing
    exists -- a producer that has NEVER produced, which is a different fact from a stale one."""
    newest = 0.0
    for p in paths:
        try:
            if p.is_dir():
                for f in p.iterdir():
                    if f.is_file():
                        newest = max(newest, f.stat().st_mtime)
            elif p.is_file():
                newest = max(newest, p.stat().st_mtime)
        except OSError:
            continue
    return newest


# --------------------------------------------------------------------- the derived seat mapping
#: One source scan per process. The derivation reads ~2,000 files; the seat layer and the census
#: both need it, and scanning twice doubled a leg's wall clock for an identical answer.
_SCAN_CACHE: dict[str, dict[str, str]] = {}


def _scan_sources(root: Path) -> dict[str, str]:
    """repo-relative path -> text, for every source file a clock could plausibly reach."""
    key = str(root.resolve())
    hit = _SCAN_CACHE.get(key)
    if hit is not None:
        return hit
    out: dict[str, str] = {}
    for rel in _SCAN_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for pat in ("*.py", "*.sh", "*.cmd", "*.ps1"):
            for p in base.rglob(pat):
                r = p.relative_to(root).as_posix()
                if _SCAN_SKIP.search(r):
                    continue
                out[r] = _read(p)
    _SCAN_CACHE[key] = out
    return out


def _seat_writers(texts: Mapping[str, str], seats: Iterable[str]) -> dict[str, list[str]]:
    """seat -> the files that name `data/intelligence/<seat>` as a path they write."""
    wanted = set(seats)
    out: dict[str, list[str]] = {}
    for rel, text in texts.items():
        if "intelligence" not in text:
            continue
        found: set[str] = set()
        for rx in _INTEL_PATTERNS:
            found.update(m.group(1) for m in rx.finditer(text))
        for seat in found & wanted:
            out.setdefault(seat, []).append(rel)
    return out


def _runner_index(texts: Mapping[str, str]) -> dict[str, list[str]]:
    """module stem -> the files that import it or name its script path.

    This is the "who runs this" edge. A miner with no `main()` carries no ComponentSpec by
    design; what gives it a clock is the scheduled file that imports it, and that edge is
    readable from the source rather than declared anywhere.
    """
    out: dict[str, list[str]] = {}
    for rel, text in texts.items():
        stems: set[str] = set()
        for m in _IMPORT_RE.finditer(text):
            stems.add(m.group(1).split(".")[-1])
        for m in _STEM_RE.finditer(text):
            stems.add(m.group(1))
        for stem in stems:
            out.setdefault(stem, []).append(rel)
    return out


#: A file that writes `data/intelligence/<var>` rather than a literal seat name. This is how the
#: roster miners fill fifty seats from one table: `INTEL / source_id / f"discoveries_{ts}.json"`.
_GENERIC_INTEL = re.compile(r"""intelligence["']?\s*(?:/|,)\s*(?!["'])""")

#: The SAME shape written in two steps, which is the desk's actual idiom:
#: `INTEL = BASE / "data" / "intelligence"` on one line and `INTEL / source` two hundred lines
#: later. A one-line pattern misses every roster miner in the tree, which is how forty-nine live
#: seats read as having no writer at all.
_INTEL_BINDING = re.compile(r"""^\s*([A-Za-z_]\w*)\s*[:=][^=\n]*?["']intelligence["']""", re.M)


def _writes_intel_generically(text: str) -> bool:
    """Does this file build a per-source path under an intelligence root from a VARIABLE?"""
    if "intelligence" not in text:
        return False
    if _GENERIC_INTEL.search(text):
        return True
    for m in _INTEL_BINDING.finditer(text):
        name = m.group(1)
        if re.search(r"\b" + re.escape(name) + r"""\s*/\s*(?!["'])""", text):
            return True
    return False


#: DISQUALIFIERS -- a file that matches one of these is a CONSUMER or an ORCHESTRATOR, never the
#: organ that fills a seat, and naming it as the organ would point every repair at the wrong
#: process. Structural, not a name list: a file that defines `_producer(` IS one of the two
#: cycles (its legs are the organs), and a file that imports the fence exit IS a fence (it
#: measures production, it does not create it).
_ORCHESTRATOR = re.compile(r"^def _producer\(", re.M)
_FENCE = re.compile(r"fence_exit|check_[a-z_]+\.py\b")


def _organ_score(rel: str, text: str, *, tier: int, hops: int, cadence_h: float | None) -> int:
    """How strongly this file looks like the organ that FILLS a seat, not one that reads it.

    Weak signals, combined and published, because no single one is decisive in this tree. The
    ranking is self-correcting by design: if it picks the wrong file, `apply_relight` runs it,
    the seat does not produce, and the repair is recorded UNPROVEN with the organ named -- a
    visible wrong answer, which is the only kind worth having.
    """
    score = {0: 120, 1: 100, 2: 50}.get(tier, 20)
    score -= 10 * int(hops)
    if int(hops) == 0:
        #: THE CLOCK ON THE WRITER IS THE WRITER'S CLOCK. A clock that merely reaches it is an
        #: inference, and preferring the inference attributed fifty seeded seats to whichever
        #: hourly leg happened to mention the sweep that runs them.
        score += 30
    if _ORCHESTRATOR.search(text):
        score -= 80
    if rel.startswith("scripts/check_") or _FENCE.search(text[:4000]):
        score -= 80
    if "/side_channels/" in f"/{rel}":
        #: The desk's own miner layer. A seat filled from a roster table is filled from here;
        #: `research/` holds the organs that READ the seats (the router, the compilers), and
        #: pointing a repair at a reader restarts the wrong process.
        score += 40
    if cadence_h is not None and cadence_h <= 1.0:
        score += 10
    return score


def derive_seat_organs(root: Path | None = None, *,
                       clocked: Mapping[str, Any] | None = None,
                       texts: Mapping[str, str] | None = None,
                       seats: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
    """seat -> {"organ", "writer", "hops", "tier", "why"}, DERIVED from the source tree.

    TWO TIERS, because the desk fills seats two ways and a derivation that knew only the first
    reported forty-nine live seats as unmapped:

      TIER 0  a clocked organ is NAMED for the seat (`world_lab.py` fills `world_lab`).
      TIER 1  a file names `data/intelligence/<seat>` as a literal path (one miner, one seat).
      TIER 3  any clocked file names the seat as a quoted id (last resort, weakest).
      TIER 2  a file names the seat as a quoted id AND writes `data/intelligence/<variable>` --
              the roster shape: `seed_miners` and `regional_survivor_hunters` fill fifty seats
              each from one table, and no literal path for any of them exists anywhere.

    `clocked` is the clock index (script path -> clock row). The ORGAN returned is the nearest
    clocked file that reaches the writer, because that is the cadence the seat can be judged
    against; the WRITER is kept so a reader sees what actually fills the directory.
    """
    base = root or ROOT
    src = dict(texts) if texts is not None else _scan_sources(base)
    names = list(seats) if seats is not None else sorted(seat_dirs(base))
    writers = _seat_writers(src, names)
    runners = _runner_index(src)
    clocks = dict(clocked or {})
    generic = {rel for rel, text in src.items() if _writes_intel_generically(text)}
    by_stem: dict[str, list[str]] = {}
    for rel in clocks:
        by_stem.setdefault(Path(rel).stem, []).append(rel)
    out: dict[str, dict[str, Any]] = {}

    for seat in names:
        cands: list[tuple[str, int]] = [(f, 0) for f in sorted(by_stem.get(seat) or [])]
        cands += [(f, 1) for f in sorted(writers.get(seat) or [])]
        quoted = re.compile("[\"']" + re.escape(seat) + "[\"']")
        if not any(tier <= 1 for _, tier in cands):
            cands += [(f, 2) for f in sorted(generic) if quoted.search(src.get(f, ""))]
        if not cands:
            #: TIER 3, the last resort: any CLOCKED file that names the seat as a quoted id.
            #: Weakest evidence and scored as such -- but a mapping gap is a defect in the
            #: mapping (LAWS 7), so "nothing in the tree mentions it" is the only honest way to
            #: leave a seat unmapped, and a wrong pick here is falsified within the hour by its
            #: own relight failing to produce.
            cands = [(f, 3) for f in sorted(clocks) if quoted.search(src.get(f, ""))]
        if not cands:
            continue
        best: dict[str, Any] | None = None
        for writer, tier in cands:
            seen = {writer}
            frontier = [writer]
            for hop in range(MAX_HOPS + 1):
                clocked_here = sorted(f for f in frontier if f in clocks)
                if clocked_here:
                    pick = clocked_here[0]
                    cad = clocks[pick].get("cadence_h")
                    score = _organ_score(writer, src.get(writer, ""), tier=tier, hops=hop,
                                         cadence_h=None if cad is None else float(cad))
                    row: dict[str, Any] = {
                        "organ": pick, "writer": writer, "hops": hop, "tier": tier,
                        "score": score,
                        "why": (f"tier {tier}: "
                                + (f"{pick} is the clocked organ named for this seat" if tier == 0
                                   else f"{writer} writes data/intelligence/{seat}")
                                + ("" if hop == 0 else f"; {pick} reaches it in {hop} hop(s)"))}
                    if best is None or score > int(best.get("score") or -999):
                        best = row
                    break
                nxt: list[str] = []
                for f in frontier:
                    stem = Path(f).stem
                    for up in runners.get(stem, ()):
                        if up not in seen and up != f:
                            seen.add(up)
                            nxt.append(up)
                if not nxt:
                    break
                frontier = sorted(nxt)[:40]
        if best is not None:
            out[seat] = best
        else:
            first = cands[0][0]
            out[seat] = {"organ": None, "writer": first, "hops": None, "tier": cands[0][1],
                         "score": None,
                         "why": (f"{first} writes data/intelligence/{seat} and no clocked file "
                                 f"reaches it within {MAX_HOPS} hop(s)")}
    return out


def seat_dirs(root: Path | None = None) -> dict[str, Path]:
    """seat name -> its directory, across BOTH intelligence roots."""
    base = root or ROOT
    out: dict[str, Path] = {}
    for r in (base / "data" / "intelligence", base / "desks" / "mt5" / "data" / "intelligence"):
        if not r.is_dir():
            continue
        try:
            for c in sorted(r.iterdir()):
                if c.is_dir() and c.name not in _NOT_SEATS:
                    out.setdefault(c.name, c)
        except OSError:
            continue
    return out


def seat_production(root: Path | None = None) -> dict[str, float]:
    """seat -> epoch seconds of its NEWEST donation, across both roots. 0.0 = never produced."""
    base = root or ROOT
    out: dict[str, float] = {}
    for r in (base / "data" / "intelligence", base / "desks" / "mt5" / "data" / "intelligence"):
        if not r.is_dir():
            continue
        try:
            children = [c for c in r.iterdir() if c.is_dir() and c.name not in _NOT_SEATS]
        except OSError:
            continue
        for c in children:
            out[c.name] = max(out.get(c.name, 0.0), _newest_mtime([c]))
    return out


# -------------------------------------------------------------------------------- retirements
def retirements(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every retired producer, keyed by BOTH its seat name and its code path.

    A RETIREMENT IS AN ANSWER AND AN INHERITOR. A row with no `replacement` is not a retirement,
    it is an abandonment -- so it is returned with `inheritor: None` and the census says so
    rather than reading it as a settled disposition.
    """
    path = (root or ROOT) / "docs" / "research" / "retirements.jsonl"
    out: dict[str, dict[str, Any]] = {}
    for line in _read(path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        rec = {"reason": str(row.get("reason") or "")[:400],
               "inheritor": (str(row.get("replacement")) if row.get("replacement") else None),
               "at": row.get("at") or row.get("date")}
        for key in (row.get("seat"), row.get("path")):
            if key:
                out[str(key)] = rec
    return out


# ------------------------------------------------------------------------------- census rows
@dataclass
class Row:
    """One producer, measured."""

    producer: str
    kind: str
    clock: str | None
    clock_host: str
    cadence_s: int | None
    expectation_s: int | None
    produced_at: float | None
    age_s: float | None
    verdict: str
    why: str
    production_paths: tuple[str, ...] = ()
    organ: str | None = None
    owner: str = UNMEASURED
    criticality: str = "optional"
    repair: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"producer": self.producer, "kind": self.kind, "clock": self.clock,
                "clock_host": self.clock_host, "cadence_s": self.cadence_s,
                "expectation_s": self.expectation_s,
                "age_h": None if self.age_s is None else round(self.age_s / 3600.0, 2),
                "verdict": self.verdict, "why": self.why, "organ": self.organ,
                "owner": self.owner, "criticality": self.criticality, "repair": self.repair,
                "production_paths": list(self.production_paths), **self.details}


def _clock_host(schedule: str) -> str:
    """Which machine a schedule name belongs to. Derived from the desk's own naming, which is
    total: box tasks are `MT5-*`/`E8-*`, VPS units are `quant-*`/`*.timer`/`*.service`, and the
    two cycles run wherever the cycle runs."""
    s = str(schedule or "")
    if s.startswith(("MT5-", "E8-", "QQuant-")):
        return "box"
    if s.startswith("quant-") or s.endswith((".timer", ".service")):
        return "vps"
    if s.startswith(("hourly_cycle:", "daily_cycle:")):
        return "either"
    return "either"


def _judge(age_s: float | None, cadence_s: int | None, expectation_s: int | None,
           *, label: str) -> tuple[str, str]:
    """LIVE / SLOW / DARK from one measured age against one declared expectation."""
    if expectation_s is None:
        return UNMEASURED, (f"{label} declares no silence budget this census can reduce to "
                            f"seconds; a bar nobody computed is not a bar to judge against")
    if age_s is None:
        return DARK, f"{label} has NEVER produced: no output file exists anywhere in this tree"
    if cadence_s and age_s <= float(cadence_s):
        return LIVE, (f"produced {age_s / 3600.0:.1f}h ago, inside its "
                      f"{cadence_s / 3600.0:.1f}h cadence")
    if age_s <= float(expectation_s):
        return SLOW, (f"produced {age_s / 3600.0:.1f}h ago -- past its cadence, inside the "
                      f"{expectation_s / 3600.0:.1f}h silence budget")
    return DARK, (f"produced {age_s / 3600.0:.1f}h ago, past the {expectation_s / 3600.0:.1f}h "
                  f"silence budget {label} declares")


def _seat_expectation(cadence_s: int | None) -> int | None:
    """A seat's silence budget: three of its own cadences, never under six hours.

    NOT ONE CADENCE. A free-tier route is rate-limited by design, a crawl can meet a 503 and a
    box can reboot; a fence that called one missed hour a defect would be forced off within a
    week, which is how a fence stops being read.
    """
    if cadence_s is None:
        return None
    return max(6 * 3600, int(cadence_s) * 3)


def mirror_reason(owner_host: str, here: str, runs_here: bool | None,
                  clock: str | None) -> str | None:
    """Why this host may not judge this producer, or None when it may.

    TWO WAYS A CHECKOUT IS A MIRROR: it is the other machine (a box clock read on the VPS), or
    it is a machine that holds none of the clocks at all (a build box, CI, a fresh clone). Both
    are UNMEASURED_HERE with the reason attached -- never a pass, and never a defect charged to
    an organ that is running correctly somewhere else.
    """
    if runs_here is False:
        return (f"this checkout holds NONE of the desk's clocks (measured: no scheduled task or "
                f"user unit is registered on this host), so its data/intelligence and reports "
                f"are a git mirror of the machine that runs {clock or 'them'}. An old file here "
                f"is not a stale producer")
    if runs_here is None:
        return ("this host's scheduler is unreadable, so whether the clocks live here is "
                "UNMEASURED -- and a producer cannot be judged against a clock nobody could "
                "confirm runs here")
    if owner_host in ("box", "vps") and owner_host != here:
        return (f"clock {clock} runs on the {owner_host}; this checkout on the {here} holds a "
                f"mirror of what that host wrote, so an old file here is not a stale producer")
    return None


def seat_rows(*, root: Path | None = None, clocks: Mapping[str, Any],
              declared: Mapping[str, str] | None = None,
              derived: Mapping[str, Mapping[str, Any]] | None = None,
              retired: Mapping[str, Mapping[str, Any]] | None = None,
              now: float | None = None, strict: bool = False,
              runs_here: bool | None = None) -> list[Row]:
    """One row per seat directory under either intelligence root."""
    base = root or ROOT
    t = now if now is not None else time.time()
    runs_here = runs_clocks_here(base) if runs_here is None else runs_here
    dirs = seat_dirs(base)
    prod = seat_production(base)
    dec = dict(declared or {})
    der = {k: dict(v) for k, v in (derived or {}).items()}
    ret = dict(retired or {})
    here = host()
    rows: list[Row] = []

    for seat in sorted(set(dirs) | set(dec)):
        rec = ret.get(seat)
        produced = prod.get(seat) or 0.0
        age = (t - produced) if produced > 0 else None
        paths = (dirs[seat].relative_to(base).as_posix(),) if seat in dirs else ()
        if rec is not None:
            rows.append(Row(seat, "seat", None, "n/a", None, None,
                            produced or None, age, RETIRED,
                            (f"retired: {rec.get('reason', '')[:180]}"
                             + (f" -- inherited by {rec.get('inheritor')}" if rec.get("inheritor")
                                else " -- NO INHERITOR NAMED, which is an abandonment, not a "
                                     "retirement")),
                            paths, organ=None,
                            details={"inheritor": rec.get("inheritor")}))
            continue

        organ = dec.get(seat) or (der.get(seat) or {}).get("organ")
        writer = (der.get(seat) or {}).get("writer")
        if not organ:
            rows.append(Row(seat, "seat", None, "n/a", None, None, produced or None, age,
                            DARK,
                            ("no organ anywhere in this tree writes data/intelligence/"
                             f"{seat}, and no retirement row names an inheritor. A mapping gap "
                             "is a defect in the mapping, never a reason to call the seat "
                             "unmeasured"),
                            paths, organ=None, repair="retire_or_clock",
                            details={"writer": writer, "mapping_gap": True}))
            continue

        clk = clocks.get(organ)
        if clk is None:
            rows.append(Row(seat, "seat", None, "n/a", None, None, produced or None, age,
                            DARK,
                            (f"{organ} writes this seat and NOTHING schedules it: no systemd "
                             "unit, box task or cycle leg. Not a slow seat -- an unscheduled "
                             "one, and the remedy is a clock"),
                            paths, organ=organ, repair="clock",
                            details={"writer": writer, "unclocked": True}))
            continue

        cadence_h = clk.get("cadence_h")
        cadence_s = None if cadence_h is None else int(float(cadence_h) * 3600)
        exp = _seat_expectation(cadence_s)
        owner_host = str(clk.get("host") or "either")
        skip = mirror_reason(owner_host, here, runs_here, str(clk.get("clock")))
        if not strict and skip:
            rows.append(Row(seat, "seat", str(clk.get("clock")), owner_host, cadence_s, exp,
                            produced or None, age, UNMEASURED_HERE, skip,
                            paths, organ=organ, details={"writer": writer}))
            continue
        verdict, why = _judge(age, cadence_s, exp, label=f"{seat} (clock {clk.get('clock')})")
        rows.append(Row(seat, "seat", str(clk.get("clock")), owner_host, cadence_s, exp,
                        produced or None, age, verdict, why, paths, organ=organ,
                        repair="run_organ" if verdict == DARK else None,
                        details={"writer": writer}))
    return rows


def component_rows(*, root: Path | None = None, registry: Any = None,
                   retired: Mapping[str, Mapping[str, Any]] | None = None,
                   now: float | None = None, strict: bool = False,
                   runs_here: bool | None = None) -> list[Row]:
    """One row per ComponentSpec in the desk's own birth registry.

    DERIVED FROM THE REGISTRY ON PURPOSE (the principal's addendum 2026-09-23): a component that
    lands today is in tomorrow's census without anybody adding it here.
    """
    base = root or ROOT
    t = now if now is not None else time.time()
    runs_here = runs_clocks_here(base) if runs_here is None else runs_here
    reg = registry if registry is not None else _desk_registry(base)
    if reg is None:
        return []
    ret = dict(retired or {})
    here = host()
    rows: list[Row] = []
    for spec in reg.all():
        cid = str(spec.component_id)
        codes = tuple(str(c) for c in spec.code_paths)
        rec = next((ret[c] for c in codes if c in ret), None)
        if rec is not None:
            rows.append(Row(cid, str(spec.kind), None, "n/a", None, None, None, None, RETIRED,
                            f"retired: {rec.get('reason', '')[:180]}"
                            + (f" -- inherited by {rec.get('inheritor')}"
                               if rec.get("inheritor") else " -- NO INHERITOR NAMED"),
                            codes, owner=str(spec.owner),
                            details={"inheritor": rec.get("inheritor")}))
            continue
        if not spec.scheduled:
            rows.append(Row(cid, str(spec.kind), None, "n/a", None, None, None, None, DARK,
                            (f"{cid} exists and NOTHING in this repository schedules it: an "
                             "executable that landed without a leg. The remedy is a leg or a "
                             "retirement row with a reason"),
                            codes, owner=str(spec.owner),
                            criticality=str(spec.criticality), repair="clock_or_retire",
                            details={"unclocked": True}))
            continue
        outs = tuple(str(o) for o in spec.outputs if o and not str(o).endswith("/"))
        sched = str(spec.schedule)
        owner_host = spec.host if spec.host in ("box", "vps") else _clock_host(sched)
        if not outs:
            rows.append(Row(cid, str(spec.kind), sched, owner_host, spec.cadence_s,
                            spec.max_silence_s, None, None, UNMEASURED,
                            (f"{cid} is scheduled by {sched} and declares no artifact, so "
                             "nothing here can measure whether it produced"),
                            codes, owner=str(spec.owner),
                            criticality=str(spec.criticality)))
            continue
        produced = _newest_mtime(base / o for o in outs)
        age = (t - produced) if produced > 0 else None
        skip = mirror_reason(owner_host, here, runs_here, sched)
        if not strict and skip:
            rows.append(Row(cid, str(spec.kind), sched, owner_host, spec.cadence_s,
                            spec.max_silence_s, produced or None, age, UNMEASURED_HERE, skip,
                            codes, owner=str(spec.owner),
                            criticality=str(spec.criticality)))
            continue
        verdict, why = _judge(age, spec.cadence_s, spec.max_silence_s,
                              label=f"{cid} (clock {sched})")
        rows.append(Row(cid, str(spec.kind), sched, owner_host, spec.cadence_s,
                        spec.max_silence_s, produced or None, age, verdict, why, outs,
                        owner=str(spec.owner), criticality=str(spec.criticality),
                        repair=(str(spec.restart_action) if verdict == DARK else None),
                        details={"outputs": list(outs)}))
    return rows


def sandbox_rows(*, root: Path | None = None, now: float | None = None) -> list[Row]:
    """One row per federated sandbox system, from the liveness fence's own reading.

    A system that is not importable on THIS host is not dark in the seat sense -- it is
    unprovisioned, and its repair is the provisioner, on the machine that holds the compute.
    """
    base = root or ROOT
    t = now if now is not None else time.time()
    report = base / "desks" / "mt5" / "reports" / "SANDBOX_LIVENESS.json"
    try:
        doc = json.loads(report.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return [Row("sandbox:federation", "sandbox", "hourly_cycle:sandbox_runner", "either",
                    3600, 3 * 3600, None, None, UNMEASURED,
                    "no SANDBOX_LIVENESS.json in this tree: the federation's liveness is "
                    "unmeasured here, which is a finding, never a pass",
                    ("desks/mt5/reports/SANDBOX_LIVENESS.json",), repair="run_sandbox_liveness")]
    rows: list[Row] = []
    produced = _newest_mtime([report])
    age = (t - produced) if produced > 0 else None
    reasons = doc.get("reasons") if isinstance(doc.get("reasons"), dict) else {}
    for sid, rec in sorted((reasons or {}).items()):
        why = str((rec or {}).get("why") or "")[:220] if isinstance(rec, dict) else str(rec)
        rows.append(Row(f"sandbox:{sid}", "sandbox", "hourly_cycle:sandbox_provision", "either",
                        3600, 3 * 3600, produced or None, age, UNMEASURED,
                        f"planned UNMEASURED by the runner: {why}",
                        ("desks/mt5/reports/SANDBOX_LIVENESS.json",),
                        repair="provision_sandbox",
                        details={"system": sid}))
    skip = mirror_reason("either", host(), runs_clocks_here(base), "hourly_cycle:sandbox_runner")
    fed = ((UNMEASURED_HERE, skip) if skip
           else _judge(age, 3600, 3 * 3600, label="sandbox federation"))
    rows.append(Row("sandbox:federation", "sandbox", "hourly_cycle:sandbox_runner", "either",
                    3600, 3 * 3600, produced or None, age, *fed,
                    ("desks/mt5/reports/SANDBOX_LIVENESS.json",),
                    repair="run_sandbox_liveness",
                    details={"n_runnable": doc.get("n_runnable"),
                             "n_unmeasured": doc.get("n_unmeasured"),
                             "n_scanned": doc.get("n_scanned")}))
    return rows


def _desk_registry(root: Path) -> Any:
    """The desk's ComponentSpec registry, or None where it cannot be imported.

    GUARDED, never fatal: this module has to answer on a build box, in CI and in a fresh clone,
    and an absent registry is UNMEASURED with the reason attached rather than a crash.
    """
    try:
        import importlib.util
        path = root / "desks" / "mt5" / "ops" / "components.py"
        spec = importlib.util.spec_from_file_location("_pc_components", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.registry(root)
    except Exception:                                        # pragma: no cover - import guard
        return None


# ------------------------------------------------------------------------------ the census
def census(*, root: Path | None = None, clocks: Mapping[str, Any] | None = None,
           declared_seats: Mapping[str, str] | None = None, now: float | None = None,
           strict: bool = False, registry: Any = None) -> dict[str, Any]:
    """Every producer the tree contains, with its clock, its last production and its verdict."""
    base = root or ROOT
    t = now if now is not None else time.time()
    clk = dict(clocks or {})
    ret = retirements(base)
    derived = derive_seat_organs(base, clocked=clk)
    rows = (seat_rows(root=base, clocks=clk, declared=declared_seats, derived=derived,
                      retired=ret, now=t, strict=strict)
            + component_rows(root=base, registry=registry, retired=ret, now=t, strict=strict)
            + sandbox_rows(root=base, now=t))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    dark = [r for r in rows if r.verdict == DARK]
    #: A producer with a clock that stopped producing, and a producer that never had a clock,
    #: are both DARK and are two different defects with two different owners. The second is the
    #: birth fence's own ratchet (`check_component_registry`, MAX_UNCLOCKED) -- counting it here
    #: too would give one number two ratchets that could disagree, which is how a fence starts
    #: being argued with instead of read.
    unclocked = [r for r in dark if r.details.get("unclocked")]
    silent = [r for r in dark if not r.details.get("unclocked")]
    return {
        "generated_utc": now_iso(),
        "law": ("EVERY SEAT, MINER AND RESEARCH ORGAN HAS A DECLARED CLOCK AND A PRODUCTION "
                "EXPECTATION. Producing nothing for longer than that expectation is a DEFECT "
                "with an owner, never a silent state; a producer with no organ mapping is a "
                "defect in the MAPPING, never a licence to read UNMEASURED."),
        "host": host(), "strict": bool(strict),
        "runs_clocks_here": runs_clocks_here(base),
        "n_producers": len(rows), "census": counts,
        "dark": [r.producer for r in dark],
        "dark_silent": [r.producer for r in silent],
        "dark_unclocked": [r.producer for r in unclocked],
        "dark_ratchet": DARK_RATCHET,
        "mapping_gaps": [r.producer for r in rows
                         if r.verdict == DARK and r.details.get("mapping_gap")],
        "derived_seat_organs": dict(sorted(derived.items())),
        "rows": [r.to_dict() for r in rows],
    }


# ----------------------------------------------------------------------------- the relighting
@dataclass(frozen=True)
class Relight:
    """One repair for one dark producer, and how its success will be judged."""

    producer: str
    action: str
    argv: tuple[str, ...]
    production_paths: tuple[str, ...]
    timeout_s: int
    why: str


def _python() -> str:
    import sys
    return sys.executable or "python"


def _organ_argv(root: Path, organ: str, budget_s: int) -> tuple[str, ...]:
    """How to run one organ for a single pass, honouring the desk's own `--once/--budget-s`."""
    path = root / organ
    text = _read(path)
    args: list[str] = []
    if "--once" in text:
        args.append("--once")
    if "--budget-s" in text:
        args += ["--budget-s", str(int(budget_s))]
    if organ.endswith(".sh"):
        return ("bash", str(path), *args)
    return (_python(), "-W", "ignore", str(path), *args)


def plan_relight(doc: Mapping[str, Any], *, root: Path | None = None,
                 budget_s: int = 300, max_repairs: int = 6) -> list[Relight]:
    """The repair for every dark producer, in the order darkness costs most.

    NOT A SUGGESTION LIST. `apply_relight` runs these, and the postcondition is the producer's
    own output being newer than it was (LAWS 7: a report is not a remedy).
    """
    base = root or ROOT
    out: list[Relight] = []
    rows = [r for r in doc.get("rows", []) if r.get("verdict") == DARK]
    rows.sort(key=lambda r: (str(r.get("criticality")) != "required",
                             -(float(r.get("age_h") or 0.0))))
    for r in rows:
        producer = str(r.get("producer"))
        paths = tuple(str(p) for p in (r.get("production_paths") or ()))
        repair = str(r.get("repair") or "")
        organ = r.get("organ")
        if repair == "run_organ" and organ:
            out.append(Relight(producer, "run_organ", _organ_argv(base, str(organ), budget_s),
                               paths, budget_s + 60,
                               f"run {organ}, the organ that writes this seat, for one pass"))
        elif repair == "provision_sandbox":
            sid = str(r.get("system") or "").strip()
            if not sid:
                continue
            out.append(Relight(
                producer, "provision_sandbox",
                (_python(), "-W", "ignore",
                 str(base / "desks" / "mt5" / "research" / "sandbox_provision.py"),
                 "--once", "--budget-s", str(int(budget_s)), "--only", sid),
                ("desks/mt5/data/sandbox_install_ledger.json",), budget_s + 60,
                f"provision {sid} into the shared venv ON THIS HOST, where the compute is"))
        elif repair.startswith("restart:task:"):
            task = repair.split("restart:task:", 1)[1]
            out.append(Relight(producer, "restart_task", ("schtasks", "/Run", "/TN", task),
                               paths, 120, f"restart the resident through its keep-alive {task}"))
        elif repair in ("clock", "clock_or_retire", "retire_or_clock"):
            #: NOT RUNNABLE FROM HERE, and saying so is the honest answer: giving an organ a leg
            #: or a retirement row is a CODE change, and an hourly leg that edited the cycle to
            #: heal itself would be a loop nobody could review.
            continue
        elif repair == "run_sandbox_liveness":
            out.append(Relight(
                producer, "run_sandbox_liveness",
                (_python(), "-W", "ignore",
                 str(base / "scripts" / "check_sandbox_liveness.py"), "--report-only"),
                paths, 300, "re-measure the federation's liveness on this host"))
        elif organ or paths:
            code = str((r.get("production_paths") or ("",))[0])
            if code.endswith(".py"):
                out.append(Relight(producer, "run_component",
                                   _organ_argv(base, str(organ or code), budget_s), paths,
                                   budget_s + 60, f"run {organ or code} for one pass"))
        if len(out) >= max_repairs:
            break
    return out


def _relight_without_plane(plans: Sequence[Relight], *, base: Path,
                           tick: Callable[[], float], t0: float, budget_s: float,
                           runner: Any) -> list[dict[str, Any]]:
    """The same repair and the same proof, on a host whose control plane predates the actuator."""
    import subprocess

    def run(argv: Sequence[str], timeout_s: int, cwd: str | None) -> dict[str, Any]:
        try:
            r = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout_s,
                               cwd=cwd, check=False)
            return {"rc": r.returncode, "tail": (r.stdout or r.stderr or "").strip()[-200:]}
        except (OSError, subprocess.SubprocessError) as exc:
            return {"rc": None, "tail": f"{type(exc).__name__}: {exc}"}

    use = runner or run
    out: list[dict[str, Any]] = []
    for plan in plans:
        if tick() - t0 >= budget_s:
            out.append({"producer": plan.producer, "action": plan.action, "result": "SKIPPED",
                        "relit": False, "why": "relight budget exhausted"})
            continue
        paths = [base / x for x in plan.production_paths]
        before = _newest_mtime(paths)
        rec = use(tuple(plan.argv), plan.timeout_s, str(base))
        after = _newest_mtime(paths)
        if not paths:
            result, why = "UNPROVEN", ("the producer declares no production path, so nothing "
                                       "here can prove it resumed")
        elif after > before:
            result, why = "RELIT", f"production resumed (fallback proof): {before} -> {after}"
        elif rec.get("rc") == 0:
            result, why = "UNPROVEN", ("the repair exited 0 and the producer's output did not "
                                       "move: a clean exit is not production (LAWS 7)")
        else:
            result, why = "FAILED", (f"the repair itself did not run: rc={rec.get('rc')} "
                                     f"{str(rec.get('tail') or '')[:160]}")
        out.append({"producer": plan.producer, "action": plan.action, "result": result,
                    "relit": result == "RELIT", "why": why, "rc": rec.get("rc"),
                    "tail": str(rec.get("tail") or "")[:200], "intent": plan.why,
                    "argv_head": plan.argv[0], "plane": "fallback"})
    return out


def apply_relight(plans: Sequence[Relight], *, root: Path | None = None,
                  runner: Callable[[Sequence[str], int, str | None], dict[str, Any]] | None = None,
                  now: Callable[[], float] | None = None,
                  budget_s: float = 900.0) -> list[dict[str, Any]]:
    """Run each repair THROUGH THE CONTROL PLANE and judge it by production, not by exit code.

    Every repair becomes a real `actuators.Actuator` with the `PRODUCTION_RESUMED`
    postcondition, so a dark producer's repair is proved by the same machinery, with the same
    discipline, as a resident restart: the producer's own newest output must be strictly newer
    than it was. A run that exits zero and writes nothing is UNPROVEN -- the desk has shipped
    healers whose only evidence was rc=0 for organs that never resumed.

    `runner` and `now` exist for the tests; production passes neither.
    """
    base = root or ROOT
    tick = now or time.monotonic
    t0 = tick()
    out: list[dict[str, Any]] = []
    try:
        from libs.ops.control_plane import actuators as act
        has_plane = hasattr(act, "producer_actuator") and hasattr(act, "newest_production")
    except Exception as exc:                                 # pragma: no cover - import guard
        return [{"producer": p.producer, "action": p.action, "result": "UNMEASURED",
                 "relit": False,
                 "why": f"the control plane is not importable here: {type(exc).__name__}: {exc}"}
                for p in plans]
    if not has_plane:
        #: AN OLDER CONTROL PLANE IS NOT A REASON NOT TO RELIGHT. A box that has not yet adopted
        #: `producer_actuator` still has dark producers, and the proof this pass needs -- the
        #: producer's own output moving -- does not depend on the plane. The repair runs, the
        #: SAME postcondition is applied here, and the record names the fallback so nobody reads
        #: it as the plane having proved it.
        return _relight_without_plane(plans, base=base, tick=tick, t0=t0, budget_s=budget_s,
                                      runner=runner)

    for plan in plans:
        if tick() - t0 >= budget_s:
            out.append({"producer": plan.producer, "action": plan.action, "result": "SKIPPED",
                        "relit": False, "why": "relight budget exhausted"})
            continue
        paths = [str(base / x) for x in plan.production_paths]
        before = act.newest_production([Path(x) for x in paths])
        actuator = act.producer_actuator(
            plan.producer, plan.argv, paths,
            name=f"relight:{plan.action}:{plan.producer}",
            timeout_s=plan.timeout_s, cwd=str(base))
        rec = act.run_actuator(actuator,
                               {"production_paths": paths,
                                "production_before": before if before > 0 else None},
                               apply=True, runner=runner, sleeper=lambda _s: None)
        out.append({"producer": plan.producer, "action": plan.action,
                    "result": ("RELIT" if rec.get("repaired") else str(rec.get("result"))),
                    "relit": bool(rec.get("repaired")),
                    "why": str(rec.get("why") or "")[:300] or str(
                        (rec.get("proofs") or [{}])[0].get("why") or "")[:300],
                    "rc": rec.get("rc"), "tail": str(rec.get("tail") or "")[:200],
                    "seconds": rec.get("seconds"), "intent": plan.why,
                    "argv_head": plan.argv[0]})
    return out


def breach(doc: Mapping[str, Any], *, ratchet: int | None = None) -> list[str]:
    """Why this census is a fence failure. Empty means the tree has no dark producer."""
    limit = DARK_RATCHET if ratchet is None else int(ratchet)
    dark = list(doc.get("dark_silent") or doc.get("dark") or [])
    gaps = list(doc.get("mapping_gaps") or [])
    out: list[str] = []
    if len(dark) > limit:
        out.append(f"{len(dark)} DARK producer(s) against a ratchet of {limit}: {dark[:8]}")
    if gaps:
        out.append(f"{len(gaps)} producer(s) have no organ mapping at all: {gaps[:8]}. A mapping "
                   f"gap is a defect in the mapping, never a reason to report UNMEASURED")
    return out
