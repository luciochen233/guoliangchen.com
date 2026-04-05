#!/usr/bin/env python3
# build-search.sh — Build client-side search index from posts + memory
import json, os, re, html as htmlmod
from datetime import datetime

SITE_DIR = "/var/www/guoliangchen.com"
POSTS_DIR = os.path.join(SITE_DIR, "posts")
OUTPUT = os.path.join(SITE_DIR, "search-index.json")

def strip_tags(text):
    return re.sub(r'<[^>]+>', '', text)

def extract_title(content):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
    return strip_tags(m.group(1)).strip() if m else ""

def extract_body(content):
    m = re.search(r'<div class="content">(.*?)</div>', content, re.DOTALL)
    if m:
        return strip_tags(m.group(1)).strip()[:500]
    # Fallback: get everything between header and footer
    m = re.search(r'</header>(.*?)<footer', content, re.DOTALL)
    return strip_tags(m.group(1)).strip()[:500] if m else ""

index = []

# Index blog posts
if os.path.isdir(POSTS_DIR):
    for fname in sorted(os.listdir(POSTS_DIR)):
        if not fname.endswith(".html") or fname == "index.html":
            continue
        path = os.path.join(POSTS_DIR, fname)
        mtime = os.path.getmtime(path)
        with open(path, 'r') as f:
            content = f.read()
        # Derive timestamp from filename date (YYYY-MM-DD), not mtime
        date_str = fname[:10]
        try:
            ts = int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())
        except (ValueError, IndexError):
            ts = int(mtime)
        index.append({
            "title": extract_title(content),
            "text": extract_body(content),
            "url": f"/posts/{fname}",
            "type": "post",
            "date": date_str,
            "timestamp": ts
        })

# Write index
with open(OUTPUT, 'w') as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

print(f"Search index: {len(index)} entries")
