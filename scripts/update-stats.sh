#!/bin/bash
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

POST_COUNT=$(ls "$SITE_DIR/posts/"*.html 2>/dev/null | wc -l)
SITE_START_EPOCH=$(date -d "2026-03-12" +%s)
NOW_EPOCH=$(date +%s)
DAYS_SINCE=$(( (NOW_EPOCH - SITE_START_EPOCH) / 86400 ))
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

TMPPY=$(mktemp)
cat > "$TMPPY" << 'PYEOF'
import json, sys, subprocess

api_key = sys.argv[1]
output_path = sys.argv[2]
post_count = int(sys.argv[3])
days_since = int(sys.argv[4])
updated_at = sys.argv[5]

result = subprocess.run(
    ["curl", "-s", "https://www.moltbook.com/api/v1/home",
     "-H", f"Authorization: Bearer {api_key}"],
    capture_output=True, text=True
)

try:
    profile = json.loads(result.stdout)
except json.JSONDecodeError:
    print("Error: failed to parse profile JSON")
    sys.exit(1)

account = profile.get('your_account', {})

stats = {
    'karma': account.get('karma', 0),
    'followers': account.get('follower_count', 0),
    'following': account.get('following_count', 0),
    'notifications': account.get('unread_notification_count', 0),
    'site_posts': post_count,
    'days_alive': days_since,
    'updated_at': updated_at
}

json.dump(stats, open(output_path, 'w'), indent=2)
print(json.dumps(stats, indent=2))
PYEOF

python3 "$TMPPY" "$API_KEY" "$OUTPUT" "$POST_COUNT" "$DAYS_SINCE" "$UPDATED_AT"
rm -f "$TMPPY"
