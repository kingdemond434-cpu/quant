"""The research-data fence (Governance, route A, 2026-11-18): no money-path reader of the home.

desks/mt5/research/data/ is outside every MONEY_PATH prefix, which is only safe while nothing on
the money path names it. These pins hold the rule: each negative turns the fence red, today's tree
is green, and a research module outside the money closure may name the home freely."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_research_data_fence", ROOT / "scripts/check_research_data_fence.py"
)
assert _spec is not None and _spec.loader is not None
fence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fence)
RS = fence.RS

ENTRY = "desks/mt5/research/run_gateway_loop.py"
GW = "desks/mt5/mt5desk/gateway.py"
TREE: dict[str, str] = {
    **dict.fromkeys(RS.ENTRY_POINTS, "X = 1\n"),
    ENTRY: "from mt5desk import gateway\n",
    "desks/mt5/mt5desk/__init__.py": "",
    GW: "LOT = 0.1\n",
}
#: every synthetic tree carries this checkout's replay_shadow: check() judges a tree by its own
RS_FILE = "ops/release/replay_shadow.py"
RS_SRC = (ROOT / RS_FILE).read_text("utf-8")
SPAWN = "import subprocess\ndef f(c):\n    subprocess.run(c)\n"  # line 3 is the site


def _pins(*rows: tuple[str, int, str]) -> str:
    sites = [
        {"file": f, "line": n, "sha256": hashlib.sha256(t.strip().encode()).hexdigest(),
         "reason": "read by hand"}
        for f, n, t in rows
    ]  # fmt: skip
    return json.dumps({"sites": sites})


def _check(tmp_path: Path, edits: dict[str, str]) -> dict[str, object]:
    files = {**TREE, RS_FILE: RS_SRC, fence.PINS: _pins(), **edits}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, "utf-8")
    return fence.check(tmp_path)


def _red(tmp_path: Path, edits: dict[str, str], why: str) -> None:
    rep = _check(tmp_path, edits)
    assert rep["ok"] is False
    assert any(why in v for v in rep["violations"]), rep["violations"]  # type: ignore[attr-defined]


# ------------------------------------------------------------------------------- the positives


def test_todays_tree_is_green() -> None:
    rep = fence.check(ROOT)
    assert rep["ok"], rep["violations"]
    assert rep["sites"] == rep["pinned"] and not rep["stale_pins"], rep


def test_the_home_is_outside_every_money_prefix_and_script_dir() -> None:
    probe = fence.HOME + "/x.json"
    assert not probe.startswith(RS.MONEY_PATH) and not probe.startswith(RS.SCRIPT_DIRS)
    assert (ROOT / fence.HOME / "README.md").is_file()


def test_a_clean_synthetic_tree_is_green(tmp_path: Path) -> None:
    assert _check(tmp_path, {})["ok"] is True


def test_a_research_module_outside_the_closure_may_name_the_home(tmp_path: Path) -> None:
    rep = _check(
        tmp_path,
        {"desks/mt5/research/miner.py": "from pathlib import Path\nD = Path('research/data')\n"},
    )
    assert rep["ok"] is True, rep


@pytest.mark.parametrize(
    "src",
    [
        "D = 'docs/research/data/notes.json'\n",  # another research/data, not the home
        "D = 'desks/mt5/data/sleeves.json'\n",  # the money data directory
        "D = 'research'\nE = 'data'\n",  # two bare words
    ],
)
def test_what_does_not_spell_the_home_stays_green(tmp_path: Path, src: str) -> None:
    assert _check(tmp_path, {GW: src})["ok"] is True


def test_a_pinned_site_on_its_unchanged_line_stays_green(tmp_path: Path) -> None:
    rep = _check(tmp_path, {GW: SPAWN, fence.PINS: _pins((GW, 3, "    subprocess.run(c)"))})
    assert rep["ok"] is True, rep


# ------------------------------------------------------------------------------- the negatives


@pytest.mark.parametrize(
    "src",
    [
        # the DATA_DIR shape
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\n"
        "DATA_DIR = ROOT / 'desks/mt5/research/data'\n",
        "def f(root):\n    return root / 'research' / 'data' / 'x.json'\n",
        "D = 'desks\\\\mt5\\\\research\\\\data\\\\x.json'\n",
        # anchored on the module, no literal spelling the whole home
        "from pathlib import Path\nD = Path(__file__).resolve().parents[1] / 'research' / 'data'\n",
    ],
)
def test_a_planted_home_reference_in_a_closure_module_is_red(tmp_path: Path, src: str) -> None:
    _red(tmp_path, {GW: src}, "home")


def test_an_os_path_join_fold_is_red(tmp_path: Path) -> None:
    src = "import os\nD = os.path.join('desks', 'mt5', 'research', 'data')\n"
    _red(tmp_path, {GW: src}, "spells a path into the home")


def test_an_f_string_is_red(tmp_path: Path) -> None:
    src = "def f(name):\n    return f'desks/mt5/research/data/{name}.json'\n"
    _red(tmp_path, {GW: src}, "spells a path into the home")


@pytest.mark.parametrize(
    "src",
    [
        "import glob\nX = glob.glob('desks/mt5/research/data/*.json')\n",
        "from pathlib import Path\nX = list(Path(__file__).parents[3].rglob('*.json'))\n",
    ],
)
def test_a_resolved_listing_into_or_over_the_home_is_red(tmp_path: Path, src: str) -> None:
    """Into the home: a hit. Recursively over an ancestor: a dynamic site, red until pinned."""
    _red(tmp_path, {GW: src}, "list")


@pytest.mark.parametrize(
    "edits",
    [
        {"desks/mt5/scripts/gw.ps1": "Get-Content desks\\mt5\\research\\data\\x.json\n"},
        {GW: "S = 'run.ps1'\n", "tools/run.ps1": "cat ../research/data/x.json\n"},
        {RS.MANIFEST: 'TASK name="MT5-X" runs="tools/x.ps1" lane="money" '
                      'note="desks/mt5/research/data"\n'},
        {RS.MANIFEST: 'TASK name="MT5-X" runs="tools/x.ps1" lane="money"\n',
         "tools/x.ps1": "type research\\data\\x.json\n"},
    ],
)  # fmt: skip
def test_a_money_script_or_money_row_naming_the_home_is_red(
    tmp_path: Path, edits: dict[str, str]
) -> None:
    _red(tmp_path, edits, "names the home")


@pytest.mark.parametrize(
    "src",
    [
        SPAWN,
        "import importlib\ndef f(n):\n    return importlib.import_module(n)\n",
        "import importlib.util\nS = importlib.util.spec_from_file_location('x', 'x.py')\n",
        "import os\ndef f(d):\n    return os.listdir(d)\n",
    ],
)
def test_a_new_dynamic_site_is_red(tmp_path: Path, src: str) -> None:
    _red(tmp_path, {GW: src}, "unpinned dynamic site")


def test_a_pinned_site_whose_line_changed_is_red(tmp_path: Path) -> None:
    pins = _pins((GW, 3, "    subprocess.run(c)"))
    changed = SPAWN.replace("run(c)", "run(c, shell=True)")
    _red(tmp_path, {GW: changed, fence.PINS: pins}, "unpinned dynamic site")


def test_a_pinned_site_that_moved_a_line_is_red(tmp_path: Path) -> None:
    pins = _pins((GW, 3, "    subprocess.run(c)"))
    _red(tmp_path, {GW: "\n" + SPAWN, fence.PINS: pins}, "unpinned dynamic site")


def test_an_unreadable_pin_file_or_module_fails_closed(tmp_path: Path) -> None:
    _red(tmp_path, {fence.PINS: "{not json"}, "cannot be read")
    other = tmp_path / "other"
    _red(other, {GW: "from mt5desk import broken\n", "desks/mt5/mt5desk/broken.py": "def (:\n"},
         "cannot be read or parsed")  # fmt: skip


def test_a_tree_without_the_entry_points_fails_closed(tmp_path: Path) -> None:
    (tmp_path / fence.PINS).parent.mkdir(parents=True)
    (tmp_path / fence.PINS).write_text(_pins(), "utf-8")
    (tmp_path / RS_FILE).parent.mkdir(parents=True)
    (tmp_path / RS_FILE).write_text(RS_SRC, "utf-8")
    rep = fence.check(tmp_path)
    assert rep["ok"] is False and any("entry point" in v for v in rep["violations"])  # type: ignore[attr-defined]


def test_main_prints_one_verdict_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert fence.main([]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("RESEARCH-DATA FENCE PASS")


# ------------------------------------- the programs the money path RUNS (Auditor MF, 2026-11-18)

ROW = 'TASK name="MT5-Prop" runs="desks/mt5/prop/prop_runner.py" lane="money"\n'
PLANT = "from pathlib import Path\nD = Path('desks/mt5/research/data') / 'x.json'\n"


def test_a_money_row_program_outside_the_closure_naming_the_home_is_red(tmp_path: Path) -> None:
    _red(tmp_path, {RS.MANIFEST: ROW, "desks/mt5/prop/prop_runner.py": PLANT},
         "a money-run program")  # fmt: skip


def test_a_money_script_program_outside_the_closure_naming_the_home_is_red(
    tmp_path: Path,
) -> None:
    _red(tmp_path, {"desks/mt5/scripts/tool.py": PLANT}, "a money-run program")


def test_a_module_a_money_run_program_imports_is_scanned_too(tmp_path: Path) -> None:
    _red(
        tmp_path,
        {
            "desks/mt5/scripts/tool.py": "from helpers import reader\n",
            "desks/mt5/helpers/__init__.py": "",
            "desks/mt5/helpers/reader.py": PLANT,
        },
        "a money-run program",
    )


@pytest.mark.parametrize("where", ["desks/mt5/scripts/tool.py", "desks/mt5/prop/prop_runner.py"])
def test_a_new_dynamic_site_in_a_money_run_program_is_red(tmp_path: Path, where: str) -> None:
    _red(tmp_path, {RS.MANIFEST: ROW, where: SPAWN}, "unpinned dynamic site")


def test_root_is_judged_by_its_own_replay_shadow(tmp_path: Path) -> None:
    """--root DIR loads DIR's replay_shadow: an entry point only DIR declares is fenced."""
    extra = "tools/extra_entry.py"
    own = RS_SRC.replace("ENTRY_POINTS = (\n", f"ENTRY_POINTS = (\n    {extra!r},\n", 1)
    assert own != RS_SRC
    edits = {RS_FILE: own, extra: PLANT}
    rep = _check(tmp_path, edits)
    assert rep["ok"] is False and any("home" in v for v in rep["violations"]), rep  # type: ignore[attr-defined]
    assert fence.main(["--root", str(tmp_path)]) == 1
    # this checkout's rules do not see that entry point: the tree's own rules are what fenced it
    assert fence.check(tmp_path, fence.RS)["ok"] is True


