"""The purity fence must fire on a returning crypto desk and stay silent on the desk's memory.

A fence that cannot fire is a comfort, not a check, and this one exists to be handed to an
outside reviewer as evidence. So the first thing pinned here is that planting a crypto-exchange
client in the tree turns it red. The second is the harder half: the desk's graveyard, its
negative-knowledge register and its deep sweeps are full of the word "crypto" on purpose, because
they record the era that was retired. A fence that flagged those would force the desk to burn its
own memory to go green, and the memory is worth more than the tidiness.

The line drawn here is CAPABILITY, not vocabulary. A file that can reach `fapi.binance.com` is a
client. A file that writes the name down in a comment, in a docstring, or in a report is a
record. Only the first is a second desk.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import check_mt5_purity as mp  # noqa: E402


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
    return tmp_path


def test_a_returning_crypto_client_turns_the_fence_red(tmp_path, monkeypatch) -> None:
    """THE NON-VACUITY PROOF. If this ever stops failing, the fence has stopped working."""
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "scripts/run_new_hunter.py":
            'import urllib.request\n'
            'def funding():\n'
            '    return urllib.request.urlopen("https://fapi.binance.com/fapi/v1/premiumIndex")\n',
    }))
    doc = mp.scan()
    hit = doc["reaches_a_crypto_venue"]
    assert [h["file"] for h in hit] == ["scripts/run_new_hunter.py"]
    assert "fapi.binance.com" in hit[0]["hosts"]


def test_the_desks_memory_of_the_retired_era_is_never_flagged(tmp_path, monkeypatch) -> None:
    """The graveyard is the most valuable thing in the repo. Going green must never cost it."""
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "docs/graveyard.md":
            "# What died\n\nThe Binance funding cross-section: 4,102 candidates, zero survivors "
            "net of cost. Endpoint was fapi.binance.com/fapi/v1/fundingRate.\n",
        "docs/research/negative_knowledge.md":
            "Bybit print flags never separated informed from uninformed flow.\n",
        "data/decision_ledger.json":
            '{"retired": "crypto-exchange universe", "host": "api.binance.com"}\n',
    }))
    doc = mp.scan()
    assert doc["reaches_a_crypto_venue"] == []
    assert doc["declares_a_crypto_universe"] == []


def test_a_hostname_in_a_comment_is_a_note_not_a_client(tmp_path, monkeypatch) -> None:
    """`.claude/desk-state.sh` names a banned host precisely to record that it is banned.

    Flagging the enforcement for enforcing is how a fence teaches its readers to skim past it.
    """
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "ops/notes.sh":
            "#!/usr/bin/env bash\n"
            "# fapi.binance.com is BANNED ground under the MT5 mandate -- never re-add.\n"
            "echo ok\n",
        "scripts/reminder.py":
            "# api.bybit.com was retired 2026-08-18.\n"
            "VALUE = 1\n",
    }))
    assert mp.scan()["reaches_a_crypto_venue"] == []


def test_the_same_hostname_in_live_code_is_still_caught(tmp_path, monkeypatch) -> None:
    """The comment rule must not become a way to smuggle a client past the fence."""
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "ops/sneaky.sh":
            "#!/usr/bin/env bash\n"
            "# just a note about api.bybit.com\n"
            'curl -s "https://api.bybit.com/v5/market/tickers?category=linear"\n',
    }))
    doc = mp.scan()
    assert [h["file"] for h in doc["reaches_a_crypto_venue"]] == ["ops/sneaky.sh"]


def test_a_file_declaring_a_crypto_universe_is_caught_without_any_hostname(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "libs/research/thing.py":
            '"""Crypto-native portfolio construction over the perpetual cross-section."""\n'
            "X = 1\n",
    }))
    doc = mp.scan()
    assert [d["file"] for d in doc["declares_a_crypto_universe"]] == ["libs/research/thing.py"]
    assert doc["reaches_a_crypto_venue"] == []


def test_the_permitted_reference_use_and_fusion_cfds_are_not_flagged(tmp_path, monkeypatch) -> None:
    """The mandate PERMITS crypto as reference data informing an MT5 instrument, and permits
    Fusion-executable crypto CFDs. A file saying so plainly is complying, not offending."""
    monkeypatch.setattr(mp, "ROOT", _tree(tmp_path, {
        "desks/mt5/research/ref.py":
            '"""Reads crypto only as information for an MT5 move; never as a hunted universe."""\n'
            "X = 1\n",
        "desks/mt5/research/cfd.py":
            '"""Sizing for Fusion-executable crypto CFDs, which reach the market through the\n'
            'MT5 gateway like every other instrument."""\n'
            "Y = 2\n",
    }))
    doc = mp.scan()
    assert doc["declares_a_crypto_universe"] == []


def test_every_allowlist_entry_states_why_it_survives_an_mt5_only_repo() -> None:
    """A bare allowlist is a list nobody can safely extend. Each entry must answer 'why is this
    not the thing we just deleted?' -- and the deadman rail, the least obvious survivor, must be
    on it, because it is the one Binance module whose deletion would cost real money."""
    assert mp._ALLOWED, "an empty allowlist means the rail is about to be deleted by a cleanup"
    for path, why in mp._ALLOWED.items():
        assert len(why.split()) >= 8, f"{path} has an excuse, not a reason"
    for rail in ("libs/execution/binance_testnet.py", "libs/execution/binance_spot_testnet.py"):
        assert "DEADMAN RAIL" in mp._ALLOWED[rail]


def test_the_real_repo_holds_one_desk() -> None:
    """The claim the principal will hand to an outside reviewer, checked against this tree.

    Named as the finding it is: if this fails, the failure message lists exactly which files
    would give a reader a second desk.
    """
    doc = mp.scan()
    bad = doc["reaches_a_crypto_venue"] + doc["declares_a_crypto_universe"]
    assert not bad, "files that would give a reader a second desk: " + ", ".join(
        sorted(b["file"] for b in bad))
