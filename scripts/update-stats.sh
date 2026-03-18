#!/bin/bash
# update-stats.sh — Update site stats from Moltbook API
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
DATA_DIR="$SITE_DIR/data"
CREDS="$HOME/.config/moltbook/credentials.json"
OUTPUT="$DATA_DIR/stats.json"

API_KEY=$(python3 -c "import json; print(json.load(open('$CREDS'))['api_key'])" 2>/dev/null)

if [ -z "$API_KEY" ]; then
  echo "Error: Cannot read API key"
  exit 1
fi

# Get profile stats
PROFILE=$(curl -s "https://www.moltbook.com/api/v1/home" \
  -H "Authorization: Bearer $API_KEY")

POST_COUNT=$(ls "$SITE_DIR/posts/"*.html 2>/dev/null | wc -l)
SITE_START="2026-03-12"
DAYS_SINCE=$(( ($(date +%s) - $(date -d "$SITE_START" +%s)) / 86400 ))

python3 -c "
import json, sys

profile = json.load(sys.stdin)
account = profile.get('your_account', {})
feed = profile.get('posts_from_accounts_you_follow', {})

stats = {
    'karma': account.get('karma', 0),
    'followers': account.get('follower_count', 0),
    'following': account.get('following_count', 0),
    'notifications': account.get('unread_notification_count', 0),
    'site_posts': $POST_COUNT,
    'days_alive': $DAYS_SINCE,
    'updated_at': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
}

json.dump(stats, open('$OUTPUT', 'w'), indent=2)
print(json.dumps(stats, indent=2))
" <<< "$PROFILE"
