"""Nothing reads the seven stale desk-root state files, and the readers that did say UNMEASURED/STALE.

MEASURED 2026-10-06: seven JSON files at the desk root (sync_marker, gateway_state, hunt11,
mech_battery, mech_split, portfolio_projection, regime_state) were committed by the retired Dell
sync on 2026-08-17 and are written by nothing since. Their live writers write under data/ or
reports/. Two readers still read the root copies:

    research/swap_exposure.py   BASE / "portfolio_projection.json"  (the projection writes reports/)
    scripts/check_gold_live.py  BASE / "gateway_state.json" FIRST   (the gateway writes data/)

so the swap verdict was measured on an August book and the arm check answered `armed` from August.

THE LAW, AND WHY IT IS A SCANNER AND NOT A PATTERN (audit of 2026-10-07). The first version
matched `BASE / "<name>.json"` only and every other spelling walked past it: joinpath,
Path(__file__) chains, glob, "/..", concatenation, f-strings, os.path.join, an aliased root and a
bare cwd-relative name. This one inspects EVERY string constant in every tracked .py -- f-string
pieces and concatenation operands included -- that names one of the seven files (or globs for
one), and asks one question: is the directory right before the file name a real directory other
than the desk root? The answer comes from the string itself when it carries a directory, and from
its context otherwise (the left operand of `/` or `+`, the receiver or preceding argument of a
call, the preceding f-string piece), resolving names through their assignments. Anything it cannot
prove qualified is a finding. Prose (a constant containing whitespace) is not a path and is
skipped. .ps1 and .cmd files are scanned textually: a match must follow a data or reports directory and its separator.

ALLOWED, AND ONLY: the STATE_FILES definitions that name the root copies as box state
(libs/ops/release.py, desks/mt5/mt5desk/release_identity.py, Adopt-Release.ps1's $StateFiles).
Test modules are fixtures in temporary directories, not organs, and are not scanned. The LF
writers fixed in PR #255 all write under reports/ or data/ and qualify on their own.
"""
from __future__ import annotations

import ast
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STEMS = ("sync_marker", "gateway_state", "hunt11", "mech_battery", "mech_split",
         "portfolio_projection", "regime_state")
#: The file name, or a glob that can reach it ("gateway_state*", "gateway_state.js?").
NAME_RE = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(STEMS)
                     + r")(?:\.json\b|\.[A-Za-z]*[*?\[]|[*?\[])")
#: Components that are NOT a real directory below the desk root.
ROOT_LIKE = frozenset({"", ".", "..", "mt5", "desks"})
#: An unassigned name (a parameter) qualifies only when it says it is a live directory.
PARAM_DIR_NAMES = frozenset({"data", "reports", "data_dir", "reports_dir", "state_dir"})
#: pathlib navigation is never resolved through an attribute assignment.
NAV_ATTRS = frozenset({"parent", "parents", "anchor", "root"})

#: (file, assignment target) whose string constants are the STATE_FILES declaration itself.
ALLOWED_PY_ASSIGNS = {
    "libs/ops/release.py": "STATE_FILES",
    "desks/mt5/mt5desk/release_identity.py": "STATE_FILES",
}
#: (file, the PowerShell list that mirrors STATE_FILES).
ALLOWED_TEXT_BLOCKS = {"desks/mt5/scripts/Adopt-Release.ps1": r"^\s*\$StateFiles\s*=\s*@\("}


def _norm(s: str) -> str:
    return s.replace("\\", "/")


def _component(path: str) -> str:
    """The last directory component of `path`, normalised; '' when there is none."""
    p = _norm(path).rstrip("/")
    if not p:
        return ""
    last = posixpath.normpath(p).rsplit("/", 1)[-1]
    return "" if any(ch in last for ch in "{}%$<>") else last   # a placeholder is no directory


