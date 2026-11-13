"""The replay-shadow Fusion gateway leg and the signal leg's certified-cell inputs
(ops/release/replay_shadow.py, replay_child.py --gateway / --signals).

Toy trees, so each test runs in seconds and says exactly what it proves:

- an order-changing edit in the gateway's decision path is CAUGHT as a divergence;
- a comment-only edit to the gateway is measured and agrees;
- an edit in a gateway branch no pass reaches stays UNMEASURED;
- an input-dependent family edit is UNMEASURED on bare bars, and CAUGHT once the certified
  cell's inputs are fed through `family_inputs.resolve` from the fixture loaders;
- the same edit, rewritten equivalently, is measured and agrees.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_rs_gateway_leg", ROOT / "ops" / "release" / "replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
sys.modules["_rs_gateway_leg"] = rs
_spec.loader.exec_module(rs)

GATEWAY = "desks/mt5/mt5desk/gateway.py"
ORTHO = "desks/mt5/mt5desk/families_orthogonal.py"

#: A gateway with the real lane's shape: resolve (price the order), cap, run (send it).
TOY_GATEWAY = '''"""A toy gateway: buys every sleeve whose last closed H1 bar closed up."""
import MetaTrader5 as mt5

NEW_RISK_OK = False
_DESK_STALE = None


def realised_q(equity, dist, symbol, info, lot=None):
    return 0.001


def resolve_family_order(st, s, equity, pending=None):
    rates = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 50)
    if rates[-2]["close"] <= rates[-3]["close"]:
        return {"ok": False, "stage": "no_signal", "why": "down"}
    tick = mt5.symbol_info_tick(s["symbol"])
    lot = 0.10
    if equity < 0:
        lot = 0.0
    return {"ok": True, "stage": "ok", "side": 1, "lot": lot, "dist": 0.002, "sym": None,
            "tick": tick, "entry_ref": tick.ask}


def cap_by_heat(sleeves, equity):
    return sleeves, None


def run_family_sleeves(st, sleeves, equity):
    for s in sleeves:
        plan = s.get("pending_order") or {}
        if plan.get("ok"):
            mt5.order_send({"symbol": s["symbol"], "volume": plan["lot"],
                            "type": mt5.ORDER_TYPE_BUY, "price": plan["entry_ref"]})
'''

#: A carry-shaped family that refuses without its recorded swap terms (as family_carry does),
#: and a resolver that hands it its symbol (as family_inputs.resolve does for carry).
TOY_ORTHO = '''def _swap_terms(symbol):
    return None  # the terms store is not on the runner


def family_toy_carry(df, *, symbol=""):
    terms = _swap_terms(symbol)
    if not terms:
        return []
    side = 1 if terms["swap_long"] > terms["swap_short"] else -1
    out = []
    closes = df["close"].tolist()
    for i in range(30, len(closes), 25):
        px = closes[i]
        out.append({"time": str(df.index[i]), "side": side, "stop": px - side * 0.01,
                    "target": px + side * 0.02})
    return out
'''

SUPPORT = {
    "desks/mt5/mt5desk/__init__.py": "",
    "desks/mt5/mt5desk/families.py": (
        "from mt5desk.families_orthogonal import family_toy_carry\n\n\n"
        "def live_family_names():\n    return ['toy_carry']\n\n\n"
        "def get_family_func(name):\n"
        "    return family_toy_carry if name == 'toy_carry' else None\n\n\n"
        "def get_param_grid(name):\n    return {}\n"
    ),
    "desks/mt5/mt5desk/executables.py": (
        "def hunt16_families():\n    return {}\n\n\n"
        "def resolve_family(name):\n"
        "    from mt5desk import families\n\n"
        "    return families.get_family_func(name)\n"
    ),
    "desks/mt5/mt5desk/family_call.py": (
        "def accepts_side(fn):\n    return False\n\n\n"
        "def signals(fn, bars, *, side, params=None):\n"
        "    return list(fn(bars, **(params or {})))\n\n\n"
        "def hunt16_signals(fn, bars, side):\n    return list(fn(bars, side))\n"
    ),
    "desks/mt5/mt5desk/family_inputs.py": (
        "def runtime_call_params(family, params):\n"
        "    return {k: v for k, v in params.items() if k != 'timeframe'}\n\n\n"
        "def resolve(sym, family, params, bars):\n"
        "    return ({'symbol': sym}, 'ok') if family == 'toy_carry' else ({}, 'ok')\n"
    ),
}

CERTS = [{"family": "toy_carry", "symbol": "AUDJPY", "params": {}}]


def _tree(root: Path, gateway: str = TOY_GATEWAY, ortho: str = TOY_ORTHO) -> Path:
    for rel, text in {**SUPPORT, GATEWAY: gateway, ORTHO: ortho}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return root


def _gateway(tmp_path: Path, head_src: str) -> tuple[list[str], set[str], dict[str, str]]:
    base, head = _tree(tmp_path / "base"), _tree(tmp_path / "head", gateway=head_src)
    anchor = rs.gateway_anchor()
    gb = rs.run_gateway(base, [GATEWAY], CERTS, anchor)
    gh = rs.run_gateway(head, [GATEWAY], CERTS, anchor)
    assert "crash" not in gb, gb
    assert "crash" not in gh, gh
    assert any(int(c.get("n") or 0) > 0 for c in gb["calls"].values()), gb["calls"]
    problems, agreed = rs.signal_problems(gb, gh)
    measured, why = rs.signal_measured(base, head, [GATEWAY], gb, gh, agreed)
    return problems, measured, why


def test_an_order_changing_gateway_edit_is_caught(tmp_path: Path) -> None:
    head = TOY_GATEWAY.replace("    lot = 0.10\n", "    lot = 0.20\n")
    assert head != TOY_GATEWAY
    problems, _measured, _why = _gateway(tmp_path, head)
    assert problems, "a doubled lot on every intended order must read as a divergence"
    assert all(p.startswith("signal leg: gateway|") for p in problems)
    assert any("volume" in p or "lot" in p for p in problems), problems


def test_a_comment_only_gateway_edit_is_measured_and_agrees(tmp_path: Path) -> None:
    head = TOY_GATEWAY.replace("    lot = 0.10\n", "    lot = 0.10  # the house lot\n    # why\n")
    problems, measured, why = _gateway(tmp_path, head)
    assert not problems
    assert measured == {GATEWAY}, why


def test_a_gateway_branch_no_pass_reaches_stays_unmeasured(tmp_path: Path) -> None:
    head = TOY_GATEWAY.replace("        lot = 0.0\n", "        lot = 5.0\n")
    assert head != TOY_GATEWAY
    problems, measured, why = _gateway(tmp_path, head)
    assert not problems
    assert GATEWAY not in measured
    assert "never ran" in why[GATEWAY]


def _signal(
    tmp_path: Path, head_ortho: str, certs: list[dict[str, Any]]
) -> tuple[list[str], set[str], dict[str, str]]:
    base, head = _tree(tmp_path / "base"), _tree(tmp_path / "head", ortho=head_ortho)
    sb, sh = rs.run_signals(base, [ORTHO], certs), rs.run_signals(head, [ORTHO], certs)
    assert "crash" not in sb, sb
    assert "crash" not in sh, sh
    problems, agreed = rs.signal_problems(sb, sh)
    measured, why = rs.signal_measured(base, head, [ORTHO], sb, sh, agreed)
    return problems, measured, why


#: An input-dependent edit: the stop of every carry signal moves.
WIDER = TOY_ORTHO.replace('"stop": px - side * 0.01,', '"stop": px - side * 0.03,')


def test_an_input_dependent_family_edit_is_unmeasured_on_bare_bars(tmp_path: Path) -> None:
    """Without its inputs the family refuses, so the edit never ran: UNMEASURED, not clean."""
    problems, measured, why = _signal(tmp_path, WIDER, [])
    assert not problems
    assert ORTHO not in measured
    assert "never ran" in why[ORTHO]


def test_an_input_dependent_family_edit_is_caught_once_inputs_are_fed(tmp_path: Path) -> None:
    """The certified cell's inputs (its symbol, then the swap terms the fixture loader serves)
    make the family trade, and the wider stop is a divergence."""
    problems, _measured, _why = _signal(tmp_path, WIDER, CERTS)
    assert problems, "a wider stop on every carry signal must read as a divergence"
    assert any(p.startswith("signal leg: toy_carry|cert0|AUDJPY") for p in problems), problems
    assert any("stop" in p for p in problems), problems


def test_an_equivalent_input_dependent_rewrite_is_measured(tmp_path: Path) -> None:
    head = TOY_ORTHO.replace('"target": px + side * 0.02}', '"target": side * 0.02 + px}')
    assert head != TOY_ORTHO
    problems, measured, why = _signal(tmp_path, head, CERTS)
    assert not problems
    assert measured == {ORTHO}, why


def test_cert_cells_reads_the_base_books_then_the_fixtures(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (base / "desks/mt5/data").mkdir(parents=True)
    (base / "desks/mt5/data/sleeves.json").write_text(
        '{"sleeves": [{"family": "carry", "symbol": "EURNOK", "params": {"timeframe": "M15"}},'
        ' {"family": "carry", "symbol": "EURNOK", "params": {"timeframe": "M15"}},'
        ' {"family": "x", "symbol": "EURUSD"}]}',
        "utf-8",
    )
    cells = rs.cert_cells(base)
    carry = [c for c in cells if c["family"] == "carry"]
    # the book's one distinct row first, then one fixture to make CERTS_PER_FAMILY
    assert carry[0] == {"family": "carry", "symbol": "EURNOK", "params": {"timeframe": "M15"}}
    assert len(carry) == rs.CERTS_PER_FAMILY
    assert not any(c["family"] == "x" for c in cells)  # a row with no params is no certificate
    assert {"ensemble", "regime_split", "world_macro_state"} <= {c["family"] for c in cells}


#: #1097 audit SF1: a family module the GATEWAY imports a name from. The PR renames only that
#: import, so every changed statement runs at import on both trees and the signal leg agrees;
#: the PR's gateway then cannot import. Comparing only the keys both trees made passed it.
ORTHO_EXPORTING = TOY_ORTHO + "from mt5desk.family_inputs import resolve as _resolve\n"
ORTHO_RENAMED = TOY_ORTHO + "from mt5desk.family_inputs import resolve as _resolve_inputs\n"
GATEWAY_IMPORTING = "from mt5desk.families_orthogonal import _resolve  # noqa: F401\n" + TOY_GATEWAY


def test_a_family_edit_that_breaks_the_gateway_import_fails(
    tmp_path: Path, monkeypatch: Any
) -> None:
    base = _tree(tmp_path / "base", gateway=GATEWAY_IMPORTING, ortho=ORTHO_EXPORTING)
    head = _tree(tmp_path / "head", gateway=GATEWAY_IMPORTING, ortho=ORTHO_RENAMED)

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        return {"steps": [{"hour": 1.0, "intents": [{"side": 1}], "doc": {}}], "imported": []}

    monkeypatch.setattr(rs, "run_tree", fake)
    rep = rs.compare(base, head, [ORTHO], grid=[{"id": "toy", "hours": [1.0]}])
    assert rep["verdict"] == "FAIL", rep["problems"]
    text = "\n".join(rep["problems"])
    assert "signal leg: gateway|import: the PR's tree fails to load what the base ran" in text
    assert "ImportError" in text
    assert "gateway|flat|pass0: the base made this call and the PR's tree never did" in text


def test_signal_problems_compares_the_key_sets() -> None:
    ok = {"digest": "a", "n": 2, "first": []}
    broken = {"error": "ImportError", "detail": "cannot import name '_resolve'"}
    # a call the base made and the PR did not
    problems, _ = rs.signal_problems({"calls": {"p0": ok, "p1": ok}}, {"calls": {"p0": ok}})
    assert problems == ["signal leg: p1: the base made this call and the PR's tree never did"]
    # a load failure only the PR records, even with no base call to miss
    problems, _ = rs.signal_problems({"calls": {}}, {"calls": {"gateway|import": broken}})
    assert len(problems) == 1 and problems[0].startswith("signal leg: gateway|import: the PR's")
    problems, _ = rs.signal_problems(
        {"calls": {"p0": ok}}, {"calls": {"p0": ok, "fam|gateway|resolve": {"error": "None"}}}
    )
    assert len(problems) == 1 and "fam|gateway|resolve" in problems[0]
    # a load failure only the BASE records: UNMEASURED, never a pass and never the PR's fault
    problems, _ = rs.signal_problems({"calls": {"gateway|import": broken}}, {"calls": {"p0": ok}})
    assert problems and all(p.startswith("UNMEASURED signal leg: gateway|import") for p in problems)
    # a call only the PR makes measures nothing and is not a divergence; a base timeout the PR
    # never made is not compared, as a base timeout never is
    problems, agreed = rs.signal_problems(
        {"calls": {"slow": {"timeout": True}}}, {"calls": {"new": ok}}
    )
    assert problems == [] and agreed == set()


#: A gateway whose decision carries every clock it can read: the module's `datetime`, a
#: function-local `import time` (which `_freeze` cannot rebind), and a data file's mtime age.
CLOCKED_GATEWAY = TOY_GATEWAY.replace(
    '    tick = mt5.symbol_info_tick(s["symbol"])\n',
    '    tick = mt5.symbol_info_tick(s["symbol"])\n'
    "    import os\n"
    "    import time as _t\n"
    "    from datetime import datetime\n\n"
    '    flag = os.path.join(os.environ["MT5_DESK_ROOT"], "data", "GENERIC_EXEC_ENABLED")\n'
    "    seen = (datetime.now().isoformat(), _t.time(), _t.time() - os.stat(flag).st_mtime)\n",
).replace('"entry_ref": tick.ask}', '"entry_ref": tick.ask, "seen": repr(seen)}')
CLOCKED_GATEWAY = CLOCKED_GATEWAY.replace(
    '"price": plan["entry_ref"]})', '"price": plan["entry_ref"], "seen": plan["seen"]})'
)


def test_the_gateway_anchor_never_reads_the_wall_clock(tmp_path: Path, monkeypatch: Any) -> None:
    """#1097 audit SF2: the anchor is a fixed weekday inside the sessions, the same whenever CI
    runs, and the child feeds every clock from it, so two runs at different wall-clock times
    give the same digests."""
    import datetime as _dt
    import time as _time

    assert CLOCKED_GATEWAY != TOY_GATEWAY and "seen" in CLOCKED_GATEWAY
    from datetime import UTC, datetime

    pinned = datetime.fromisoformat(rs.gateway_anchor())
    assert pinned.weekday() < 5 and pinned.tzinfo is not None
    assert pinned.utcoffset() == _dt.timedelta(0)
    assert 7 <= pinned.hour < 20  # London and New York, inside the gateway's windows

    def wall_clock(wall: datetime) -> type[datetime]:
        class Wall(datetime):
            @classmethod
            def now(cls, tz: Any = None) -> Any:  # type: ignore[override]
                return wall if tz is not None else wall.replace(tzinfo=None)

        return Wall

    anchors: list[str] = []
    digests: list[dict[str, Any]] = []
    seen: list[str] = []
    walls = (datetime(2027, 7, 3, 3, 47, tzinfo=UTC), datetime(2031, 1, 6, 22, 5, tzinfo=UTC))
    for wall in walls:
        with monkeypatch.context() as m:
            m.setattr(_dt, "datetime", wall_clock(wall))
            m.setattr(_time, "time", wall.timestamp)
            anchors.append(rs.gateway_anchor())
        tree = _tree(tmp_path / f"t{len(anchors)}", gateway=CLOCKED_GATEWAY)
        got = rs.run_gateway(tree, [GATEWAY], CERTS, anchors[-1])
        assert "crash" not in got, got
        digests.append({k: c.get("digest") for k, c in got["calls"].items()})
        seen += [
            p["seen"] for c in got["calls"].values() for p in c.get("first") or [] if "seen" in p
        ]
    assert anchors[0] == anchors[1] == rs.GATEWAY_ANCHOR
    assert digests[0] == digests[1]
    assert any(d for d in digests[0].values()), digests[0]
    # every clock the pass read was the frozen pass instant, and the data file aged zero there
    assert seen
    for s in seen:
        iso, t, age = ast.literal_eval(s)
        assert datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp() == t
        assert age == 0.0
        assert t <= pinned.timestamp()
