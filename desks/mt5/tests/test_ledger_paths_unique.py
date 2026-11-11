"""ONE FORWARD LEDGER PER SLEEVE KEY (2026-11-11, the 76 shadow-ledger seal breaches).

`shadow_forward` named a ledger by symbol, family and window only, so every ACTIVE key that
differed in its params wrote ONE file and the last writer won (965 of 1,016 keys on 121 files).
These tests pin the fix: `research/ledger_paths.py` is the only namer, no two ACTIVE keys share a
path, the migration keeps every collided file as read-only evidence and deletes nothing, and the
readers that join by stem refuse a stem several keys share.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import ledger_paths as lp  # noqa: E402

#: Three GBPCHF keys that differ only in params (spread 154 vs 2), the Auditor's example, and the
#: seven XAUUSD.asia variants that all wrote ledger_XAUUSD_asia.json and drive E8 gold sizing.
GBPCHF = ["GBPCHF.carry.asia#spread=154", "GBPCHF.carry.asia#spread=2", "GBPCHF.carry.asia"]
GOLD = ["XAUUSD.asia", "XAUUSD.asia#rr=1.5", "XAUUSD.asia#rr=2.5",
        "XAUUSD.asia#rr=1.5_wait_bars=8", "XAUUSD.asia#session=asia_vol_filter=high",
        "XAUUSD.asia#rr=2.5_session=asia_vol_filter=high",
        "XAUUSD.asia#rr=1.5_session=asia_vol_filter=high"]


def _active_keys() -> set[str]:
    """Every ACTIVE / LIVE key this checkout knows: the sleeve registry and shadow state."""
    keys: set[str] = set()
    reg = DESK / "data" / "sleeve_registry.json"
    try:
        doc = json.loads(reg.read_text("utf-8"))
        keys |= {str(k) for k, v in (doc.get("sleeves") or {}).items()
                 if isinstance(v, dict) and str(v.get("status") or "").upper()
                 in ("ACTIVE", "LIVE", "PROMOTION CANDIDATE")}
    except (OSError, ValueError):
        pass
    for name in ("shadow_state.json", "qquant_shadow_state.json"):
        try:
            doc = json.loads((DESK / "reports" / "shadow" / name).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        keys |= {str(k) for k, v in doc.items()
                 if isinstance(v, dict) and str(v.get("status") or "").upper() == "ACTIVE"}
    try:
        doc = json.loads((DESK / "reports" / "shadow" / "scalp_shadow_state.json")
                         .read_text("utf-8"))
        keys |= {str(k) for k, v in (doc.get("sleeves") or {}).items()
                 if isinstance(v, dict) and str(v.get("status") or "").upper() == "ACTIVE"}
    except (OSError, ValueError, AttributeError):
        pass
    return keys


def test_no_two_active_keys_share_a_ledger_path() -> None:
    keys = _active_keys() | set(GBPCHF) | set(GOLD)
    by_path: dict[str, list[str]] = {}
    for k in keys:
        by_path.setdefault(lp.ledger_name(k), []).append(k)
    shared = {p: ks for p, ks in by_path.items() if len(ks) > 1}
    assert not shared, f"{len(shared)} ledger path(s) shared by several keys: {shared}"


def test_the_old_namer_did_collide_on_these_keys() -> None:
    """The regression is real: the legacy stems of the example keys coincide."""
    import shadow_forward as sf
    rows = [("GBPCHF", "asia", {"spread": s}, "carry", "LONG") for s in (154, 2)]
    owners, _ = sf.ledger_owners(rows)
    assert list(owners.values()) == [sorted(sf.sleeve_key(*r) for r in rows)]


def test_the_name_is_readable_and_names_the_full_key() -> None:
    name = lp.ledger_name("XAUUSD.asia#rr=1.5")
    assert re.fullmatch(r"ledger_XAUUSD_asia__[0-9a-f]{12}\.json", name)
    assert lp.ledger_name("XAUUSD.asia#rr=1.5") != lp.ledger_name("XAUUSD.asia#rr=2.5")
    assert lp.ledger_name("XAUUSD.asia#rr=1.5").startswith("ledger_")   # globs keep working


#: Only this module may build a `ledger_` file name.
_BUILDS = re.compile(
    r"""f["']ledger_\{|["']ledger_["']\s*\+|["']ledger_%s"""      # builds a name
    r"""|removeprefix\(\s*["']ledger_|len\(\s*["']ledger_["']\)"""  # parses one
    r"""|glob\([^)]*["']ledger_|\[7:-5\]""")                         # globs past iter_ledgers


