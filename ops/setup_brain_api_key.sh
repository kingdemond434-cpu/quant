#!/usr/bin/env bash
# ONE-TIME principal step (Option A, 2026-07-19): put the AI brain on metered API billing.
#
# Before running: create the key in the Anthropic Console (console.anthropic.com >
# API keys), and set a monthly SPEND CAP on the workspace first (start at $50).
#
# Run as quant on the VPS:
#     bash ops/setup_brain_api_key.sh
# then paste the sk-ant-... key, press Enter, then Ctrl-D. The key is written straight
# to a 600-perm gitignored file -- it never appears in chat, logs, or git.
set -euo pipefail
cd /home/quant/quant-platform
umask 077

echo "Paste the Anthropic API key (sk-ant-...), then Enter and Ctrl-D:" >&2
KEY="$(cat | tr -d '[:space:]')"
[ -n "$KEY" ] || { echo "ERROR: no key given" >&2; exit 1; }
case "$KEY" in sk-ant-*) ;; *) echo "ERROR: does not look like an Anthropic key (sk-ant-...)" >&2; exit 1;; esac

printf '%s' "$KEY" > data/secrets/anthropic_api_key
chmod 600 data/secrets/anthropic_api_key
echo "key file written (600): data/secrets/anthropic_api_key" >&2

# Pre-approve the key for Claude Code so headless -p runs never hit the interactive
# "use this API key?" prompt (approval list stores the key's last 20 chars).
SUFFIX="${KEY: -20}"
python3 - "$SUFFIX" <<'PY'
import json, os, sys
p = os.path.expanduser("~/.claude.json")
d = json.load(open(p)) if os.path.exists(p) else {}
r = d.setdefault("customApiKeyResponses", {})
a = r.setdefault("approved", [])
r.setdefault("rejected", [])
if sys.argv[1] not in a:
    a.append(sys.argv[1])
json.dump(d, open(p, "w"), indent=1)
print("claude config: key pre-approved for headless use", file=sys.stderr)
PY

# Retire the old OAuth login (quota-dead old account) so auth is unambiguous.
# Reversible: mv the .retired file back to restore subscription auth.
if [ -f "$HOME/.claude/.credentials.json" ]; then
    mv "$HOME/.claude/.credentials.json" "$HOME/.claude/.credentials.json.retired-$(date -u +%Y%m%d)"
    echo "old OAuth login retired (restore by mv-ing the .retired file back)" >&2
fi

# VERIFY-THEN-CLAIM: prove the brain can authenticate before declaring done.
source ops/brain_env.sh
echo "verifying with a live call..." >&2
OUT="$(claude -p 'Reply with exactly: AUTH-OK' --dangerously-skip-permissions 2>&1 || true)"
echo "$OUT"
if echo "$OUT" | grep -q "AUTH-OK"; then
    echo "=== BRAIN API AUTH VERIFIED -- watchdog will auto-fire the next cycle ===" >&2
else
    echo "=== VERIFY FAILED -- brain NOT authenticated. Check the key / spend cap; the" >&2
    echo "    old login can be restored from ~/.claude/.credentials.json.retired-* ===" >&2
    exit 1
fi
