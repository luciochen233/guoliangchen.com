#!/bin/bash
# build.sh — Full site rebuild
# Generates index.html, search-index.json, and updates stats
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
DATA_DIR="$SITE_DIR/data"

echo "=== Building site ==="

# 1. Update stats if not recently done
[ -f "$DATA_DIR/stats.json" ] || bash "$(dirname "$0")/update-stats.sh"

# 2. Build search index (unified: posts + ideas)
python3 "$(dirname "$0")/rebuild-index.py"

# 3. Generate index.html from components
# (In practice: cat templates/components/*.html with data injected)
# For now, index.html is maintained by the agent — scripts handle data only

# 3.5. Normalize SEO <head> on all post + idea pages (idempotent, safe to re-run)
#      build-ideas.py is run manually elsewhere (it depends on ideas.md having content).
python3 "$(dirname "$0")/rewrite-post-heads.py"
python3 "$(dirname "$0")/rewrite-idea-heads.py"

# 3.6. Inject JSON-LD structured data (Person on homepage, BlogPosting/Article
#      on every post and idea page, CollectionPage on ideas indexes). Idempotent.
python3 "$(dirname "$0")/inject-json-ld.py"

# 3.7. Ensure every HTML page has <link rel="icon" href="/favicon.ico"> in <head>.
#      Idempotent. Runs AFTER 3.5/3.6 because those scripts rewrite <head> blocks
#      and would otherwise drop the favicon link from pages like posts/index.html.
python3 "$(dirname "$0")/inject-favicon.py"

# 3.8. Inject perf <head> resources: preconnect + Google Fonts <link>, defer on
#      script.js, loading=lazy + decoding=async on <img>. Runs AFTER rebuild-index
#      so listing pages (posts/index.html, ideas/{week}/index.html) get fonts too.
python3 "$(dirname "$0")/inject-perf-headers.py"

# 4. Regenerate sitemap.xml from on-disk mtimes (covers posts + ideas + indexes)
python3 "$(dirname "$0")/rebuild-sitemap.py"

echo "=== Build complete ==="
echo "Posts: $(ls "$SITE_DIR/posts/"*.html 2>/dev/null | wc -l)"
echo "Sitemap: $(grep -c '<url>' "$SITE_DIR/sitemap.xml" 2>/dev/null || echo 0) URLs"
echo "Feed entries: $(python3 -c "import json; print(len(json.load(open('$DATA_DIR/moltbook-feed.json'))))" 2>/dev/null || echo 0)"
