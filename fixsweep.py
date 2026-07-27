import pathlib, ast
p = pathlib.Path("scripts/breadth_expander.py")
s = p.read_text("utf-8")
old = '''    user = (f"LENS OF THE DAY -- {lens_name}\n{lens_txt}\n\n"
            f"Name 15-20 sources through THIS lens only. Be specific and checkable. Prefer OBSCURE and NON-ENGLISH over well-known -- the desk already has the obvious ones.")
    print(f"=== BREADTH EXPANDER | lens: {lens_name} | seats: {', '.join(seats)} ===\n")

    rows, n_new = [], 0
    for seat in seats:
        prov = by_model.get(seat)
        if not prov:
            print(f"  {seat}: not in roster, skipped"); continue
        try:
            txt = _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)
        except Exception as e:
            print(f"  {seat}: FAILED ({type(e).__name__} {getattr(e,'code','')})")
            continue
        for ln in txt.splitlines():
'''
new = '''    print(f"=== BREADTH EXPANDER | FULL SWEEP: {len(sweep)} lenses x 3 seats ===\n")
    rows, n_new = [], 0
    for li, (lens_name, lens_txt) in sweep:
        div = [DIVERSITY_POOL[(day + li + k) % len(DIVERSITY_POOL)] for k in (0, 1)]
        seats = [LEAD_SEAT, *div]
        print(f"--- lens {li+1}/{len(sweep)}: {lens_name} | "
              f"{', '.join(x.split('/')[-1] for x in seats)}")
        user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                f"Name 15-20 sources through THIS lens only. Be specific and checkable. "
                f"Prefer OBSCURE and NON-ENGLISH over well-known -- the desk has the obvious ones.")
        pending = []
        for seat in seats:
            prov = by_model.get(seat)
            if not prov:
                continue
            try:
                pending.append((seat, _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)))
            except Exception as e:
                print(f"    {seat.split('/')[-1]}: FAILED "
                      f"({type(e).__name__} {getattr(e, 'code', '')})")
        for seat, txt in pending:
            for ln in txt.splitlines():
'''
assert old in s, "region anchor missing"
s = s.replace(old, new)
p.write_text(s, "utf-8")
ast.parse(s)
print("sweep loop fixed; parses clean")
