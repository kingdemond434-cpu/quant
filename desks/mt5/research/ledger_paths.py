"""THE ONLY NAMER OF A FORWARD LEDGER. One file per sleeve key, in every forward engine.

THE DEFECT THIS EXISTS TO END (Auditor root cause of the 76 shadow-ledger seal breaches,
2026-11-11). `shadow_forward` named a ledger by symbol, family and window alone --

    ledger_{sym}_{win}.json          session_range_breakout
    ledger_{sym}_{fam}_{win}.json    every other family

-- so every ACTIVE key that differed only in its params (three GBPCHF keys at spread 154 and 2;
seven XAUUSD.asia variants) wrote ONE file and the last writer won. Measured on the box: 965 of
1,016 keys shared 121 files. A sealed prefix then "changed" with no edit, a certificate could cite
another sleeve's trades, and every reader that joined by file name read whichever variant wrote
last. GBPCHF flipped from winning to losing without a single trade changing.

THE RULE NOW:

    ledger_path(key)  ->  reports/shadow/ledger_<slug>__<sha1(key)[:12]>.json

The slug is a readable prefix of the key (symbol, family, window); the hash makes the name unique
to the FULL key, params, chart and side included. New names still match `ledger_*.json`, so every
glob reader keeps working; a reader that needs to know WHOSE ledger a file is asks `key_of(path)`
(and `stem_of(path)` for the old `<sym>_<fam>_<win>` join stem), never the file name.

`desks/mt5/tests/test_ledger_paths_unique.py` fails if two ACTIVE keys resolve to one path, or if
any module outside this one builds a `ledger_` file name by hand.

WHO OWNS A FILE is recorded in a sidecar, `reports/shadow/_keys/<ledger file name>`, written by
the engine beside each ledger. One small file per ledger, so three engines never race on a shared
index, and `_keys/` sits outside the `ledger_*.json` glob so no reader mistakes it for trades.

MIGRATION, NEVER A MERGE (`migrate`). Each engine re-derives its whole ledger from its own replay
every pass, so nothing is lost by retiring a collided file -- and nothing is gained by trying to
split one, because the last writer erased the others. So:

    legacy file one key maps to   renamed to that key's path (its content was only ever that key's)
    legacy file >1 keys map to    MOVED to reports/shadow/_collided/, made read-only, kept as
                                  evidence, and listed in the census with every key that shared it
    legacy file no key maps to    left exactly where it is (an orphan is not ours to judge)

Nothing is ever deleted and no evidence file is ever overwritten: a name already present under
`_collided/` gets a time suffix. Until a key's ledger is rebuilt from its own replay, any
certificate or promotion that cited the collided file is UNMEASURED-integrity -- nothing is voided
or resized here; the Judge re-reads after the fix.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
SHADOW_DIR = BASE / "reports" / "shadow"
#: Sidecars: one JSON per ledger, same file name, saying which sleeve key owns it.
KEYS_DIR_NAME = "_keys"
#: Evidence: collided legacy files, read-only, never deleted.
COLLIDED_DIR_NAME = "_collided"

PREFIX = "ledger_"
SUFFIX = ".json"
HASH_LEN = 12
SLUG_MAX = 80

_SLUG_BAD = re.compile(r"[^A-Za-z0-9]+")
_KEYED_NAME = re.compile(r"^ledger_(?P<slug>.*)__(?P<h>[0-9a-f]{12})\.json$")


# ------------------------------------------------------------------------------- the namer
def key_hash(key: str) -> str:
    """sha1 of the full sleeve key, first 12 hex characters."""
    return hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:HASH_LEN]


def slug(key: str) -> str:
    """A readable prefix: the key before its params tail, with every run of punctuation as `_`.

    `XAUUSD.asia#spread=2` -> `XAUUSD_asia`; `GBPCHF.mean_rev.london@M5#x=1.SHORT` ->
    `GBPCHF_mean_rev_london_M5`. Readability only; uniqueness is the hash's job.
    """
    head = str(key).split("#", 1)[0]
    s = _SLUG_BAD.sub("_", head).strip("_")
    return (s[:SLUG_MAX].rstrip("_")) or "sleeve"


def ledger_name(key: str) -> str:
    """The file name of `key`'s forward ledger."""
    return f"{PREFIX}{slug(key)}__{key_hash(key)}{SUFFIX}"


