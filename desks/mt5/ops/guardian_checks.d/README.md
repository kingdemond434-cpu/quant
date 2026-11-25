# Same-day guardian checks

Every miss the 6h pass or the brain finds becomes a check the same day: drop one JSON file here.
`libs/ops/guardian_sweep.py` runs every file on each 15-minute guardian pass. No code change is needed.

    {"id": "short_id", "path": "repo-relative path", "max_age_h": 26, "min_bytes": 200,
     "json_key": "optional top-level key", "why": "the miss this catches, with its date"}

A check fails when its file is missing, older than max_age_h, smaller than min_bytes, or
(when json_key is set) is not JSON or lacks that key. A secrets path is always refused.
