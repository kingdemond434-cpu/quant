import pathlib, ast
p = pathlib.Path("scripts/claim_verifier.py"); s = p.read_text("utf-8")
old = '''    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "checked": len(f), "failed": len(bad),
                               "by_severity": sev_counts, "claims": f}, indent=1), "utf-8")'''
new = '''    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "checked": len(f), "failed": len(bad),
                               "by_severity": sev_counts, "claims": f}, indent=1), "utf-8")

    # ---- ESCALATION: a reported failure that nobody acts on is the same as no check ------
    # The NAV gap sat in venue_divergence_shadow for FOUR DAYS, widening 36%->176%, while every
    # dashboard read green. Detection without escalation changes nothing, so every CRITICAL/HIGH
    # is written into the two channels that already gate action: the principal pager and the
    # Gate-0 blocker queue. Idempotent -- re-running does not duplicate entries.
    crit = [x for x in bad if x["severity"] in ("CRITICAL", "HIGH")]
    if crit:
        stamp = datetime.now(tz=UTC).date().isoformat()
        pager = DATA / "PRINCIPAL_ACTION.md"
        head = f"CLAIM-VERIFIER {stamp}: {len(crit)} unverified claim(s) -- desk state disputed"
        body = [head, ""]
        for x in crit:
            body.append(f"- [{x['severity']}] {x['claim']}")
            body.append(f"    claims: {x['claimed']}")
            body.append(f"    source: {x['actual']}")
            body.append(f"    consequence: {x['consequence']}")
        txt = "\n".join(body) + "\n"
        prev = pager.read_text("utf-8") if pager.exists() else ""
        if head not in prev:
            pager.write_text(txt + "\n" + prev, "utf-8")
            print(f"  PAGED principal -> {pager.name}")

        gq = ROOT / "docs/GATE0_QUEUE.md"
        if gq.exists():
            g = gq.read_text("utf-8")
            add = ""
            for x in crit:
                key = f"CV-{stamp}-{x['claim'][:28]}"
                if key not in g:
                    add += (f"\n| CV | **{x['claim']}** ({key}) | claims `{x['claimed']}` but "
                            f"source says `{x['actual']}` -- {x['consequence']} | BEFORE any live "
                            f"capital |\n")
            if add:
                gq.write_text(g + add, "utf-8")
                print(f"  QUEUED as Gate-0 blocker(s) -> {gq.name}")
    else:
        print("  no escalation needed -- every claim survived contact with its source")'''
assert old in s, "anchor missing"
s = s.replace(old, new)
p.write_text(s, "utf-8"); ast.parse(s)
print("escalation wired: pager + Gate-0 queue, idempotent")