def ledger_path(key: str, shadow_dir: Path | None = None) -> Path:
    """THE ONLY WAY TO NAME A FORWARD LEDGER: one path per full sleeve key."""
    return Path(shadow_dir or SHADOW_DIR) / ledger_name(key)


def legacy_name(stem: str) -> str:
    """The pre-2026-11-11 file name for a legacy join stem. For migration and evidence ONLY."""
    return f"{PREFIX}{stem}{SUFFIX}"


def legacy_stem_forward(sym: str, family: str, window: str) -> str:
    """The stem `shadow_forward` used to name a ledger by: symbol, family and window only.

    It is no longer a file name. It survives as a JOIN STEM because the allocator's backtest matrix
    and several monitors key their own rows `<sym>_<fam>_<win>`; such a join must be unique to be
    used (see `unique_by_stem`).
    """
    if family == "session_range_breakout":
        return f"{sym}_{window}"
    return f"{sym}_{family}_{window}"


def legacy_stem_qquant(key: str) -> str:
    return str(key).replace(" ", "_").replace("/", "_")


def legacy_stem_scalp(name: str) -> str:
    return str(name)


# --------------------------------------------------------------------------- the sidecar
def _keys_dir(shadow_dir: Path) -> Path:
    return Path(shadow_dir) / KEYS_DIR_NAME


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def register(path: Path, key: str, *, engine: str, stem: str | None = None,
             integrity: str = "OWN_REPLAY") -> None:
    """Record that `path` is `key`'s ledger. Idempotent; rewritten only when it changes.

    `integrity` is OWN_REPLAY when the engine has just written the file from this key's own
    replay, and UNMEASURED when the migration renamed a legacy file to it (Auditor S2): its
    content was one key's by the census, but no replay of that key has re-derived it yet.
    Engines call this AFTER the write, so OWN_REPLAY is never claimed for a file not written.
    """
    path = Path(path)
    side = _keys_dir(path.parent) / path.name
    doc = {"sleeve_key": str(key), "engine": engine, "stem": stem, "name": path.name,
           "integrity": integrity}
    try:
        if json.loads(side.read_text("utf-8")) == doc:
            return
    except (OSError, ValueError):
        pass
    _atomic_write(side, json.dumps(doc, indent=1, sort_keys=True))


