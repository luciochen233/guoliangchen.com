#!/usr/bin/env python3
"""
rebuild-index.py — Unified search index builder.
Always builds the COMPLETE index (posts + ideas) in one pass.
Use this instead of build-search.py or relying on build-ideas.py's partial update.
"""
import json, os, re
from datetime import datetime

SITE_DIR = "/var/www/guoliangchen.com"
POSTS_DIR = os.path.join(SITE_DIR, "posts")
OUTPUT = os.path.join(SITE_DIR, "search-index.json")
IDEAS_MD = "/home/lucio/.openclaw/workspace/ideas.md"
ARCHIVE_DIR = "/home/lucio/.openclaw/workspace/memory/ideas-archive"


def strip_tags(text):
    return re.sub(r'<[^>]+>', '', text)


def extract_title(content):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
    return strip_tags(m.group(1)).strip() if m else ""


def extract_body(content):
    m = re.search(r'<div class="content">(.*?)</div>', content, re.DOTALL)
    if m:
        return strip_tags(m.group(1)).strip()[:500]
    m = re.search(r'</header>(.*?)<footer', content, re.DOTALL)
    return strip_tags(m.group(1)).strip()[:500] if m else ""


def slugify(title):
    title = title.strip().strip('"').strip()
    slug = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', title)
    slug = re.sub(r'[-\s]+', '-', slug).strip('-').lower()
    return slug[:60]


def parse_date_from_idea(content):
    m = re.search(r'Date:\s*(\d{4}-\d{2}-\d{2})', content)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d')
        except:
            pass
    num_m = re.search(r'^## Idea #(\d+)', content, re.MULTILINE)
    if num_m:
        from datetime import timedelta
        num = int(num_m.group(1))
        return datetime(2026, 1, 15) + timedelta(days=num)
    return datetime.now()


def parse_ideas(filepath):
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except:
        return []
    
    pattern = r'^## Idea #(\d+[a-z]?):\s*"?([^"\n]+)"?'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    ideas = []
    for i, m in enumerate(matches):
        num_str = m.group(1)
        num_m = re.match(r'(\d+)([a-z]?)', num_str)
        num = int(num_m.group(1))
        dup = num_m.group(2)
        title = m.group(2).strip().strip('"').strip()
        
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        body = content[start:end].strip()
        
        body_lines = []
        for line in body.split('\n'):
            line = line.strip()
            if not line or line.startswith('## ') or line.startswith('**线索来源') or line.startswith('---'):
                continue
            if line.startswith('- '):
                line = '• ' + line[2:]
            body_lines.append(line)
        body = '\n\n'.join(body_lines)
        
        date = parse_date_from_idea(content[start:start+200])
        iso_cal = date.isocalendar()
        week = f"{iso_cal[0] % 100:02d}W{iso_cal[1]:02d}"
        
        ideas.append({
            'num': num, 'dup': dup, 'title': title,
            'slug': slugify(title), 'body': body,
            'date': date, 'week': week
        })
    
    return ideas


def main():
    global _index
    index = []
    
    # === POSTS ===
    post_count = 0
    if os.path.isdir(POSTS_DIR):
        for fname in sorted(os.listdir(POSTS_DIR)):
            if not fname.endswith(".html") or fname == "index.html":
                continue
            path = os.path.join(POSTS_DIR, fname)
            with open(path, 'r') as f:
                content = f.read()
            date_str = fname[:10]
            try:
                ts = int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())
            except (ValueError, IndexError):
                ts = int(os.path.getmtime(path))
            index.append({
                "title": extract_title(content),
                "text": extract_body(content),
                "url": f"/posts/{fname}",
                "type": "post",
                "date": date_str,
                "timestamp": ts
            })
            post_count += 1
    
    # === IDEAS ===
    idea_count = 0
    all_ideas = parse_ideas(IDEAS_MD)
    if os.path.isdir(ARCHIVE_DIR):
        for fname in sorted(os.listdir(ARCHIVE_DIR)):
            if fname.endswith('.md'):
                all_ideas.extend(parse_ideas(os.path.join(ARCHIVE_DIR, fname)))
    
    # Deduplicate
    seen = {}
    for idea in all_ideas:
        key = (idea['num'], idea.get('dup', ''))
        if key not in seen:
            seen[key] = idea
    
    for idea in seen.values():
        url = f"/ideas/{idea['week']}/{idea['num']}{idea['dup']}-{idea['slug']}.html"
        index.append({
            "title": f"#{idea['num']}{idea['dup']}: {idea['title']}",
            "text": idea['body'][:500],
            "url": url,
            "type": "idea",
            "date": idea['date'].strftime('%Y-%m-%d'),
            "timestamp": int(idea['date'].timestamp())
        })
        idea_count += 1
    
    _index = index
    with open(OUTPUT, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"Search index: {len(index)} entries ({post_count} posts + {idea_count} ideas)")

    # === POSTS INDEX PAGE ===
    generate_posts_index()


def generate_posts_index():
    """Generate /posts/index.html listing all blog posts, newest first."""
    posts = sorted(
        [x for x in _index if x.get('type') == 'post'],
        key=lambda x: x.get('timestamp', 0), reverse=True
    )
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Posts — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css?v=5">
</head>
<body>
  <div class="container" style="padding:60px 20px;max-width:700px;margin:0 auto">
    <h1 style="font-size:28px;margin-bottom:8px">All Posts</h1>
    <p style="color:var(--text-dim);margin-bottom:40px">%d posts</p>
    <ul style="list-style:none;padding:0">
''' % len(posts)
    for p in posts:
        html += f'      <li style="margin-bottom:24px;border-bottom:1px solid var(--border);padding-bottom:16px">\n'
        html += f'        <a href="{p["url"]}" style="font-size:17px;font-weight:600">{p["title"]}</a>\n'
        html += f'        <div style="color:var(--text-dim);font-size:13px;margin-top:4px">{p["date"]}</div>\n'
        html += '      </li>\n'
    html += '''    </ul>
    <div style="margin-top:40px"><a href="/" style="color:var(--text-dim)">← back</a></div>
  </div>
</body>
</html>'''
    out = os.path.join(POSTS_DIR, "index.html")
    with open(out, 'w') as f:
        f.write(html)
    print(f"Posts index: {out} ({len(posts)} posts)")


if __name__ == '__main__':
    main()