def test_no_module_outside_ledger_paths_builds_parses_or_globs_a_ledger_name() -> None:
    offenders: list[str] = []
    for base in (DESK, ROOT / "scripts", ROOT / "libs"):
        for path in base.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in f"/{rel}" or path.name == "ledger_paths.py":
                continue
            try:
                text = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if _BUILDS.search(line):
                    offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "build ledger names through ledger_paths:\n" + "\n".join(offenders)


# ------------------------------------------------------------------------------ the migration
def _write(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), "utf-8")


def test_migration_keeps_collided_files_as_evidence_and_deletes_nothing(tmp_path) -> None:
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_GBPCHF_carry_asia.json", [{"r_multiple": 1.0}])   # 3 keys shared it
    _write(shadow / "ledger_EURUSD_asia.json", [{"r_multiple": 0.5}, {"r_multiple": -1}])
    _write(shadow / "ledger_ORPHAN_asia.json", [{"r_multiple": 2.0}])         # no key maps
    owners = lp.owners_of([(k, "GBPCHF_carry_asia") for k in GBPCHF]
                          + [("EURUSD.asia", "EURUSD_asia")])
    before = sorted(p.read_bytes() for p in shadow.rglob("*.json"))

    acct = lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow)

    moved = shadow / "_collided" / "ledger_GBPCHF_carry_asia.json"
    assert moved.is_file() and not (shadow / "ledger_GBPCHF_carry_asia.json").exists()
    assert not os.stat(moved).st_mode & stat.S_IWUSR, "evidence must be read-only"
    assert acct["collided"]["ledger_GBPCHF_carry_asia.json"]["keys"] == sorted(GBPCHF)
    # The unique legacy file is that key's own record: renamed, sidecar written.
    own = lp.ledger_path("EURUSD.asia", shadow)
    assert own.is_file() and lp.key_of(own) == "EURUSD.asia"
    assert lp.stem_of(own) == "EURUSD_asia"
    # The orphan is untouched.
    assert (shadow / "ledger_ORPHAN_asia.json").is_file()
    # Nothing deleted: every original byte string still exists somewhere under shadow/.
    after = sorted(p.read_bytes() for p in shadow.rglob("ledger_*.json"))
    assert all(b in after for b in before)
    census = json.loads(lp.census_path("shadow_forward", shadow).read_text("utf-8"))
    assert census["n_collided_files"] == 1 and census["n_collided_keys"] == 3
    assert census["collided"]["ledger_GBPCHF_carry_asia.json"]["integrity"] == "UNMEASURED"
    # Idempotent, and never overwrites evidence.
    assert lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow)["collided"] == {}
    _write(shadow / "ledger_GBPCHF_carry_asia.json", [{"r_multiple": 9.0}])
    again = lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow)
    second = again["collided"]["ledger_GBPCHF_carry_asia.json"]["moved_to"]
    assert second != "ledger_GBPCHF_carry_asia.json"
    assert json.loads(moved.read_text("utf-8")) == [{"r_multiple": 1.0}]


def test_a_stale_legacy_copy_never_overwrites_the_keys_own_ledger(tmp_path) -> None:
    shadow = tmp_path / "shadow"
    own = lp.ledger_path("EURUSD.asia", shadow)
    _write(own, [{"r_multiple": 3.0}])
    _write(shadow / "ledger_EURUSD_asia.json", [{"r_multiple": -3.0}])
    acct = lp.migrate({"ledger_EURUSD_asia.json": ["EURUSD.asia"]}, engine="t",
                      shadow_dir=shadow)
    assert json.loads(own.read_text("utf-8")) == [{"r_multiple": 3.0}]
    assert "ledger_EURUSD_asia.json" in acct["superseded"]
    assert list((shadow / "_collided" / "superseded").glob("*.json"))


