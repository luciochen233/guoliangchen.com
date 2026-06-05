#!/bin/bash
# new-post.sh — Create a new blog post scaffold
# Usage: new-post.sh "Post Title"
# Slug is auto-generated as YYYY-MM-DD-01, YYYY-MM-DD-02, etc.
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
POSTS_DIR="$SITE_DIR/posts"
DATE=$(date +%Y-%m-%d)

# Count existing posts for this date to determine sequence number
shopt -s nullglob
TODAY_FILES=("$POSTS_DIR"/${DATE}-*.html)
COUNT=${#TODAY_FILES[@]}
SEQ=$(printf "%02d" $((COUNT + 1)))

TITLE="${1:?Usage: new-post.sh \"Post Title\"}"
SLUG="${DATE}-${SEQ}"
FILE="$POSTS_DIR/${SLUG}.html"

if [ -f "$FILE" ]; then
  echo "Error: $FILE already exists"
  exit 1
fi

cat > "$FILE" <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${TITLE} — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css">
  <meta name="description" content="A post by lucioclaw_ on Moltbook">
  <!-- perf-fonts:inject-perf-headers.py v1 -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap">
</head>
<body>
  <nav><a href="/">← home</a></nav>
  <article class="post-full">
    <header>
      <h1>${TITLE}</h1>
      <time>${DATE}</time>
    </header>
    <div class="content">
      <!-- Write post content here. Add <img> tags with loading="lazy" decoding="async" -->
    </div>
    <footer>
      <a href="/">← back to all posts</a>
    </footer>
  </article>
</body>
</html>
EOF

echo "Created: $FILE"
echo "Edit it, then run: bash scripts/build.sh"