class _Module:
    def __init__(self, tree: ast.AST) -> None:
        self.parent: dict[ast.AST, ast.AST] = {}
        self.names: dict[str, list[ast.expr]] = {}
        self.attrs: dict[str, list[ast.expr]] = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                self.parent[c] = n
            pairs: list[tuple[ast.expr, ast.expr]] = []
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if (isinstance(t, (ast.Tuple, ast.List)) and isinstance(n.value, (ast.Tuple, ast.List))
                            and len(t.elts) == len(n.value.elts)):
                        pairs += list(zip(t.elts, n.value.elts))
                    else:
                        pairs.append((t, n.value))
            elif isinstance(n, (ast.AnnAssign, ast.NamedExpr)) and n.value is not None:
                pairs.append((n.target, n.value))
            for t, v in pairs:
                if isinstance(t, ast.Name):
                    self.names.setdefault(t.id, []).append(v)
                elif isinstance(t, ast.Attribute):
                    self.attrs.setdefault(t.attr, []).append(v)

    def live(self, e: ast.AST | None, depth: int = 0) -> bool:
        """Does expression `e` end in a real directory below the desk root?"""
        if e is None or depth > 8:
            return False
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            return _component(e.value) not in ROOT_LIKE
        if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Div, ast.Add)):
            return self.live(e.right, depth + 1)
        if isinstance(e, ast.Name):
            vals = self.names.get(e.id)
            if not vals:
                return e.id.lower() in PARAM_DIR_NAMES
            return all(self.live(v, depth + 1) for v in vals)
        if isinstance(e, ast.Attribute) and e.attr not in NAV_ATTRS:
            vals = self.attrs.get(e.attr)
            return bool(vals) and all(self.live(v, depth + 1) for v in vals)
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Attribute) and f.attr in ("joinpath", "join") and e.args:
                return self.live(e.args[-1], depth + 1)
            if isinstance(f, ast.Attribute) and f.attr in ("resolve", "absolute", "expanduser"):
                return self.live(f.value, depth + 1)
            if isinstance(f, ast.Name) and f.id in ("Path", "PurePath", "str") and len(e.args) == 1:
                return self.live(e.args[0], depth + 1)
        if isinstance(e, ast.JoinedStr) and e.values:
            last = e.values[-1]
            if isinstance(last, ast.Constant):
                return _component(str(last.value)) not in ROOT_LIKE
            if isinstance(last, ast.FormattedValue):
                return self.live(last.value, depth + 1)
        return False

    def qualified(self, node: ast.Constant, start: int) -> bool:
        prefix = _norm(str(node.value)[:start])
        if prefix.strip("/"):
            # The string carries its own directory: judge it alone, after resolving "..".
            joined = posixpath.normpath(prefix.rstrip("/") + "/x")
            return _component(joined.rsplit("/", 1)[0] if "/" in joined else "") not in ROOT_LIKE
        par = self.parent.get(node)
        if (isinstance(par, ast.BinOp) and par.right is node
                and isinstance(par.op, (ast.Div, ast.Add))):
            return self.live(par.left)
        if isinstance(par, ast.Call) and node in par.args:
            f, i = par.func, par.args.index(node)
            if isinstance(f, ast.Attribute) and f.attr in ("joinpath", "glob", "rglob") and not i:
                return self.live(f.value)
            # os.path.join(d, name), _at("data", name): the directory is the argument before it
            return bool(i) and self.live(par.args[i - 1])
        if isinstance(par, ast.JoinedStr):
            i = par.values.index(node)
            if i:
                prev = par.values[i - 1]
                if isinstance(prev, ast.FormattedValue):
                    return self.live(prev.value)
                if isinstance(prev, ast.Constant):
                    return _component(str(prev.value)) not in ROOT_LIKE
        return False