# ------------------------------------------------------------------------------- the readers
def _engine_write(shadow: Path, key: str, stem: str, rows: list) -> Path:
    p = lp.ledger_path(key, shadow)
    _write(p, rows)
    lp.register(p, key, engine="shadow_forward", stem=stem)
    return p


def test_resolve_refuses_a_stem_several_keys_share(tmp_path) -> None:
    shadow = tmp_path / "shadow"
    for k in GOLD[:3]:
        _engine_write(shadow, k, "XAUUSD_asia", [{"r_multiple": 1.0}])
    _engine_write(shadow, "EURUSD.asia", "EURUSD_asia", [{"r_multiple": 1.0}])
    assert lp.resolve("XAUUSD.asia#rr=1.5", shadow) == lp.ledger_path("XAUUSD.asia#rr=1.5",
                                                                       shadow)
    assert lp.resolve("XAUUSD_asia", shadow) is None            # three ledgers: refuse
    assert lp.resolve("EURUSD_asia", shadow) == lp.ledger_path("EURUSD.asia", shadow)
    names, ambiguous = lp.join_names(lp.iter_ledgers(shadow))
    assert set(ambiguous) == {"XAUUSD_asia"}
    assert names[lp.ledger_path("EURUSD.asia", shadow)] == "EURUSD_asia"
    assert {names[lp.ledger_path(k, shadow)] for k in GOLD[:3]} == set(GOLD[:3])


def test_a_mirror_never_reads_a_retired_shared_copy(tmp_path) -> None:
    shadow, mirror = tmp_path / "shadow", tmp_path / "mirror"
    _write(shadow / "ledger_GBPCHF_carry_asia.json", [{"r_multiple": 1.0}])
    _write(mirror / "ledger_GBPCHF_carry_asia.json", [{"r_multiple": 1.0}])
    lp.migrate(lp.owners_of((k, "GBPCHF_carry_asia") for k in GBPCHF), engine="shadow_forward",
               shadow_dir=shadow)
    names = [p.name for p in lp.iter_ledgers([shadow, mirror])]
    assert "ledger_GBPCHF_carry_asia.json" not in names


def test_gold_asia_column_reads_its_own_clock_and_never_a_variant(tmp_path, monkeypatch) -> None:
    """The allocator column `gold_asia` joins clock `XAUUSD.asia` exactly (Auditor 02:27Z)."""
    from research import portfolio_evidence as pe

    shadow = tmp_path / "shadow"
    _engine_write(shadow, "XAUUSD.asia", "XAUUSD_asia",
                  [{"phase": "forward", "entry_time": "2026-11-02T04:00", "r_multiple": 2.0}])
    _engine_write(shadow, "XAUUSD.asia#rr=1.5", "XAUUSD_asia",
                  [{"phase": "forward", "entry_time": "2026-11-02T04:00", "r_multiple": -1.0}])
    monkeypatch.setattr(pe, "SHADOW", shadow)
    series = pe.daily_series()
    assert series["gold_asia"] == {"2026-11-02": 2.0}
    assert "XAUUSD_asia" not in series                          # shared stem: not joined
    assert set(pe.ambiguous_stems()) == {"XAUUSD_asia"}
    status = pe.column_clock_status()
    assert status["gold_asia"]["status"] == "JOINED"
    assert status["gold_asia"]["ledger"] == lp.ledger_name("XAUUSD.asia")
    assert status["gold_asia"]["integrity"] == "OWN_REPLAY"


def test_only_gold_asia_is_mapped_and_the_other_gold_columns_read_unmeasured(
        tmp_path, monkeypatch) -> None:
    """Auditor S4: only the clock decision_core NAMES is joined; the inferred two are not."""
    from research import portfolio_evidence as pe

    assert pe.COLUMN_CLOCKS == {"gold_asia": "XAUUSD.asia"}
    shadow = tmp_path / "shadow"
    _engine_write(shadow, "XAUUSD.london_am", "XAUUSD_london_am",
                  [{"phase": "forward", "entry_time": "2026-11-02T10:00", "r_multiple": 1.0}])
    monkeypatch.setattr(pe, "SHADOW", shadow)
    series = pe.daily_series()
    assert "gold_london_am" not in series and "gold_afternoon" not in series
    assert "XAUUSD_london_am" in series                         # its own unique stem still joins
    status = pe.column_clock_status()
    assert status["gold_london_am"]["status"] == "UNMEASURED"
    assert status["gold_afternoon"]["status"] == "UNMEASURED"
    assert status["gold_asia"]["status"] == "NO_LEDGER"


