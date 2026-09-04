#!/usr/bin/env bash
# Local staging server. Vercel will not export secret values, so those come
# from ~/.claude/secrets.zsh; everything else comes from .env.local.
set -euo pipefail
cd "$(dirname "$0")"
[ -f ~/.claude/secrets.zsh ] && source ~/.claude/secrets.zsh
set -a; [ -f .env.local ] && . ./.env.local; set +a
# .env.local carries "[SENSITIVE]" placeholders for secrets; drop those so the
# real values sourced above survive.
for v in OPENAI_API_KEY ZENABM_TOKEN GTMP; do
  [ "${!v:-}" = "[SENSITIVE]" ] && unset "$v" || true
done
[ -f ~/.claude/secrets.zsh ] && source ~/.claude/secrets.zsh
exec .venv/bin/uvicorn server:app --reload --port 8765 --app-dir backend