def test_a_root_without_replay_shadow_fails_closed(tmp_path: Path) -> None:
    rep = fence.check(tmp_path)
    assert rep["ok"] is False and "cannot be loaded" in rep["violations"][0]


# ------------------- the programs a scanned module RUNS, to a fixed point (Auditor MF, 2026-11-18)

RUN_HELPER = "import subprocess, sys\nsubprocess.run([sys.executable, 'tools/new_helper.py'])\n"
RUN_A = "import subprocess, sys\nsubprocess.run([sys.executable, 'tools/a.py'])\n"
RUN_B = "import runpy\nrunpy.run_path('tools/b.py')\n"
RUN_B_LINE = RUN_B.splitlines()[1]


def test_a_program_a_closure_module_runs_is_scanned_with_its_imports(tmp_path: Path) -> None:
    """closure module -> the .py it runs -> a module that .py imports, naming the home: red."""
    _red(
        tmp_path,
        {
            GW: RUN_HELPER,
            fence.PINS: _pins((GW, 2, RUN_HELPER.splitlines()[1])),
            "tools/new_helper.py": "from libs.foo import load\n",
            "libs/__init__.py": "",
            "libs/foo.py": "def load():\n    return open('desks/mt5/research/data/x.json')\n",
        },
        "libs/foo.py:2",
    )


