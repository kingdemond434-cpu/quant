#!/usr/bin/env bash
# Principal step (Option B): install the `claude setup-token` OAuth token for the brain.
#
# Run:   bash ops/setup_brain_token.sh
# When prompted, paste ONLY the token (the long sk-ant-oat01-... string from
# `claude setup-token`), then press Enter. Nothing else -- no commands, no quotes.
# The script validates the paste, rejects anything that is not a token, writes it
# to a 600-perm gitignored file, and verifies auth with a live call.
set -euo pipefail
cd /home/quant/quant-platform
umask 077

printf '\nPaste the token (sk-ant-oat01-...) and press Enter:\n> ' >&2
IFS= read -r RAW
KEY="$(printf '%s' "$RAW" | tr -d '[:space:]')"

if [ -z "$KEY" ]; then
    echo "ERROR: empty input. Run again and paste the token." >&2; exit 1
fi
case "$KEY" in
    sk-ant-*) ;;
    *) echo "ERROR: that is not a token (must start with sk-ant-). You pasted something else -- run again and paste ONLY the token line from claude setup-token." >&2; exit 1;;
esac
if [ "${#KEY}" -lt 40 ]; then
    echo "ERROR: too short to be a token (${#KEY} chars). Paste the FULL sk-ant-oat01-... string." >&2; exit 1
fi

printf '%s' "$KEY" > data/secrets/claude_oauth_token
chmod 600 data/secrets/claude_oauth_token
echo "token written (600): data/secrets/claude_oauth_token (${#KEY} chars)" >&2

echo "verifying with a live call..." >&2
source ops/brain_env.sh
OUT="$(claude -p 'Reply with exactly: AUTH-OK' --dangerously-skip-permissions 2>&1 || true)"
echo "$OUT"
if echo "$OUT" | grep -q "AUTH-OK"; then
    echo "=== BRAIN AUTH VERIFIED (new account) -- watchdog will auto-fire the next cycle ===" >&2
    # retire the stale old-account login so no script can silently use it again
    if [ -f "$HOME/.claude/.credentials.json" ]; then
        mv "$HOME/.claude/.credentials.json" "$HOME/.claude/.credentials.json.retired-$(date -u +%Y%m%d)"
        echo "old-account stored login retired (reversible: mv the .retired file back)" >&2
    fi
elif echo "$OUT" | grep -qi "limit"; then
    echo "=== TOKEN OK BUT THIS ACCOUNT IS ALSO AT ITS LIMIT -- upgrade it to Max at claude.ai" >&2
    echo "    Billing, then re-run just the verify:  source ops/brain_env.sh && claude -p 'say AUTH-OK' ===" >&2
    exit 1
else
    echo "=== VERIFY FAILED (not a limit issue) -- token may be invalid/revoked. Re-run" >&2
    echo "    claude setup-token, then run this script again with the fresh token. ===" >&2
    exit 1
fi
