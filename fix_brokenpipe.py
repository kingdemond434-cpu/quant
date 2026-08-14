#!/usr/bin/env python3
"""Fix BrokenPipeError in run_paper_sleeve_spawner.py"""

import re

with open('/home/quant/quant-platform/scripts/run_paper_sleeve_spawner.py', 'r') as f:
    content = f.read()

old = '''def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out, rc = run(_ROOT)
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        print(f"paper-sleeve spawner (R0102): {out['status']} -- "
              f"cohort {out['cohort'].get('m_concurrent')}/{out['cohort'].get('cap')}, "
              f"{len(out.get('queued', []))} queued, "
              f"{len(out.get('spawned', []))} spawned all-time")
        if out.get("why"):
            print(f"  {out['why']}")
        for q in out.get("queued", [])[:6]:
            print(f"  QUEUED {q['name']} (since {str(q['ts'])[:10]}) -- {q['reason'][:90]}")
    return rc'''

new = '''def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out, rc = run(_ROOT)
    try:
        if args.json:
            print(json.dumps(out, indent=1, default=str))
        else:
            print(f"paper-sleeve spawner (R0102): {out['status']} -- "
                  f"cohort {out['cohort'].get('m_concurrent')}/{out['cohort'].get('cap')}, "
                  f"{len(out.get('queued', []))} queued, "
                  f"{len(out.get('spawned', []))} spawned all-time")
            if out.get("why"):
                print(f"  {out['why']}")
            for q in out.get("queued", [])[:6]:
                print(f"  QUEUED {q['name']} (since {str(q['ts'])[:10]}) -- {q['reason'][:90]}")
    except BrokenPipeError:
        # Pipe closed (e.g., `head`, `less`) - exit cleanly
        sys.exit(0)
    return rc'''

if old in content:
    content = content.replace(old, new)
    with open('/home/quant/quant-platform/scripts/run_paper_sleeve_spawner.py', 'w') as f:
        f.write(content)
    print("SUCCESS: BrokenPipeError fix applied")
else:
    print("ERROR: Could not find target code")
    idx = content.find("def main()")
    if idx >= 0:
        print("Found at:", idx)
        print(content[idx:idx+500])
    else:
        print("NOT FOUND at all")