def _sidecar(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    for d in (_keys_dir(path.parent), _keys_dir(SHADOW_DIR)):
        try:
            doc = json.loads((d / path.name).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("sleeve_key"):
            return doc
    return None


def is_keyed(path: Path | str) -> bool:
    """True for a ledger named by this module (slug + hash), False for a legacy name."""
    return bool(_KEYED_NAME.match(Path(path).name))


def key_of(path: Path | str) -> str | None:
    """The sleeve key that owns this ledger, or None when that is not known.

    A legacy-named file returns None: its name was shared, so it cannot say whose it is.
    """
    doc = _sidecar(Path(path))
    if doc is None:
        return None
    if is_keyed(path) and ledger_name(doc["sleeve_key"]) != Path(path).name:
        return None                               # a sidecar that disagrees with the name lies
    return str(doc["sleeve_key"])


def stem_of(path: Path | str) -> str:
    """The legacy `<sym>_<fam>_<win>`-shaped join stem of a ledger.

    From the sidecar for a keyed file (the stem the engine declared); from the name itself for a
    legacy file. Several keyed files may share one stem -- that is the point of the fix -- so a
    reader that joins on it must refuse ambiguity (`unique_by_stem`), never merge.
    """
    p = Path(path)
    doc = _sidecar(p)
    if doc is not None and doc.get("stem"):
        return str(doc["stem"])
    m = _KEYED_NAME.match(p.name)
    if m:
        return m.group("slug")
    return p.name[len(PREFIX):-len(SUFFIX)] if p.name.startswith(PREFIX) else p.stem


def integrity_of(path: Path | str) -> str:
    """OWN_REPLAY, or UNMEASURED (renamed by the migration and not yet rebuilt, or unknown)."""
    doc = _sidecar(Path(path))
    return str((doc or {}).get("integrity") or "UNMEASURED")


def label_of(path: Path | str) -> str:
    """A per-sleeve label that is UNIQUE per ledger: the sleeve key when known, else the stem."""
    return key_of(path) or stem_of(path)


def sleeve_id(path: Path | str) -> str:
    """A per-ledger id that is UNIQUE per file and still parses like the legacy stem.

    `<stem>~<hash>` for a keyed ledger, the bare stem for a legacy one. Readers that split a sleeve
    label on `_` for its symbol or family (excursions, regime_coverage, alpha_breadth) keep
    working, and two params variants of one stem are two sleeves, never one merged series.
    """
    p = Path(path)
    m = _KEYED_NAME.match(p.name)
    stem = stem_of(p)
    return f"{stem}~{m.group('h')}" if m else stem


def find(key: str, shadow_dir: Path | None = None) -> Path | None:
    """`key`'s own ledger if it exists. Never a neighbour's, never a legacy shared file."""
    p = ledger_path(key, shadow_dir)
    return p if p.is_file() else None


def read_rows(key: str, shadow_dir: Path | None = None, default: object = None) -> object:
    """`key`'s own ledger rows, or `default` when it has none yet (UNMEASURED, not zero)."""
    p = find(key, shadow_dir)
    if p is None:
        return [] if default is None else default
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return [] if default is None else default


def migrated(shadow_dir: Path | None = None, engine: str = "shadow_forward") -> bool:
    """True once `engine`'s migration has run here (its census exists).

    Before that, a legacy-named file may still be a SHARED file, so `resolve` will not hand one
    out: the answer is UNMEASURED for at most one engine pass, never a neighbour's trades.
    """
    return census_path(engine, shadow_dir).is_file()


def _join_candidates(name: str) -> set[str]:
    n = str(name)
    head = n.split("#", 1)[0]
    return {n, n.replace(".", "_"), head, head.replace(".", "_"),
            n.replace(".", "_").replace("#", "_")}


def resolve(name: str, dirs: Iterable[Path] | Path | None = None) -> Path | None:
    """The ONE ledger a sleeve name answers to, or None. Never a guess between several.

    1. the name as a full sleeve key: its own keyed ledger;
    2. else the name as a legacy join stem (`CADJPY_asia`, `CADJPY.asia`): the ledger whose
       declared stem it is -- only when exactly ONE ledger declares it. Two keyed ledgers on one
       stem are two strategies; a reader that wants one of them must name its key.

    A legacy-named file is NEVER returned for a stem (Auditor M1): its name may still be a file
    several keys shared -- a migration that failed part-way, a mirror's stale copy -- and the
    answer is then UNMEASURED, never a neighbour's trades.
    """
    if dirs is None:
        dirs = [SHADOW_DIR]
    elif isinstance(dirs, (str, Path)):
        dirs = [Path(dirs)]
    dirs = [Path(d) for d in dirs]
    for d in dirs:
        p = find(name, d)
        if p is not None:
            return p
    index = _stem_index(tuple(dirs))
    hits: list[Path] = []
    for c in _join_candidates(name):
        for p in index.get(c, ()):
            if is_keyed(p) and key_of(p) and p not in hits:
                hits.append(p)
    return hits[0] if len(hits) == 1 else None


_STEM_CACHE: dict[tuple[Path, ...], tuple[tuple[Any, ...], dict[str, list[Path]]]] = {}


def _dir_sig(d: Path) -> tuple[int | None, ...]:
    out: list[int | None] = []
    for x in (d, d / KEYS_DIR_NAME, d / COLLIDED_DIR_NAME):
        try:
            out.append(x.stat().st_mtime_ns)
        except OSError:
            out.append(None)
    return tuple(out)


def _stem_index(dirs: tuple[Path, ...]) -> dict[str, list[Path]]:
    """{join stem: [ledgers declaring it]} over `dirs`, cached until a directory changes."""
    sig = tuple(_dir_sig(d) for d in dirs) + (_dir_sig(SHADOW_DIR),)
    hit = _STEM_CACHE.get(dirs)
    if hit is not None and hit[0] == sig:
        return hit[1]
    index: dict[str, list[Path]] = {}
    for p in iter_ledgers(list(dirs)):
        index.setdefault(stem_of(p), []).append(p)
    _STEM_CACHE[dirs] = (sig, index)
    return index


def resolve_rows(name: str, dirs: Iterable[Path] | Path | None = None) -> list[Any]:
    """`resolve(name)`'s rows, or [] when no single ledger answers (UNMEASURED, not zero)."""
    p = resolve(name, dirs)
    if p is None:
        return []
    try:
        rows = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return rows if isinstance(rows, list) else []


# ------------------------------------------------------------------------- the census
def _collided_dir(shadow_dir: Path) -> Path:
    return Path(shadow_dir) / COLLIDED_DIR_NAME


def census_path(engine: str, shadow_dir: Path | None = None) -> Path:
    return _collided_dir(Path(shadow_dir or SHADOW_DIR)) / f"CENSUS_{engine}.json"


def retired_legacy_names(shadow_dir: Path | None = None) -> frozenset[str]:
    """Every legacy file name a migration retired (collided or renamed), across all engines.

    A mirror (backups/moat/shadow_ledgers) may still hold copies under those names; they are no
    longer any sleeve's forward evidence and `iter_ledgers` skips them.
    """
    out: set[str] = set()
    d = _collided_dir(Path(shadow_dir or SHADOW_DIR))
    for f in sorted(d.glob("CENSUS_*.json")) if d.is_dir() else ():
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for part in ("collided", "renamed", "superseded"):
            out.update((doc.get(part) or {}).keys())
        # A shared file whose move FAILED is still shared: never anyone's evidence.
        out.update(n for n, v in (doc.get("failed") or {}).items()
                   if isinstance(v, dict) and int(v.get("n_keys") or 0) > 1)
    return frozenset(out)


def iter_ledgers(dirs: Iterable[Path] | Path, pattern: str = "ledger_*.json",
                 ) -> Iterator[Path]:
    """Every forward ledger under `dirs`, each file name once (the first directory wins).

    Skips the legacy names a migration retired, so a mirror's stale shared copy is never read as
    a sleeve's evidence beside that sleeve's own keyed ledger.
    """
    if isinstance(dirs, (str, Path)):
        dirs = [Path(dirs)]
    dirs = [Path(d) for d in dirs]
    retired = retired_legacy_names(dirs[0] if dirs else None) | retired_legacy_names()
    seen: set[str] = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob(pattern)):
            if f.name in seen or f.name in retired or not f.is_file():
                continue
            seen.add(f.name)
            yield f


def unique_by_stem(paths: Iterable[Path]) -> tuple[dict[str, Path], dict[str, list[str]]]:
    """{stem: path} for stems exactly ONE ledger answers to; {stem: [names]} for the rest.

    A join on the legacy stem is only honest when one sleeve owns it. Two keyed ledgers on one
    stem are two strategies, and merging them is the splice this module exists to end.
    """
    groups: dict[str, list[Path]] = {}
    for p in paths:
        groups.setdefault(stem_of(p), []).append(Path(p))
    unique = {s: ps[0] for s, ps in groups.items() if len(ps) == 1}
    ambiguous = {s: sorted(p.name for p in ps) for s, ps in groups.items() if len(ps) > 1}
    return unique, ambiguous


def join_names(paths: Iterable[Path]) -> tuple[dict[Path, str], dict[str, list[str]]]:
    """One published name per ledger, for readers whose consumers join on the legacy stem.

    A ledger whose stem ONE ledger owns keeps that stem, so every existing join is unchanged for
    it. Ledgers that share a stem (params variants of one cell) are published under their own
    sleeve key instead -- which joins nothing keyed by the stem, on purpose: the old stem join
    read whichever variant wrote last, and `pf_allocator.join_forward` already refuses an
    ambiguous join rather than spreading it. Returns ({path: name}, {stem: [ledger names]}).
    """
    paths = list(paths)
    unique, ambiguous = unique_by_stem(paths)
    # ONLY A KEYED LEDGER WITH A KNOWN OWNER MAY CARRY A STEM (Auditor M1). A legacy or unkeyed
    # file is published under its own file name (`ledger_<stem>`), so a shared file a migration could not move,
    # or a mirror's stale copy, never reaches a stem-joined consumer as one sleeve's record.
    owner = {p: s for s, p in unique.items() if is_keyed(p) and key_of(p)}
    return {p: owner.get(p) or key_of(p) or p.stem for p in paths}, ambiguous


# ------------------------------------------------------------------------- the migration
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _records(path: Path) -> int | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return len(doc) if isinstance(doc, list) else None


def _free_target(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    while True:
        cand = path.with_name(f"{path.stem}.{stamp}{'' if n == 0 else f'.{n}'}{path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def _read_only(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


#: The record wall's signed manifest (scripts/check_immutable_evaluator.py). Seal rows of the
#: legacy files a migration retires are ANNOTATED there (Auditor S3), never removed: the
#: journaled box-side re-seal must carry every one of them forward.
MANIFEST = BASE / "data" / "IMMUTABLE_MANIFEST.json"
SEAL_PREFIX = "desks/mt5/reports/shadow/"


def _move_one(name: str, keys: list[str], sd: Path, cdir: Path, engine: str,
              stems: Mapping[str, str], acct: dict[str, Any]) -> None:
    src = sd / name
    sha, n = _sha256(src), _records(src)
    if len(keys) == 1:
        dst = ledger_path(keys[0], sd)
        if dst.exists():
            # The key already has its own ledger; this legacy copy is stale. Evidence, not
            # trades: move it aside, never over the key's own file.
            tgt = _free_target(cdir / "superseded" / name)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, tgt)
            _read_only(tgt)
            acct["superseded"][name] = {"key": keys[0], "moved_to": f"superseded/{tgt.name}",
                                        "sha256": sha, "records": n}
            return
        os.replace(src, dst)
        # UNMEASURED until this key's own replay rewrites it (Auditor S2).
        register(dst, keys[0], engine=engine, stem=stems.get(keys[0]), integrity="UNMEASURED")
        acct["renamed"][name] = {"key": keys[0], "to": dst.name, "sha256": sha, "records": n,
                                 "integrity": "UNMEASURED"}
        return
    cdir.mkdir(parents=True, exist_ok=True)
    tgt = _free_target(cdir / name)
    os.replace(src, tgt)
    _read_only(tgt)
    acct["collided"][name] = {"keys": keys, "n_keys": len(keys), "moved_to": tgt.name,
                              "sha256": sha, "records": n, "collided": True,
                              "integrity": "UNMEASURED"}


def migrate(owners: Mapping[str, Sequence[str]], *, engine: str,
            shadow_dir: Path | None = None, stems: Mapping[str, str] | None = None,
            now: datetime | None = None, manifest: Path | None = None) -> dict[str, Any]:
    """Retire every legacy-named ledger this engine's keys map to. Idempotent; deletes nothing.

    `owners` is {legacy file name: [every sleeve key that maps to it]}, built from the engine's
    FULL key set (never a partial `rows=` pass, or a shared file would look like one key's).
    `stems` is {key: join stem}, recorded in each sidecar.

    EACH FILE IS ITS OWN TRANSACTION AND THE CENSUS IS ALWAYS WRITTEN (Auditor M1). A move that
    fails is recorded under `failed` with its keys and the error, and the census goes out in a
    `finally` -- so every file already moved is retired from every reader even when a later one
    fails, and a shared file that could not be moved is retired too (`retired_legacy_names`).

    `manifest` is the record wall's manifest whose seal rows are annotated; it defaults to the
    desk's own only when `shadow_dir` IS the desk's shadow directory, so a test never touches it.

    Returns this pass's accounting; the cumulative census is `census_path(engine)`.
    """
    sd = Path(shadow_dir or SHADOW_DIR)
    cdir = _collided_dir(sd)
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    stems = stems or {}
    acct: dict[str, Any] = {"engine": engine, "at": stamp, "collided": {}, "renamed": {},
                            "superseded": {}, "failed": {}, "absent": 0}
    try:
        for name, keys in sorted(owners.items()):
            src = sd / name
            if not src.is_file() or is_keyed(src):
                acct["absent"] += 1
                continue
            ks = sorted({str(k) for k in keys})
            try:
                _move_one(name, ks, sd, cdir, engine, stems, acct)
            except Exception as exc:                  # one file never stops the others
                acct["failed"][name] = {"keys": ks, "n_keys": len(ks),
                                        "why": f"{type(exc).__name__}: {exc}",
                                        "integrity": "UNMEASURED"}
    finally:
        if owners:
            _write_census(engine, sd, acct)
            if manifest is None and sd.resolve() == SHADOW_DIR.resolve():
                manifest = MANIFEST
            if manifest is not None:
                try:
                    annotate_seals(manifest, acct)
                except Exception as exc:              # the census already holds the record
                    acct["seal_annotation_error"] = f"{type(exc).__name__}: {exc}"
    return acct


def annotate_seals(manifest: Path, acct: Mapping[str, Any]) -> int:
    """Mark the seal row of every legacy file this pass retired `collided` (Auditor S3).

    The row is KEPT, byte for byte, with fields added beside it: the files leave the record
    wall's `ledger_*.json` glob, so the checker stops judging them, and the re-seal (box-side,
    journaled) must carry these rows forward rather than drop them. Returns rows annotated.
    """
    try:
        doc = json.loads(Path(manifest).read_text("utf-8"))
    except (OSError, ValueError):
        return 0
    rows = doc.get("append_only") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return 0
    n = 0
    for part in ("collided", "renamed", "superseded", "failed"):
        for name, info in (acct.get(part) or {}).items():
            row = rows.get(SEAL_PREFIX + name)
            if not isinstance(row, dict) or row.get("retired_by"):
                continue
            row.update({"collided": part in ("collided", "failed"), "retired_by":
                        "ledger_paths.migrate", "retired_as": part, "retired_at": acct["at"],
                        "moved_to": info.get("moved_to") or info.get("to"),
                        "keys": info.get("keys") or [info.get("key")],
                        "integrity": "UNMEASURED"})
            n += 1
    if n:
        doc["collided_seal_rows"] = sum(1 for r in rows.values()
                                        if isinstance(r, dict) and r.get("retired_by"))
        _atomic_write(Path(manifest), json.dumps(doc, indent=1))
    return n


def _write_census(engine: str, sd: Path, acct: dict[str, Any]) -> None:
    """Cumulative per-engine census plus one journal line per pass that moved anything."""
    path = census_path(engine, sd)
    try:
        doc = json.loads(path.read_text("utf-8"))
        if not isinstance(doc, dict):
            doc = {}
    except (OSError, ValueError):
        doc = {}
    for part in ("collided", "renamed", "superseded", "failed"):
        merged = dict(doc.get(part) or {})
        merged.update(acct[part])
        doc[part] = merged
    # A file that failed once and moved later is no longer a failure.
    for part in ("collided", "renamed", "superseded"):
        for name in acct[part]:
            doc["failed"].pop(name, None)
    doc.update({
        "engine": engine, "updated_at": acct["at"],
        "rule": ("one forward ledger per sleeve key (desks/mt5/research/ledger_paths.py). "
                 "Collided legacy files are kept here read-only as evidence and never deleted; "
                 "any certificate or promotion that cited one is UNMEASURED-integrity until the "
                 "key's own ledger is rebuilt from its own replay and the Judge re-reads it. "
                 "Renamed single-owner files are UNMEASURED until their key's own replay "
                 "rewrites them. Nothing is voided or resized by this migration."),
        "n_collided_files": len(doc["collided"]),
        "n_collided_keys": sum(int(v.get("n_keys") or 0) for v in doc["collided"].values()),
        "n_failed": len(doc["failed"]),
    })
    _atomic_write(path, json.dumps(doc, indent=1, sort_keys=True))
    if not (acct["collided"] or acct["renamed"] or acct["superseded"] or acct["failed"]):
        return
    journal = path.parent / "MIGRATION.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: acct[k] for k in ("engine", "at")}
                            | {p: sorted(acct[p])
                               for p in ("collided", "renamed", "superseded", "failed")},
                            sort_keys=True) + "\n")


def owners_of(entries: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """{legacy file name: [keys]} from (key, legacy stem) pairs."""
    out: dict[str, set[str]] = {}
    for key, stem in entries:
        out.setdefault(legacy_name(stem), set()).add(str(key))
    return {n: sorted(ks) for n, ks in out.items()}
