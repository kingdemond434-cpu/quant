import pathlib, ast
p = pathlib.Path("scripts/breadth_expander.py"); s = p.read_text("utf-8")

# bound per-call time so the whole sweep fits its cadence budget
s = s.replace("def _ask(base_url: str, key: str, model: str, system: str, user: str, timeout: float = 240.0)",
              "def _ask(base_url: str, key: str, model: str, system: str, user: str, timeout: float = 110.0)")

old = '''    rows: list[dict] = []
    for li, (lens_name, lens_txt) in enumerate(LENSES):
        seats = [LEAD_SEAT] + [DIVERSITY_POOL[(day + li + k) % len(DIVERSITY_POOL)] for k in (0, 1)]
        print(f"--- lens {li+1}/{len(LENSES)}: {lens_name} | "
              f"{', '.join(x.split('/')[-1] for x in seats)}")
        user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                "Name 15-20 sources through THIS lens only. Be specific and checkable. "
                "Prefer OBSCURE and NON-ENGLISH over well-known -- the desk has the obvious ones.")
        for seat in seats:
            prov = by_model.get(seat)
            if not prov:
                continue
            try:
                txt = _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)
            except Exception as e:  # noqa: BLE001
                print(f"    {seat.split('/')[-1]}: FAILED "
                      f"({type(e).__name__} {getattr(e, 'code', '')})")
                continue
            got = 0'''
new = '''    # PARALLEL LLM CALLS -- 18 sequential high-effort calls ran 70+ min and were reaped by the
    # watchdog three times; the sweep must fit inside its cadence budget, so fan them out.
    jobs = []
    for li, (lens_name, lens_txt) in enumerate(LENSES):
        seats = [LEAD_SEAT] + [DIVERSITY_POOL[(day + li + k) % len(DIVERSITY_POOL)] for k in (0, 1)]
        user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                "Name 15-20 sources through THIS lens only. Be specific and checkable. "
                "Prefer OBSCURE and NON-ENGLISH over well-known -- the desk has the obvious ones.")
        for seat in seats:
            prov = by_model.get(seat)
            if prov:
                jobs.append((lens_name, seat, prov, user))

    def _run(j):
        lens_name, seat, prov, user = j
        try:
            return lens_name, seat, _ask(prov["base_url"], prov["key"], seat, SYSTEM, user), None
        except Exception as e:  # noqa: BLE001
            return lens_name, seat, "", f"{type(e).__name__} {getattr(e, 'code', '')}"

    print(f"dispatching {len(jobs)} calls in parallel...")
    with ThreadPoolExecutor(max_workers=9) as ex:
        answers = list(ex.map(_run, jobs))

    rows: list[dict] = []
    for lens_name, seat, txt, err in answers:
        if err:
            print(f"    {seat.split('/')[-1]:<22} FAILED ({err})")
            continue
        if True:
            got = 0'''
assert old in s, "anchor missing"
s = s.replace(old, new)
p.write_text(s, "utf-8"); ast.parse(s); print("parallelized; parses clean")
