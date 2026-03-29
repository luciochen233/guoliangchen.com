#!/bin/bash
# fetch-feed.sh — Fetch Moltbook hot feed to JSON
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

curl -s "https://www.moltbook.com/api/v1/posts?sort=hot&limit=10" \
  -H "Authorization: Bearer $API_KEY" | python3 -c "
import json, sys

data = json.load(sys.stdin)
posts = data.get('posts', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
feed = []
for p in (posts if isinstance(posts, list) else [])[:10]:
    feed.append({
        'title': p.get('title', ''),
        'author': p.get('author', {}).get('name', '') if isinstance(p.get('author'), dict) else str(p.get('author', '')),
        'score': p.get('score', p.get('hot_score', 0)),
        'comments': p.get('comment_count', 0),
        'url': f'https://www.moltbook.com/post/{p.get(\"id\", \"\")}' if p.get('id') else '',
        'preview': (p.get('content', '') or '')[:150],
        'fetched_at': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
    })

json.dump(feed, open('$OUTPUT', 'w'), indent=2)
print(f'Fetched {len(feed)} posts')
"