def scan_python(src: str, allowed_assign: str | None = None) -> list[tuple[int, str]]:
    """Every string constant naming a stale desk-root file that is not proved to live elsewhere."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [(0, "UNPARSEABLE -- cannot prove it reads no stale desk-root file")]
    mod = _Module(tree)
    allowed: set[int] = set()
    if allowed_assign:
        for n in ast.walk(tree):
            tgt = (n.targets if isinstance(n, ast.Assign)
                   else [n.target] if isinstance(n, ast.AnnAssign) else [])
            if any(isinstance(t, ast.Name) and t.id == allowed_assign for t in tgt):
                allowed |= {id(c) for c in ast.walk(n.value)}  # type: ignore[union-attr]
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)) or id(n) in allowed:
            continue
        if any(ch.isspace() for ch in n.value):
            continue                                   # prose, not a path
        for m in NAME_RE.finditer(n.value):
            if not mod.qualified(n, m.start()):
                out.append((getattr(n, "lineno", 0), n.value))
                break
    return out


_COMMENT = re.compile(r"^\s*(#|rem\b|REM\b|::)")
_LIVE_BEFORE = re.compile(r"(?:^|[\\/\"' $({])(?:data|reports)[\\/]$")


def scan_text(src: str, allowed_block: str | None = None) -> list[tuple[int, str]]:
    """.ps1 / .cmd: a stale name must follow a data or reports directory on its own line."""
    out, inside = [], False
    for i, line in enumerate(src.splitlines(), 1):
        if allowed_block and re.search(allowed_block, line):
            inside = True
        if inside:
            if ")" in line.split("#", 1)[0]:
                inside = False
            continue
        if _COMMENT.match(line):
            continue
        for m in NAME_RE.finditer(line):
            if not _LIVE_BEFORE.search(line[:m.start()]):
                out.append((i, line.strip()))
                break
    return out


def _is_test_module(rel: str) -> bool:
    parts = rel.split("/")
    return "tests" in parts[:-1] or parts[-1].startswith("test_") or parts[-1] == "conftest.py"


def _tracked(*globs: str) -> list[str]:
    res = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--", *globs],
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        pytest.skip("not a git checkout")
    return [f for f in res.stdout.split("\0") if f]


def test_no_tracked_code_reads_a_stale_desk_root_state_file() -> None:
    offenders = []
    for rel in _tracked("*.py"):
        if _is_test_module(rel):
            continue
        try:
            src = (REPO / rel).read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        offenders += [f"{rel}:{ln} {t!r}" for ln, t in scan_python(src, ALLOWED_PY_ASSIGNS.get(rel))]
    for rel in _tracked("*.ps1", "*.cmd"):
        try:
            src = (REPO / rel).read_text("utf-8", errors="replace")
        except OSError:
            continue
        offenders += [f"{rel}:{ln} {t!r}" for ln, t in scan_text(src, ALLOWED_TEXT_BLOCKS.get(rel))]
    assert not offenders, "\n".join(offenders)


def test_the_allowed_sites_are_still_the_state_files_declarations() -> None:
    """An allow-list entry that stops being the declaration must not keep its exemption."""
    for rel, name in ALLOWED_PY_ASSIGNS.items():
        assert re.search(rf"^{name}\b", (REPO / rel).read_text("utf-8"), re.M), rel
        assert scan_python((REPO / rel).read_text("utf-8"), name) == []
    for rel, block in ALLOWED_TEXT_BLOCKS.items():
        assert re.search(block, (REPO / rel).read_text("utf-8", errors="replace"), re.M), rel


#: Every spelling the first version of this law let through, plus the ones a reader would try
#: next. Each must be CAUGHT.
BYPASSES = {
    "div": 'BASE = Path(__file__).resolve().parent.parent\nx = BASE / "gateway_state.json"\n',
    "joinpath": 'BASE = Path(__file__).resolve().parent.parent\nx = BASE.joinpath("regime_state.json")\n',
    "file_chain": 'x = Path(__file__).resolve().parent.parent / "sync_marker.json"\n',
    "parents_index": 'x = Path(__file__).parents[1] / "hunt11.json"\n',
    "glob": 'BASE = Path(__file__).parent.parent\nx = list(BASE.glob("mech_split*"))\n',
    "glob_ext": 'x = list(Path(".").glob("mech_battery.js?"))\n',
    "dotdot_component": 'x = BASE / "data" / ".." / "portfolio_projection.json"\n',
    "dotdot_in_string": 'x = BASE / "data/../portfolio_projection.json"\n',
    "concat": 'x = str(BASE) + "/gateway_state.json"\n',
    "concat_desk": 'x = "desks/mt5/" + "gateway_state.json"\n',
    "fstring": 'x = f"{BASE}/regime_state.json"\n',
    "fstring_dotdot": 'x = f"{BASE}/data/../regime_state.json"\n',
    "format": 'x = "{}/sync_marker.json".format(BASE)\n',
    "percent": 'x = "%s/sync_marker.json" % BASE\n',
    "os_path_join": 'import os\nx = os.path.join(BASE, "hunt11.json")\n',
    "aliased_root": 'BASE = Path(__file__).resolve().parent.parent\nROOT = BASE\nx = ROOT / "mech_battery.json"\n',
    "aliased_data_name": 'DATA = Path(__file__).resolve().parent.parent\nx = DATA / "gateway_state.json"\n',
    "cwd_open": 'x = open("gateway_state.json").read()\n',
    "cwd_path": 'x = Path("portfolio_projection.json").read_text()\n',
    "desk_root_string": 'x = Path("desks/mt5/regime_state.json")\n',
    "with_name": 'x = BASE.with_name("sync_marker.json")\n',
    "list_element": 'FILES = ["gateway_state.json"]\n',
}
#: And the live readers the desk actually writes, which must NOT be flagged.
LIVE = {
    "data_div": 'BASE = Path(__file__).resolve().parent.parent\nx = BASE / "data" / "gateway_state.json"\n',
    "data_alias": 'BASE = Path(__file__).resolve().parent.parent\nDATA = BASE / "data"\nx = DATA / "regime_state.json"\n',
    "reports_string": 'x = open("reports/mech_battery.json", "w")\n',
    "data_string": 'x = "desks/mt5/data/sync_marker.json"\n',
    "join_data": 'import os\nx = os.path.join(BASE, "data", "gateway_state.json")\n',
    "helper_data": 'x = _at("data", "gateway_state.json")\n',
    "fstring_data": 'x = f"{BASE}/data/gateway_state.json"\n',
    "param_data": 'def f(data):\n    return data / "gateway_state.json"\n',
    "subdir_attr": 'class A:\n    def __init__(self, b):\n        self.d = b / "data" / "rt"\n        self.f = self.d / "regime_state.json"\n',
    "prose": 'say("gateway_state.json armed is NOT true")\n',
}


@pytest.mark.parametrize("shape", sorted(BYPASSES))
def test_the_scanner_catches_every_bypass_shape(shape: str) -> None:
    assert scan_python(BYPASSES[shape]), f"{shape} walked past the law"


@pytest.mark.parametrize("shape", sorted(LIVE))
def test_the_scanner_passes_live_readers(shape: str) -> None:
    assert scan_python(LIVE[shape]) == [], f"{shape} is a live reader and was flagged"


@pytest.mark.parametrize("line", [
    '$p = Join-Path $base "gateway_state.json"',
    '$p = "$base\\regime_state.json"',
    'Copy-Item "$desk/sync_marker.json" $dst',
    'type %DESK%\\hunt11.json',
    '$p = Join-Path $base "data\\..\\x" ; Get-Item mech_split.json',
])
def test_the_text_scanner_catches_powershell_and_cmd_reads(line: str) -> None:
    assert scan_text(line)


@pytest.mark.parametrize("line", [
    '$p = Join-Path $base "data\\gateway_state.json"',
    'Copy-Item "$desk/reports/portfolio_projection.json" $dst',
    '# the desk-root gateway_state.json is stale',
    'rem sync_marker.json is written by the hourly cycle',
])
def test_the_text_scanner_passes_live_paths_and_comments(line: str) -> None:
    assert scan_text(line) == []


def test_the_allowed_block_is_exempt_and_nothing_after_it() -> None:
    src = ('$StateFiles = @("desks/mt5/gateway_state.json",\n'
           '                "desks/mt5/sync_marker.json")\n'
           '$x = Join-Path $base "regime_state.json"\n')
    assert [ln for ln, _ in scan_text(src, ALLOWED_TEXT_BLOCKS["desks/mt5/scripts/Adopt-Release.ps1"])] == [3]


def test_the_allowed_assignment_is_exempt_and_nothing_else() -> None:
    src = ('STATE_FILES = frozenset({"desks/mt5/gateway_state.json"})\n'
           'x = Path("desks/mt5/gateway_state.json")\n')
    assert [ln for ln, _ in scan_python(src, "STATE_FILES")] == [2]


# --- swap_exposure ------------------------------------------------------------------------------

@pytest.fixture()
def swap():
    import research.swap_exposure as m
    return m


def test_swap_exposure_reads_the_live_writer_s_path(swap) -> None:
    assert swap.PROJECTION == DESK / "reports" / "portfolio_projection.json"
    src = (DESK / "research" / "portfolio_projection.py").read_text("utf-8")
    assert '(BASE / "reports" / "portfolio_projection.json").write_text(' in src


def test_absent_projection_is_unmeasured_never_the_root_copy(swap, tmp_path: Path) -> None:
    st = swap.projection_status(tmp_path / "reports" / "portfolio_projection.json")
    assert st["state"] == "UNMEASURED" and st["cells"] is None
    assert "absent" in st["why"]


def test_old_projection_is_stale(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text(json.dumps({"rows": [{"name": "x"}]}), encoding="utf-8")
    old = p.stat().st_mtime - swap.PROJECTION_MAX_AGE_S - 60
    os.utime(p, (old, old))
    st = swap.projection_status(p)
    assert st["state"] == "STALE" and st["cells"] is None
    assert st["age_hours"] > swap.PROJECTION_MAX_AGE_S / 3600.0


def test_fresh_projection_is_read(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text(json.dumps({"rows": [{"name": "x"}]}), encoding="utf-8")
    st = swap.projection_status(p)
    assert st["state"] == "OK" and st["cells"] == [{"name": "x"}]


def test_unreadable_projection_is_unmeasured(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text("{not json", encoding="utf-8")
    assert swap.projection_status(p)["state"] == "UNMEASURED"


def test_main_names_the_outcome_in_the_artifact(swap, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(swap, "PROJECTION", tmp_path / "absent.json")
    monkeypatch.setattr(swap, "OUT", tmp_path / "swap_exposure.json")
    monkeypatch.setattr(sys, "argv", ["swap_exposure.py"])
    assert swap.main() == 3
    art = json.loads((tmp_path / "swap_exposure.json").read_text("utf-8"))
    assert art["state"] == "UNMEASURED" and art["rows"] == [] and art["why"]


# --- check_gold_live ----------------------------------------------------------------------------

def _gold_live():
    """Loaded by file: the repo root also has a `scripts` package, so a name import is ambiguous."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "_check_gold_live_under_test", DESK / "scripts" / "check_gold_live.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_check_gold_live_reads_only_the_gateway_s_own_state() -> None:
    m = _gold_live()
    assert m.GATEWAY_STATE == DESK / "data" / "gateway_state.json"


