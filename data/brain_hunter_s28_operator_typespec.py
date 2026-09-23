"""BRAIN HUNTER s28 -- the operator set WITH ITS TYPE ALGEBRA, from a reimplementation.

Source: AshSwing/FastPlus src/operator.rs (MIT, github, public; mined as TEXT, never installed
-- the supply-chain rule). A Rust/PyO3 parser for WorldQuant's Fast Expression Language whose
registry declares, for all 108 Expert-scope operators: positional argument TYPES, keyword
arguments with defaults, arity (-1 = n-ary), RETURN TYPE, and the platform's own description.

WHY THIS IS THE HIGH-YIELD NODE (the brief's recursive-expansion rule): the official docs list
operators; a reimplementation had to encode the SEMANTICS the docs assume. The thing the desk
did not have is not the operator names -- it is the TYPE ALGEBRA over them:

    Matrix (date x symbol panel) | Vector | Group (a labelling) | Boolean/Number constants

and the rule that a signal must be Matrix-compatible. `group_rank(x, industry)` is
(Matrix, Group) -> Matrix; `densify` is Group -> Group; `vec_avg` is Vector -> Matrix. The
desk's generator has NO type discipline, so it can emit expressions that are not merely bad
alphas but MALFORMED, and it only discovers this by evaluating them.

Output: data/brain_hunter_s28_operator_typespec.json + the diff against the desk's own
data/brain_operator_catalogue.json.
"""
from __future__ import annotations

import json
import pathlib
import re
import tempfile
import urllib.request
from collections.abc import Iterator
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_URL = ("https://raw.githubusercontent.com/AshSwing/FastPlus/dev/src/operator.rs")
SRC = pathlib.Path(tempfile.gettempdir()) / "fp_operator.rs"
OUT = ROOT / "data/brain_hunter_s28_operator_typespec.json"
DESK = ROOT / "data/brain_operator_catalogue.json"

BLOCK = re.compile(
    r"define_operator!\(\s*[A-Z0-9_]+,\s*"
    r'"(?P<name>[a-z0-9_]+)",\s*'
    r"\[(?P<pos>[^\]]*)\],\s*"
    r"\{(?P<kw>.*?)\},\s*"
    r"(?P<nary>-?\d+),\s*"
    r"(?P<ret>[A-Za-z]+),\s*"
    r'"(?P<desc>(?:[^"\\]|\\.)*)"\s*\)',
    re.S,
)
KW = re.compile(r'"(?P<n>[a-z0-9_]+)"\s*=>\s*\((?P<t>[A-Za-z]+),\s*(?P<d>[^)]*?)\)\s*,?', re.S)


def main() -> None:
    if not SRC.exists():                       # fetch once, cache; TEXT only, never executed
        with urllib.request.urlopen(SRC_URL, timeout=30) as r:
            SRC.write_bytes(r.read())
    text = SRC.read_text()
    ops: dict[str, dict[str, Any]] = {}
    for m in BLOCK.finditer(text):
        kws = {k.group("n"): {"type": k.group("t"), "default": k.group("d").strip()}
               for k in KW.finditer(m.group("kw"))}
        ops[m.group("name")] = {
            "pos_arg_types": [p.strip() for p in m.group("pos").split(",") if p.strip()],
            "kwargs": kws,
            "arity": int(m.group("nary")),
            "return_type": m.group("ret"),
            "description": m.group("desc").replace("\\n", " ").strip(),
        }

    desk_raw = json.loads(DESK.read_text())
    def walk(o: Any) -> Iterator[str]:
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    yield from walk(v)
                if re.fullmatch(r"[a-z][a-z0-9_]{1,30}", str(k)):
                    yield str(k)
                if k in ("name", "operator") and isinstance(v, str):
                    yield v
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
        elif isinstance(o, str):
            yield o
    desk_tokens = set(walk(desk_raw))
    known = sorted(n for n in ops if n in desk_tokens)
    missing = sorted(n for n in ops if n not in desk_tokens)

    by_sig: dict[str, list[str]] = {}
    for n, o in ops.items():
        pos: list[str] = list(o['pos_arg_types'])
        sig = f"({','.join(pos) or '-'})->{o['return_type']}"
        by_sig.setdefault(sig, []).append(n)

    group_consuming = sorted(n for n, o in ops.items() if "Group" in o["pos_arg_types"])
    out = {
        "session": "brain_hunter_s28", "date": "2026-08-29",
        "source": {"repo": "AshSwing/FastPlus", "path": "src/operator.rs", "branch": "dev",
                   "licence": "MIT", "access": "public raw.githubusercontent",
                   "handling": "mined as TEXT; nothing installed or executed (supply-chain rule)"},
        "derives_from": "docs/research/prospector_coverage.md s27 next-ground item 3",
        "operators_parsed": len(ops),
        "readme_claim": "108 operators in Expert scope",
        "signatures": {k: sorted(v) for k, v in sorted(by_sig.items(), key=lambda kv: -len(kv[1]))},
        "group_consuming_operators": group_consuming,
        "already_named_in_desk_catalogue": known,
        "not_named_in_desk_catalogue": missing,
        "operators": ops,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print("parsed", len(ops), "| desk-known", len(known), "| desk-unknown", len(missing))
    print("signature classes:", len(by_sig))
    for k, v in sorted(by_sig.items(), key=lambda kv: -len(kv[1]))[:12]:
        print(" ", str(len(v)).rjust(3), k)
    print("group-consuming:", group_consuming)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
