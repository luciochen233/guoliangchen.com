#!/bin/bash
# deploy.sh — Deploy site after building
# Syncs built assets to live site directory
set -euo pipefail

SITE_DIR="${SITE_DIR:-/var/www/guoliangchen.com}"
BUILD_DIR="${BUILD_DIR:-/tmp/site-build}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

echo "=== Deploying site ==="

# Validate site dir exists
if [ ! -d "$SITE_DIR" ]; then
  echo "Error: Site directory does not exist: $SITE_DIR" >&2
  exit 1
fi

cd "$SITE_DIR"

# Verify all required files exist
REQUIRED_FILES=(
  "index.html"
  "assets/style.css"
  "assets/script.js"
  "search-index.json"
  "data/stats.json"
  "data/moltbook-feed.json"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Warning: Required file missing: $file"
  fi
done

# Update git
if [ -d ".git" ]; then
  echo "Syncing git..."
  git add .
  git commit -m "Site update $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet --no-verify || true
  git pull --rebase --quiet
  git push origin "$DEPLOY_BRANCH" --quiet
fi

# Set proper permissions
find . -type f -exec chmod 644 {} \;
find . -type d -exec chmod 755 {} \;

# Restart web server if needed
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl reload nginx 2>/dev/null || true
fi

echo "=== Deploy complete ==="
echo "Site: http://guoliangchen.com"
echo "Posts: $(ls "$SITE_DIR/posts/"*.html 2>/dev/null | wc -l)"