def test_the_allocation_artifact_publishes_the_forward_join() -> None:
    src = (DESK / "research" / "pf_allocator.py").read_text("utf-8")
    assert '"forward_join": dict(_FORWARD_JOIN)' in src
    assert "column_clock_status()" in src and '"ambiguous_stems": _amb' in src


def test_forward_engines_name_ledgers_only_through_ledger_paths() -> None:
    for name in ("shadow_forward.py", "qquant_shadow.py", "scalp_shadow.py"):
        text = (DESK / "research" / name).read_text("utf-8")
        assert "ledger_path(" in text and "register(" in text and "migrate" in text, name


@pytest.mark.parametrize("key", GBPCHF + GOLD)
def test_sidecar_round_trip(tmp_path, key: str) -> None:
    p = _engine_write(tmp_path, key, "STEM_x", [])
    assert lp.key_of(p) == key and lp.label_of(p) == key and lp.is_keyed(p)


# --------------------------------------------------------------------- Auditor HOLD, 1dee9f44
def test_a_failed_move_is_recorded_and_the_census_is_still_written(tmp_path, monkeypatch) -> None:
    """M1: one file failing never stops the others, and the census always goes out."""
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_GBPCHF_carry_asia.json", [{"r_multiple": 1.0}])
    _write(shadow / "ledger_XAUUSD_asia.json", [{"r_multiple": 2.0}])
    owners = lp.owners_of([(k, "GBPCHF_carry_asia") for k in GBPCHF]
                          + [(k, "XAUUSD_asia") for k in GOLD])
    real = lp._move_one

    def flaky(name, *a, **kw):
        if name == "ledger_GBPCHF_carry_asia.json":
            raise PermissionError("locked by a reader")
        return real(name, *a, **kw)

    monkeypatch.setattr(lp, "_move_one", flaky)
    acct = lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow)
    assert "ledger_GBPCHF_carry_asia.json" in acct["failed"]
    assert acct["failed"]["ledger_GBPCHF_carry_asia.json"]["n_keys"] == len(GBPCHF)
    assert "ledger_XAUUSD_asia.json" in acct["collided"]         # the other file still moved
    census = json.loads(lp.census_path("shadow_forward", shadow).read_text("utf-8"))
    assert census["n_failed"] == 1 and "ledger_XAUUSD_asia.json" in census["collided"]
    # the shared file that could not move is still retired from every reader
    assert "ledger_GBPCHF_carry_asia.json" in lp.retired_legacy_names(shadow)
    assert all(p.name != "ledger_GBPCHF_carry_asia.json" for p in lp.iter_ledgers(shadow))

    monkeypatch.setattr(lp, "_move_one", real)                   # next pass succeeds
    lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow)
    census = json.loads(lp.census_path("shadow_forward", shadow).read_text("utf-8"))
    assert census["n_failed"] == 0 and "ledger_GBPCHF_carry_asia.json" in census["collided"]


def test_a_legacy_file_is_never_joined_by_stem(tmp_path) -> None:
    """M1: a legacy-named file cannot say whose it is, so it never owns a stem."""
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_EURUSD_asia.json", [{"r_multiple": 1.0}])
    assert lp.resolve("EURUSD_asia", shadow) is None
    names, _ = lp.join_names(list(lp.iter_ledgers(shadow)))
    assert names[shadow / "ledger_EURUSD_asia.json"] != "EURUSD_asia"


def test_a_renamed_file_is_unmeasured_until_its_own_replay_rewrites_it(tmp_path) -> None:
    """S2: the migration's rename is not the key's own replay; the engine's write is."""
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_EURUSD_asia.json", [{"r_multiple": 1.0}])
    lp.migrate(lp.owners_of([("EURUSD.asia", "EURUSD_asia")]), engine="shadow_forward",
               shadow_dir=shadow)
    own = lp.ledger_path("EURUSD.asia", shadow)
    assert own.is_file() and lp.integrity_of(own) == "UNMEASURED"
    _engine_write(shadow, "EURUSD.asia", "EURUSD_asia", [{"r_multiple": 0.5}])
    assert lp.integrity_of(own) == "OWN_REPLAY"