def test_a_two_hop_chain_of_run_programs_is_scanned(tmp_path: Path) -> None:
    """closure module runs a.py, a.py runs b.py, b.py names the home: red."""
    _red(
        tmp_path,
        {
            GW: RUN_A,
            "tools/a.py": RUN_B,
            "tools/b.py": PLANT,
            fence.PINS: _pins((GW, 2, RUN_A.splitlines()[1]), ("tools/a.py", 2, RUN_B_LINE)),
        },
        "tools/b.py:2",
    )


def test_a_chain_whose_hop_is_unpinned_is_red_on_the_hop(tmp_path: Path) -> None:
    rep = _check(tmp_path, {GW: RUN_A, "tools/a.py": RUN_B, "tools/b.py": "X = 1\n",
                            fence.PINS: _pins((GW, 2, RUN_A.splitlines()[1]))})  # fmt: skip
    assert rep["ok"] is False and rep["scanned"] >= 2, rep
    assert any("tools/a.py:2" in v for v in rep["violations"]), rep  # type: ignore[attr-defined]


def test_a_program_only_named_not_run_is_not_scanned(tmp_path: Path) -> None:
    """A .py named as data (a provenance table hashed, never run) is not a program it runs."""
    rep = _check(tmp_path, {GW: "HASHED = {'h': 'tools/hashed.py'}\n", "tools/hashed.py": PLANT})
    assert rep["ok"] is True, rep
