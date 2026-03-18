#!/bin/bash
# new-post.sh — Create a new blog post scaffold
# Usage: new-post.sh "Post Title" [slug]
set -euo pipefail

SITE_DIR="/var/www/guoliangchen.com"
POSTS_DIR="$SITE_DIR/posts"
DATE=$(date +%Y-%m-%d)

TITLE="${1:?Usage: new-post.sh \"Post Title\" [slug]}"
SLUG="${2:-$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')}"
FILE="$POSTS_DIR/${DATE}-${SLUG}.html"

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
</head>
<body>
  <nav><a href="/">← home</a></nav>
  <article class="post-full">
    <header>
      <h1>${TITLE}</h1>
      <time>${DATE}</time>
    </header>
    <div class="content">
      <!-- Write post content here -->
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
