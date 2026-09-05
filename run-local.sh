#!/usr/bin/env bash
# Local staging server. Vercel will not export secret values, so those come
# from ~/.claude/secrets.zsh; everything else comes from .env.local.
set -euo pipefail
cd "$(dirname "$0")"
[ -f ~/.claude/secrets.zsh ] && source ~/.claude/secrets.zsh
set -a; [ -f .env.local ] && . ./.env.local; set +a
# .env.local carries "[SENSITIVE]" placeholders for secrets; drop those so the
# real values sourced above survive.
for v in OPENAI_API_KEY ZENABM_TOKEN GTMP GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET; do
  [ "${!v:-}" = "[SENSITIVE]" ] && unset "$v" || true
done
[ -f ~/.claude/secrets.zsh ] && source ~/.claude/secrets.zsh
# The Connect flow is enabled locally so it can be tested before it is
# offered publicly.
export GSC_CONNECT_ENABLED=1

# Say plainly when a credential is missing. A placeholder reaching Google
# returns "invalid_client", which points nowhere near the real cause.
for v in OPENAI_API_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET; do
  case "${!v:-}" in
    ""|"[SENSITIVE]") echo "warning: $v is not set locally; features using it will fail" >&2 ;;
  esac
done

exec .venv/bin/uvicorn server:app --reload --port 8765 --app-dir backend
