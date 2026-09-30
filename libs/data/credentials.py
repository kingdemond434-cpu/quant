"""EVERY ENVIRONMENT CREDENTIAL THE DESK CAN USE: which provider, which fetcher reads it, under
which NAME, which legs and families it feeds, and whether it is set on this host.

WHY A REGISTRY OF NAMES (2026-09-30). The principal is registering free API keys on the Windows
trading box with `setx`. A key set under a name no reader looks for is a key that unlocks nothing,
silently, and six lanes built readers for these keys on six branches with no shared list of names.
Measured the day this was written: the EDGAR User-Agent is read as `QUANT_EDGAR_UA` on live and in
two lanes, as `SEC_EDGAR_UA` in the disclosure lane, and the principal's instruction names
`SEC_EDGAR_USER_AGENT`; the LLM seat's `deepseek_cycle` reads only `OPENROUTER_API_KEY` while
`llm_seat` accepts four names. This module is the one place those names are written down, and
`desks/mt5/research/credential_coverage.py` turns it into an hourly artifact.

THE STATUS OF A VARIABLE, per host, from presence ONLY:

    SET              present under a name every registered consumer reads
    MISMATCHED_NAME  present, but under a name at least one registered consumer does NOT read --
                     that consumer is still dark and the fix is a rename, not a signup
    BLOCKED_AUTH     absent under every accepted name and every secrets-file key name

NO VALUE IS EVER READ HERE. `os.environ` is consulted with `in` and for a non-empty test; a
secrets file is parsed and only its KEY NAMES are kept (the parsed values are dropped inside the
reader and never returned, logged or written). Nothing in this module returns a string derived
from a credential's value -- not a prefix, not a length, not a hash. A fetcher that needs the
value reads it itself, through `accepted_names()`, and puts it only in its own request.

THE ESTIMATE IS AN ESTIMATE. `Estimate.cells_per_day` is arithmetic on declared quantities (series
x mapped symbols x cells per pair, bounded by the consumer's per-pass donation cap x 24 passes),
labelled as such everywhere it is shown. The measured number is the consumer's own donation files,
which the coverage leg reads; the estimate only ranks keys nobody has set yet.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The two secrets directories the desk uses. Neither is ever committed (`data/secrets/**` never
#: leaves the box); a file here is read for its key NAMES only.
SECRETS_DIRS: tuple[Path, ...] = (ROOT / "data" / "secrets", DESK / "data" / "secrets")

SET = "SET"
MISMATCHED_NAME = "MISMATCHED_NAME"
BLOCKED_AUTH = "BLOCKED_AUTH"
UNMEASURED = "UNMEASURED"
STATUSES = (SET, MISMATCHED_NAME, BLOCKED_AUTH)

#: Status words other lanes use for "the key is absent", all of which ARE BLOCKED_AUTH. The
#: coverage report maps them so one vocabulary reaches the principal.
BLOCKED_SYNONYMS: frozenset[str] = frozenset({
    "BLOCKED_NO_KEY", "NEEDS_CREDENTIAL", "BLOCKED_ON_KEY", "DARK", "NO_KEY", "BLOCKED_AUTH"})

LIVE = "live"


@dataclass(frozen=True)
class Consumer:
    """One reader of a credential.

    `reads` lists every NAME this reader accepts -- environment names bare, secrets-file keys as
    `file:<relative path>#<key>`. A consumer whose `reads` lacks the name the principal set is the
    MISMATCHED_NAME case. `branch` is where the reader lives (`live`, or the unmerged branch and
    PR); `seats` are the `data/intelligence/<seat>/` directories its cells are donated under, the
    consumer's own artifact the coverage leg counts 24h cells from.
    """

    path: str
    reads: tuple[str, ...]
    branch: str = LIVE
    leg: str | None = None
    seats: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Estimate:
    """Declared quantities behind a cells/day ESTIMATE. None where the consumer declares none."""

    series: int = 0
    symbols: int = 0
    cells_per_pair: int = 0
    per_pass_cap: int | None = None
    basis: str = ""

    @property
    def grid(self) -> int:
        return int(self.series) * int(self.symbols) * int(self.cells_per_pair)

    @property
    def cells_per_day(self) -> int | None:
        if self.grid <= 0:
            return None
        return min(self.grid, self.per_pass_cap * 24) if self.per_pass_cap else self.grid


@dataclass(frozen=True)
class CredentialVar:
    env: str                              #: the canonical name (the principal's `setx` name)
    provider: str
    signup_url: str
    free_tier: str
    unlocks: str                          #: datasets
    instruments: tuple[str, ...]          #: MT5 instruments the cells land on
    families: tuple[str, ...]
    consumers: tuple[Consumer, ...]
    aliases: tuple[str, ...] = ()         #: other env names some reader accepts
    secrets: tuple[str, ...] = ()         #: `file:<path>#<key>` names a reader accepts
    kind: str = "key"                     #: key | id | secret | login | user_agent | token
    group: str = ""                       #: vars that only work together (id + secret)
    principal_list: bool = False          #: on the principal's 2026-09-30 setx list
    built: str = "BUILT"                  #: BUILT | NOT_BUILT: <why>
    estimate: Estimate = field(default_factory=Estimate)

    @property
    def accepted(self) -> tuple[str, ...]:
        return (self.env, *self.aliases)


# ------------------------------------------------------------------------------ the data ---
#: THE REGISTRY IS DATA, in `desks/mt5/data/credential_registry.json`. It names fetcher files by
#: path, and a path literal in a .py file reads to the component registry as "this file runs that
#: script" -- a registry that merely NAMES its consumers would have put every one of them on a
#: false clock. The JSON is not walked, so the clocks stay the truth.
REGISTRY_FILE = DESK / "data" / "credential_registry.json"
#: The keyed_sources leg: its consumer rows are recognised by LEG, never by a path literal here.
KS_LEG = "keyed_sources"
#: Cells per (series, symbol) the keyed_sources leg mints: 8 direct exogenous_conditioner cells
#: (2 transforms x 2 thresholds x 2 sides) + 6 indirect (3 certified parents x gt/lt).
KS_CELLS_PER_PAIR = 14
KS_PER_PASS = 1200


def _load(path: Path = REGISTRY_FILE
          ) -> tuple[tuple[CredentialVar, ...], tuple[dict[str, Any], ...]]:
    doc = json.loads(path.read_text("utf-8"))
    out: list[CredentialVar] = []
    for d in doc.get("vars") or []:
        cons = tuple(Consumer(**{**c, "reads": tuple(c.get("reads") or ()),
                                 "seats": tuple(c.get("seats") or ())})
                     for c in d.get("consumers") or [])
        est = Estimate(**(d.get("estimate") or {}))
        out.append(CredentialVar(**{
            **{k: v for k, v in d.items() if k not in ("consumers", "estimate")},
            "instruments": tuple(d.get("instruments") or ()),
            "families": tuple(d.get("families") or ()),
            "aliases": tuple(d.get("aliases") or ()), "secrets": tuple(d.get("secrets") or ()),
            "consumers": cons, "estimate": est}))
    keyless = tuple(dict(k, wired_in=tuple(k.get("wired_in") or ()))
                    for k in doc.get("keyless") or [])
    return tuple(out), keyless


REGISTRY, KEYLESS = _load()
BY_ENV: dict[str, CredentialVar] = {v.env: v for v in REGISTRY}


# --------------------------------------------------------------------------- presence -------
def _secret_key_names(path: Path) -> frozenset[str]:
    """The top-level KEY NAMES of a secrets JSON file. Values are dropped inside this function."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(doc, dict):
        return frozenset()
    names = {str(k) for k, v in doc.items() if v not in (None, "", {}, [])}
    del doc
    return frozenset(names)