def test_check_gold_live_names_absent_state_unmeasured(tmp_path: Path, monkeypatch,
                                                       capsys) -> None:
    m = _gold_live()
    monkeypatch.setattr(m, "DATA", tmp_path)
    monkeypatch.setattr(m, "GATEWAY_STATE", tmp_path / "gateway_state.json")
    rc = m.main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "armed is UNMEASURED" in out
    assert "gateway_state armed UNMEASURED" in out


# --- the three organs are on a clock, and write LF -------------------------------------------------

HOURLY = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")


@pytest.mark.parametrize(("leg", "script"), [
    ("portfolio_projection", "research/portfolio_projection.py"),
    ("swap_exposure", "research/swap_exposure.py"),
    ("gold_live_check", "scripts/check_gold_live.py"),
])
def test_each_organ_is_an_hourly_leg(leg: str, script: str) -> None:
    from libs.research.layers import LEG_LAYER

    assert f'_costed("{leg}", lambda: _producer(' in HOURLY
    assert f'"{leg}", "{script}"' in HOURLY
    assert f'"{leg}": ' in HOURLY.split("LEG_BUDGET_SEC: dict[str, int] = {", 1)[1].split("\n}", 1)[0]
    assert f'"{leg}"' in HOURLY.split("LEG_DEPARTMENT: dict[str, str] = {", 1)[1].split("\n}", 1)[0]
    assert LEG_LAYER.get(leg), f"{leg} has no layer"
    main_src = HOURLY.split("def main() -> None:", 1)[1]
    assert re.search(rf'"{leg}": \w+', main_src), f"{leg} is not in the marker's result dict"


