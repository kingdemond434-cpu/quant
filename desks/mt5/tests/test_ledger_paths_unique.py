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
_BUILDS = re.compile(r"""f["']ledger_\{|["']ledger_["']\s*\+|["']ledger_%s""")


def test_no_module_outside_ledger_paths_builds_a_ledger_name() -> None:
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


def test_forward_engines_name_ledgers_only_through_ledger_paths() -> None:
    for name in ("shadow_forward.py", "qquant_shadow.py", "scalp_shadow.py"):
        text = (DESK / "research" / name).read_text("utf-8")
        assert "ledger_path(" in text and "register(" in text and "migrate" in text, name


@pytest.mark.parametrize("key", GBPCHF + GOLD)
def test_sidecar_round_trip(tmp_path, key: str) -> None:
    p = _engine_write(tmp_path, key, "STEM_x", [])
    assert lp.key_of(p) == key and lp.label_of(p) == key and lp.is_keyed(p)
