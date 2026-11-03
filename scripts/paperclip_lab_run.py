#!/usr/bin/env python3
"""Entry point of the Paperclip lab pass (isolated runner). See libs/research/paperclip_lab/lab.py.

    python scripts/paperclip_lab_run.py --calls 24 --out out/paperclip_bundle.json
    python scripts/paperclip_lab_run.py --role dataset_converter      # Paperclip process adapter
    python scripts/paperclip_lab_run.py --dry                          # no model: material + plan

The token is the workflow's own GITHUB_TOKEN (`models: read`); no other credential is read.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.paperclip_lab import lab  # noqa: E402
from libs.research.paperclip_lab.roles import BY_NAME  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=int(os.environ.get("PAPERCLIP_CALLS", "24")))
    ap.add_argument("--deadline-s", type=float, default=2400.0)
    ap.add_argument("--out", default="out/paperclip_bundle.json")
    ap.add_argument("--role", choices=sorted(BY_NAME))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    if a.dry:
        m = lab.load_material()
        w = lab.role_weights(lab._read_json(lab.ROOT / lab.SCORECARD_REL))
        print(json.dumps({"material": {k: len(v) for k, v in m.items()},
                          "plan": lab.plan(a.calls, w, m)}, indent=1))
        return 0
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("paperclip_lab: no GITHUB_TOKEN (the runner's own models:read token)", file=sys.stderr)
        return 2
    b = lab.run(token=token, n_calls=a.calls, deadline_s=a.deadline_s, out=Path(a.out),
                only_role=a.role)
    calls = sum(b["spend"]["calls_by_role"].values())
    print(f"paperclip_lab: {len(b['rows'])} rows kept, {len(b['red_team_killed'])} red-team "
          f"kills, {calls} calls, models {b['spend']['calls_by_model']}, "
          f"errors {b['spend']['model_errors']}")
    # A pass that reached no model at all is a FAILED pass, so the workflow turns red.
    return 0 if calls else 1


if __name__ == "__main__":
    raise SystemExit(main())
