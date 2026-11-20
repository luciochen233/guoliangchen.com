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
import json, os, sys, subprocess

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

# /api/v1/home does NOT return follower_count / following_count
# (only karma + unread_notification_count). Pull those from /api/v1/agents/me.
# Note: /api/v1/agents/me wraps the profile under {"success":true,"agent":{...}}.
result_me = subprocess.run(
    ["curl", "-s", "https://www.moltbook.com/api/v1/agents/me",
     "-H", f"Authorization: Bearer {api_key}"],
    capture_output=True, text=True
)
try:
    me = json.loads(result_me.stdout).get('agent', {})
except (json.JSONDecodeError, AttributeError):
    me = {}

account = profile.get('your_account', {})

stats = {
    'karma': account.get('karma', 0),
    'followers': me.get('follower_count', 0),
    'following': me.get('following_count', 0),
    'notifications': account.get('unread_notification_count', 0),
    'site_posts': post_count,
    'days_alive': days_since,
    'updated_at': updated_at
}

# Publish atomically: write to a temp file in the same directory, then rename.
# A reader (the homepage JS, a crawler) can otherwise catch the file between
# truncate and write and parse a truncated document.
mode = os.stat(output_path).st_mode & 0o777 if os.path.exists(output_path) else 0o664
tmp_path = output_path + '.tmp'
with open(tmp_path, 'w') as fh:
    json.dump(stats, fh, indent=2)
    fh.flush()
    os.fsync(fh.fileno())
os.chmod(tmp_path, mode)
os.replace(tmp_path, output_path)
print(json.dumps(stats, indent=2))
PYEOF

python3 "$TMPPY" "$API_KEY" "$OUTPUT" "$POST_COUNT" "$DAYS_SINCE" "$UPDATED_AT"
rm -f "$TMPPY"

# Keep the homepage's shipped stat bar equal to stats.json. A no-JS visitor or a
# crawler reads the HTML, not the JS that overwrites it, and that fetch ends in
# `.catch(() => {})` — so a failure would leave stale numbers in place silently.
# Non-fatal by design: this must never fail the hourly stats refresh.
SITE_DIR="$SITE_DIR" python3 "$SITE_DIR/scripts/sync-index-stats.py" || echo "warn: index stat sync failed (non-fatal)"
