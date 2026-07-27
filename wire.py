import pathlib
p = pathlib.Path("scripts/daily_research_cycle.py"); s = p.read_text()
if "breadth_expander" in s:
    print("already wired")
else:
    anchor = '    ("stablecoin_supply", "scripts/collect_stablecoin_supply.py", 120),  # broad stablecoin-supply momentum clock\n'
    add = ('    ("breadth_expander", "scripts/breadth_expander.py", 420),  # external-LLM breadth scout (Stage-A only)\n'
           '    ("signal_halflife",  "scripts/signal_halflife.py", 180),  # signal ageing/decay tracker\n')
    if anchor not in s:
        raise SystemExit("anchor missing -- NOT wiring (no blind edits)")
    p.write_text(s.replace(anchor, anchor + add))
    print("wired: breadth_expander + signal_halflife into daily cycle")
import ast; ast.parse(pathlib.Path("scripts/daily_research_cycle.py").read_text()); print("daily cycle parses OK")