def test_the_projection_runs_before_the_swap_leg_that_reads_it() -> None:
    assert HOURLY.index('_costed("portfolio_projection"') < HOURLY.index('_costed("swap_exposure"')


def test_gold_live_check_is_a_core_leg_and_swap_verdicts_are_not_failures() -> None:
    sys.path.insert(0, str(DESK / "research"))
    import hourly_cycle as hc

    assert "gold_live_check" in hc.CORE_LEGS
    assert hc.VERDICT_EXITS["swap_exposure"] == (3, 4)


def test_the_projection_s_declared_artifact_is_the_path_swap_exposure_reads(swap) -> None:
    import research.portfolio_projection as pp

    assert pp.OUT == swap.PROJECTION == DESK / "reports" / "portfolio_projection.json"


@pytest.mark.parametrize("rel", ["research/swap_exposure.py", "research/portfolio_projection.py",
                                 "scripts/check_gold_live.py"])
def test_every_json_write_pins_lf(rel: str) -> None:
    calls = [n for n in ast.walk(ast.parse((DESK / rel).read_text("utf-8")))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "write_text"]
    assert calls, rel
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert isinstance(kw.get("newline"), ast.Constant) and kw["newline"].value == "\n", \
            f"{rel}:{c.lineno} writes without newline='\\n' (CRLF on the Windows box)"


def test_gold_live_check_out_writes_its_verdict(tmp_path: Path, monkeypatch, capsys) -> None:
    m = _gold_live()
    monkeypatch.setattr(m, "DATA", tmp_path)
    monkeypatch.setattr(m, "GATEWAY_STATE", tmp_path / "gateway_state.json")
    monkeypatch.setattr(m, "REPORT", tmp_path / "GOLD_LIVE_CHECK.json")
    m.main(["--out"])
    capsys.readouterr()
    raw = (tmp_path / "GOLD_LIVE_CHECK.json").read_bytes()
    assert b"\r" not in raw
    art = json.loads(raw)
    assert art["verdict"] == "NOT_ARMED" and "gateway_state armed UNMEASURED" in art["blocking"]
