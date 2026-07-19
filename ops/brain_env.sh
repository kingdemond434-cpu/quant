# Shared brain auth environment -- sourced by EVERY claude-invoking script
# (run_cro_ai.sh + all 4 digger scripts). See ledgers #101/#102.
#
# Auth precedence (first file found wins; both 600-perm, gitignored, read at spawn
# time -- NEVER systemd Environment=, which is /proc-visible):
#   1. data/secrets/anthropic_api_key      -> ANTHROPIC_API_KEY (Option A, DORMANT
#      escape hatch: metered Console billing if the Max pool ever starves the brain)
#   2. data/secrets/claude_oauth_token     -> CLAUDE_CODE_OAUTH_TOKEN (Option B,
#      CURRENT: `claude setup-token` output from the principal's Max account.
#      setup-token does NOT update ~/.claude/.credentials.json -- the token only
#      works via this env var, which also outranks any stale stored login)
#   3. neither file -> whatever OAuth login exists in ~/.claude (legacy fallback)
export PATH="$HOME/.local/bin:$PATH"
_BRAIN_KEYFILE="/home/quant/quant-platform/data/secrets/anthropic_api_key"
_BRAIN_TOKENFILE="/home/quant/quant-platform/data/secrets/claude_oauth_token"
if [ -f "$_BRAIN_KEYFILE" ]; then
    ANTHROPIC_API_KEY="$(cat "$_BRAIN_KEYFILE")"
    export ANTHROPIC_API_KEY
elif [ -f "$_BRAIN_TOKENFILE" ]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(tr -d '[:space:]' < "$_BRAIN_TOKENFILE")"
    export CLAUDE_CODE_OAUTH_TOKEN
fi
