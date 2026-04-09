#!/usr/bin/env python3
"""
build-ideas.py — Parse ideas.md and generate individual HTML pages grouped by ISO week.
Each week's ideas go into /ideas/{year}W{week}/ — e.g. /ideas/26W12/1-title.html

Run: python3 scripts/build-ideas.py
"""
import re, os, json
from datetime import datetime

SITE_DIR = "/var/www/guoliangchen.com"
IDEAS_DIR = os.path.join(SITE_DIR, "ideas")
IDEAS_MD = "/home/lucio/.openclaw/workspace/ideas.md"
ARCHIVE_DIR = "/home/lucio/.openclaw/workspace/memory/ideas-archive"
SEARCH_INDEX = os.path.join(SITE_DIR, "search-index.json")

os.makedirs(IDEAS_DIR, exist_ok=True)

def slugify(title):
    title = title.strip().strip('"').strip()
    slug = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', title)
    slug = re.sub(r'[-\s]+', '-', slug).strip('-').lower()
    return slug[:60]

def md_to_html(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    paragraphs = []
    for para in text.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        if para.startswith('• '):
            items = ['<li>' + p[2:].strip() + '</li>' for p in para.split('\n') if p.strip().startswith('• ')]
            if items:
                paragraphs.append('<ul>' + ''.join(items) + '</ul>')
        else:
            paragraphs.append('<p>' + para + '</p>')
    return '\n'.join(paragraphs)

def parse_date(content):
    """Extract date from idea content. Falls back to today if no date found."""
    m = re.search(r'Date:\s*(\d{4}-\d{2}-\d{2})', content)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d')
        except:
            pass
    # Fallback: try to extract from idea number (heuristic)
    # #1 = earliest, increment roughly 1 idea/day from earliest known date
    num_m = re.search(r'^## Idea #(\d+)', content, re.MULTILINE)
    if num_m:
        num = int(num_m.group(1))
        # Heuristic: ideas start ~Jan 2026 (idea #1 ≈ 2026-01-15)
        base = datetime(2026, 1, 15)
        from datetime import timedelta
        estimated = base + timedelta(days=num)
        return estimated
    return datetime.now()

def week_folder(dt):
    """Return year+Wxx folder name for a date, e.g. '26W12'."""
    iso_cal = dt.isocalendar()
    return f"{iso_cal[0] % 100:02d}W{iso_cal[1]:02d}"

def parse_ideas_from_file(filepath):
    """Parse all ideas from a single file."""
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
        # Extract number and optional letter suffix
        num_m = re.match(r'(\d+)([a-z]?)', num_str)
        num = int(num_m.group(1))
        dup = num_m.group(2)
        
        title = m.group(2).strip().strip('"').strip()
        
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        body = content[start:end].strip()
        
        # Clean body
        body_lines = []
        for line in body.split('\n'):
            line = line.strip()
            if not line or line.startswith('## ') or line.startswith('**线索来源') or line.startswith('---'):
                continue
            if line.startswith('- '):
                line = '• ' + line[2:]
            body_lines.append(line)
        body = '\n\n'.join(body_lines)
        
        date = parse_date(content[start:start+200])
        wf = week_folder(date)
        
        ideas.append({
            'num': num, 'dup': dup,
            'title': title,
            'slug': slugify(title),
            'body': body,
            'date': date,
            'week': wf
        })
    
    return ideas

def idea_url(idea):
    return f"/ideas/{idea['week']}/{idea['num']}{idea['dup']}-{idea['slug']}.html"

def build_idea_html(idea, all_ideas):
    title = idea['title']
    body = idea['body']
    
    # Group by week
    by_week = {}
    for x in all_ideas:
        wf = x['week']
        if wf not in by_week:
            by_week[wf] = []
        by_week[wf].append(x)
    
    for wf in by_week:
        by_week[wf].sort(key=lambda x: (x['num'], x.get('dup','')))
    
    sorted_weeks = sorted(by_week.keys(), reverse=True)
    
    # Find prev/next within same week
    week_ideas = by_week.get(idea['week'], [])
    week_ideas_sorted = sorted(week_ideas, key=lambda x: (x['num'], x.get('dup','')))
    
    current_idx = None
    for i, x in enumerate(week_ideas_sorted):
        if x['num'] == idea['num'] and x.get('dup','') == idea.get('dup',''):
            current_idx = i
            break
    
    prev_link = ''
    next_link = ''
    if current_idx is not None:
        if current_idx > 0:
            prev = week_ideas_sorted[current_idx - 1]
            prev_link = f'<a href="{idea_url(prev)}">← #{prev["num"]}{prev["dup"]}</a>'
        if current_idx < len(week_ideas_sorted) - 1:
            nxt = week_ideas_sorted[current_idx + 1]
            next_link = f'<a href="{idea_url(nxt)}" style="float:right">#{nxt["num"]}{nxt["dup"]} →</a>'
    
    # Week nav
    current_week_idx = sorted_weeks.index(idea['week'])
    week_nav_items = []
    for i, wf in enumerate(sorted_weeks):
        if i == current_week_idx:
            week_nav_items.append(f'<span style="color:#888">{wf}</span>')
        else:
            week_nav_items.append(f'<a href="/ideas/{wf}/">{wf}</a>')
    week_nav = ' · '.join(week_nav_items)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Idea #{idea['num']}{idea['dup']}: {title} — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css">
  <meta name="description" content="{title}">
</head>
<body>
  <nav>
    <a href="/">← home</a>
    · <a href="/ideas/">all ideas</a>
    · <a href="/ideas/{idea['week']}/">← {idea['week']}</a>
    <span style="float:right;color:#888">#{idea['num']}{idea['dup']} · {idea['date'].strftime('%Y-%m-%d')}</span>
  </nav>
  <div style="padding:8px 40px;border-bottom:1px solid #eee;font-size:13px;color:#888">
    {week_nav}
  </div>
  <article class="post-full">
    <header>
      <h1>Idea #{idea['num']}{idea['dup']}: {title}</h1>
    </header>
    <div class="content">
      {md_to_html(body)}
    </div>
  </article>
  <nav style="padding:20px 40px; border-top:1px solid #eee; display:flex; justify-content:space-between">
    {prev_link}
    {next_link}
  </nav>
</body>
</html>"""
    return html

def build_week_index(week, ideas):
    """Build the index page for a specific week folder."""
    sorted_ideas = sorted(ideas, key=lambda x: (x['num'], x.get('dup','')))
    
    cards = []
    for idea in sorted_ideas:
        preview = idea['body'][:150].replace('\n', ' ').strip()
        cards.append(f"""<li>
          <div class="idea-num">#{idea['num']}{idea['dup']}</div>
          <div class="idea-body">
            <div class="idea-title"><a href="{idea_url(idea)}">{idea['title']}</a></div>
            <div class="idea-preview">{preview[:100]}…</div>
          </div>
        </li>""")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ideas {week} — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css">
  <style>
    .ideas-list {{ list-style:none; padding:0; margin:0; }}
    .ideas-list li {{ display:flex; gap:16px; padding:16px 0; border-bottom:1px solid #eee; }}
    .idea-num {{ color:#888; font-size:13px; min-width:44px; padding-top:3px; }}
    .idea-title {{ font-size:16px; font-weight:600; margin-bottom:4px; }}
    .idea-title a {{ color:#222; text-decoration:none; }}
    .idea-title a:hover {{ color:#007bff; }}
    .idea-preview {{ font-size:13px; color:#666; }}
  </style>
</head>
<body>
  <nav><a href="/">← home</a> · <a href="/ideas/">all ideas</a></nav>
  <div style="padding:40px; max-width:800px; margin:0 auto">
    <h1 style="margin-bottom:8px">Ideas {week} <span style="font-size:18px; color:#888; font-weight:normal">({len(ideas)} entries)</span></h1>
    <p style="color:#666; margin-bottom:32px">Week of {ideas[0]['date'].strftime('%Y-%m-%d')} — {ideas[-1]['date'].strftime('%Y-%m-%d')}</p>
    <ul class="ideas-list">
      {''.join(cards)}
    </ul>
  </div>
</body>
</html>"""
    return html

def build_main_index(ideas):
    """Build the main /ideas/ index grouped by week."""
    by_week = {}
    for idea in ideas:
        wf = idea['week']
        if wf not in by_week:
            by_week[wf] = []
        by_week[wf].append(idea)
    
    for wf in by_week:
        by_week[wf].sort(key=lambda x: (x['num'], x.get('dup','')))
    
    sorted_weeks = sorted(by_week.keys(), reverse=True)
    
    week_blocks = []
    for wf in sorted_weeks:
        week_ideas = by_week[wf]
        count = len(week_ideas)
        week_blocks.append(f"""<div class="week-block">
  <h2><a href="/ideas/{wf}/">{wf}</a> <span class="count">{count}</span></h2>
  <ul class="week-list">
    {''.join(f'<li><a href="{idea_url(i)}">#{i["num"]}{i["dup"]}: {i["title"]}</a></li>' for i in week_ideas[:5])}
    {f'<li class="more"><a href="/ideas/{wf}/">→ more</a></li>' if count > 5 else ''}
  </ul>
</div>""")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ideas — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css">
  <style>
    .week-block {{ margin-bottom:40px }}
    .week-block h2 {{ font-size:20px; margin-bottom:12px }}
    .week-block h2 a {{ color:#222; text-decoration:none }}
    .week-block h2 a:hover {{ color:#007bff }}
    .count {{ font-size:14px; color:#888; font-weight:normal }}
    .week-list {{ list-style:none; padding:0; margin:0 }}
    .week-list li {{ padding:6px 0; font-size:14px }}
    .week-list li a {{ color:#444; text-decoration:none }}
    .week-list li a:hover {{ color:#007bff }}
    .week-list li.more {{ color:#888; font-style:italic }}
  </style>
</head>
<body>
  <nav><a href="/">← home</a></nav>
  <div style="padding:40px; max-width:800px; margin:0 auto">
    <h1 style="margin-bottom:8px">Ideas <span style="font-size:18px; color:#888; font-weight:normal">({len(ideas)} total)</span></h1>
    <p style="color:#666; margin-bottom:32px">Collected continuously. Grouped by ISO week.</p>
    {''.join(week_blocks)}
  </div>
</body>
</html>"""
    return html

def update_search_index(ideas):
    try:
        with open(SEARCH_INDEX, 'r') as f:
            index = json.load(f)
    except:
        index = []
    
    index = [x for x in index if x.get('type') != 'idea']
    
    for idea in ideas:
        index.append({
            "title": f"#{idea['num']}{idea['dup']}: {idea['title']}",
            "text": idea['body'][:500],
            "url": idea_url(idea),
            "type": "idea",
            "date": "",
            "timestamp": 0
        })
    
    with open(SEARCH_INDEX, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"Search index: {len(index)} entries")

def main():
    print(f"Reading ideas from {IDEAS_MD}...")
    all_ideas = parse_ideas_from_file(IDEAS_MD)
    print(f"Found {len(all_ideas)} ideas in ideas.md")
    
    # Also read archived ideas
    if os.path.isdir(ARCHIVE_DIR):
        for fname in sorted(os.listdir(ARCHIVE_DIR)):
            if fname.endswith('.md'):
                path = os.path.join(ARCHIVE_DIR, fname)
                archived = parse_ideas_from_file(path)
                print(f"  + {len(archived)} ideas from {fname}")
                all_ideas.extend(archived)
    
    # Deduplicate by num+dup
    seen = {}
    unique_ideas = []
    for idea in all_ideas:
        key = (idea['num'], idea.get('dup',''))
        if key not in seen:
            seen[key] = idea
            unique_ideas.append(idea)
        else:
            # Keep the one with more body content
            if len(idea['body']) > len(seen[key]['body']):
                seen[key] = idea
    all_ideas = unique_ideas
    
    print(f"Total unique: {len(all_ideas)}")
    
    # Build week folders
    by_week = {}
    for idea in all_ideas:
        wf = idea['week']
        if wf not in by_week:
            by_week[wf] = []
        by_week[wf].append(idea)
    
    for wf, ideas in by_week.items():
        week_dir = os.path.join(IDEAS_DIR, wf)
        os.makedirs(week_dir, exist_ok=True)
        
        # Build individual pages
        for idea in ideas:
            html = build_idea_html(idea, all_ideas)
            fname = f"{idea['num']}{idea['dup']}-{idea['slug']}.html"
            path = os.path.join(week_dir, fname)
            with open(path, 'w') as f:
                f.write(html)
        
        # Build week index
        index_html = build_week_index(wf, ideas)
        with open(os.path.join(week_dir, 'index.html'), 'w') as f:
            f.write(index_html)
        
        print(f"  wrote {wf}/ ({len(ideas)} ideas)")
    
    # Build main index
    with open(os.path.join(IDEAS_DIR, 'index.html'), 'w') as f:
        f.write(build_main_index(all_ideas))
    print(f"wrote /ideas/index.html")
    
    # Update search
    # Rebuild search index using unified script
    import subprocess
    subprocess.run(["python3", os.path.join(os.path.dirname(__file__), "rebuild-index.py")], check=True)
    print("Done!")

if __name__ == '__main__':
    main()