def secret_present(spec: str, root: Path = ROOT) -> bool:
    """`file:<relative path>[#<key>]` -> does that file exist and (if named) hold that key."""
    if not spec.startswith("file:"):
        return False
    rel, _, key = spec[5:].partition("#")
    p = root / rel
    if not p.exists():
        return False
    return (not key) or key in _secret_key_names(p)


def env_present(name: str, environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return bool(str(env.get(name, "")).strip())


def accepted_names(var: str) -> tuple[str, ...]:
    """Every environment NAME some reader accepts for `var`, canonical first. A fetcher reads the
    value itself through these names; this module never does."""
    v = BY_ENV.get(var)
    return v.accepted if v else (var,)


def present_names(v: CredentialVar, environ: Mapping[str, str] | None = None,
                  root: Path = ROOT) -> list[str]:
    """Which accepted env names and secrets-file names are present. Names only."""
    got = [n for n in v.accepted if env_present(n, environ)]
    got += [s for s in v.secrets if secret_present(s, root)]
    return got


def status(v: CredentialVar, environ: Mapping[str, str] | None = None,
           root: Path = ROOT) -> dict[str, Any]:
    """SET / MISMATCHED_NAME / BLOCKED_AUTH for one variable, with the consumers left dark."""
    found = present_names(v, environ, root)
    if not found:
        return {"status": BLOCKED_AUTH, "present_as": [], "dark_consumers": [c.path for c in
                                                                           v.consumers]}
    dark = [c.path for c in v.consumers if not any(n in c.reads for n in found)]
    return {"status": MISMATCHED_NAME if dark else SET, "present_as": found,
            "dark_consumers": dark}


def name_mismatches() -> list[dict[str, Any]]:
    """Static: every consumer that does NOT read the canonical (principal's) name."""
    out: list[dict[str, Any]] = []
    for v in REGISTRY:
        for c in v.consumers:
            if v.env not in c.reads:
                out.append({"var": v.env, "consumer": c.path, "branch": c.branch,
                            "reads": [n for n in c.reads if not n.startswith("file:")],
                            "secrets": [n for n in c.reads if n.startswith("file:")]})
    return out


KS_ROSTER = DESK / "data" / "source_rosters" / "keyed_sources.json"


def estimate_for(v: CredentialVar, roster: Path = KS_ROSTER) -> Estimate:
    """The ESTIMATE behind a var's rank. For the keyed_sources leg it is DERIVED from the roster
    (mapped (series, instrument) pairs x cells per pair, bounded by the per-pass cap x 24), so it
    cannot drift from what the leg will actually mint; for other lanes it is the declared shape."""
    if not any(c.leg == KS_LEG for c in v.consumers) or v.kind in ("secret",):
        return v.estimate
    try:
        rows = json.loads(roster.read_text("utf-8")).get("sources") or []
    except (OSError, ValueError, AttributeError):
        return v.estimate
    series = pairs = 0
    for r in rows:
        if isinstance(r, dict) and (r.get("key_env") or [None])[0] == v.env:
            for spec in (r.get("series") or {}).values():
                series += 1
                pairs += len((spec or {}).get("instruments") or {})
    if not pairs:
        return v.estimate
    return Estimate(pairs, 1, KS_CELLS_PER_PAIR, KS_PER_PASS,
                    f"keyed_sources roster: {series} series, {pairs} (series, instrument) pairs "
                    f"x {KS_CELLS_PER_PAIR} cells (8 direct + 6 indirect)")


def normalise_status(word: str) -> str:
    """Another lane's word for an absent key -> BLOCKED_AUTH; anything else unchanged."""
    w = str(word or "").split(":", 1)[0].strip().upper()
    return BLOCKED_AUTH if w in BLOCKED_SYNONYMS else str(word)


def setx_line(v: CredentialVar) -> str:
    """The principal's one-line set command, with a PLACEHOLDER value only."""
    return f'setx {v.env} "<{v.kind}>"'


__all__ = ["BLOCKED_AUTH", "BY_ENV", "KEYLESS", "MISMATCHED_NAME", "REGISTRY", "SET", "UNMEASURED",
           "Consumer", "CredentialVar", "Estimate", "accepted_names", "env_present", "estimate_for",
           "name_mismatches", "normalise_status", "present_names", "secret_present", "setx_line",
           "status"]
