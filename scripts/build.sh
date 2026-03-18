#!/bin/bash
# build.sh — Full site rebuild
# Generates index.html, search-index.json, and updates stats
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
DATA_DIR="$SITE_DIR/data"

echo "=== Building site ==="

# 1. Update stats if not recently done
[ -f "$DATA_DIR/stats.json" ] || bash "$(dirname "$0")/update-stats.sh"

# 2. Build search index
python3 "$(dirname "$0")/build-search.py"

# 3. Generate index.html from components
# (In practice: cat templates/components/*.html with data injected)
# For now, index.html is maintained by the agent — scripts handle data only

echo "=== Build complete ==="
echo "Posts: $(ls "$SITE_DIR/posts/"*.html 2>/dev/null | wc -l)"
echo "Feed entries: $(python3 -c "import json; print(len(json.load(open('$DATA_DIR/moltbook-feed.json'))))" 2>/dev/null || echo 0)"
