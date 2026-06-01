#!/bin/bash
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
DATA_DIR="$SITE_DIR/data"
CREDS="$HOME/.config/moltbook/credentials.json"
OUTPUT="$DATA_DIR/moltbook-feed.json"

API_KEY=$(python3 -c "import json; print(json.load(open('$CREDS'))['api_key'])" 2>/dev/null)

if [ -z "$API_KEY" ]; then
  echo "Error: Cannot read API key from $CREDS"
  exit 1
fi

TMPPY=$(mktemp)
FETCHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat > "$TMPPY" << 'PYEOF'
import json, sys, subprocess

api_key = sys.argv[1]
output_path = sys.argv[2]
fetched_at = sys.argv[3]

# Try /api/v1/feed first (personalized feed)
result = subprocess.run(
    ["curl", "-s", "https://www.moltbook.com/api/v1/feed",
     "-H", f"Authorization: Bearer {api_key}"],
    capture_output=True, text=True
)

feed = []
try:
    data = json.loads(result.stdout)
    if data.get('success') and 'posts' in data:
        for p in data['posts'][:10]:
            feed.append({
                'title': p.get('title', ''),
                'author': p.get('author', {}).get('name', '') if isinstance(p.get('author'), dict) else str(p.get('author', '')),
                'score': p.get('score', p.get('hot_score', 0)),
                'comments': p.get('comment_count', 0),
                'url': f'https://www.moltbook.com/post/{p.get("id", "")}' if p.get('id') else '',
                'preview': (p.get('content', '') or '')[:150],
                'fetched_at': fetched_at
            })
except (json.JSONDecodeError, KeyError):
    pass

json.dump(feed, open(output_path, 'w'), indent=2)
print(f"Fetched {len(feed)} posts")
PYEOF

python3 "$TMPPY" "$API_KEY" "$OUTPUT" "$FETCHED_AT"
rm -f "$TMPPY"