def test_engines_register_only_after_the_ledger_is_written() -> None:
    """S2: a sidecar must never claim OWN_REPLAY for a file the engine has not yet written."""
    for name in ("shadow_forward.py", "qquant_shadow.py", "scalp_shadow.py"):
        lines = (DESK / "research" / name).read_text("utf-8").splitlines()
        reg = [i for i, ln in enumerate(lines) if "_lp.register(" in ln]
        assert reg, name
        for i in reg:
            window = "\n".join(lines[max(0, i - 12):i])
            assert "write_text(" in window or "atomic" in window.lower(), (name, i + 1)


def test_the_seal_rows_of_retired_files_are_annotated_never_dropped(tmp_path) -> None:
    """S3: the record wall's rows are kept and marked, so the re-seal carries them forward."""
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_XAUUSD_asia.json", [{"r_multiple": 2.0}])
    _write(shadow / "ledger_EURUSD_asia.json", [{"r_multiple": 1.0}])
    manifest = tmp_path / "IMMUTABLE_MANIFEST.json"
    seal = {"sha256": "ab", "n": 1}
    manifest.write_text(json.dumps({"append_only": {
        lp.SEAL_PREFIX + "ledger_XAUUSD_asia.json": dict(seal),
        lp.SEAL_PREFIX + "ledger_EURUSD_asia.json": dict(seal),
        lp.SEAL_PREFIX + "ledger_OTHER_asia.json": dict(seal)}}), "utf-8")
    owners = lp.owners_of([(k, "XAUUSD_asia") for k in GOLD] + [("EURUSD.asia", "EURUSD_asia")])
    lp.migrate(owners, engine="shadow_forward", shadow_dir=shadow, manifest=manifest)
    rows = json.loads(manifest.read_text("utf-8"))["append_only"]
    gold = rows[lp.SEAL_PREFIX + "ledger_XAUUSD_asia.json"]
    assert gold["sha256"] == "ab" and gold["n"] == 1             # the seal itself is kept
    assert gold["collided"] is True and gold["retired_as"] == "collided"
    assert sorted(gold["keys"]) == sorted(GOLD) and gold["integrity"] == "UNMEASURED"
    eur = rows[lp.SEAL_PREFIX + "ledger_EURUSD_asia.json"]
    assert eur["collided"] is False and eur["retired_as"] == "renamed"
    assert "retired_by" not in rows[lp.SEAL_PREFIX + "ledger_OTHER_asia.json"]
    assert json.loads(manifest.read_text("utf-8"))["collided_seal_rows"] == 2


def test_a_test_migration_never_touches_the_desks_own_manifest(tmp_path) -> None:
    before = lp.MANIFEST.read_bytes() if lp.MANIFEST.exists() else None
    shadow = tmp_path / "shadow"
    _write(shadow / "ledger_XAUUSD_asia.json", [{"r_multiple": 2.0}])
    lp.migrate(lp.owners_of([(k, "XAUUSD_asia") for k in GOLD]), engine="shadow_forward",
               shadow_dir=shadow)
    assert (lp.MANIFEST.read_bytes() if lp.MANIFEST.exists() else None) == before


def test_sleeve_id_is_unique_per_ledger_and_parses_like_the_stem(tmp_path) -> None:
    """M2: readers that split a label on `_` keep their symbol; variants never merge."""
    shadow = tmp_path / "shadow"
    paths = [_engine_write(shadow, k, "XAUUSD_asia", [{"r_multiple": 1.0}]) for k in GOLD]
    ids = [lp.sleeve_id(p) for p in paths]
    assert len(set(ids)) == len(GOLD)
    assert all(i.split("_")[0] == "XAUUSD" and i.startswith("XAUUSD_asia~") for i in ids)
    _write(shadow / "ledger_EURUSD_asia.json", [])
    assert lp.sleeve_id(shadow / "ledger_EURUSD_asia.json") == "EURUSD_asia"
