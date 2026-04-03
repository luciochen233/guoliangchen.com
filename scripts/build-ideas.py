#!/usr/bin/env python3
"""
build-ideas.py — Parse ideas.md and generate individual HTML pages + ideas index.
Run: python3 scripts/build-ideas.py
"""
import re, os, json

SITE_DIR = "/var/www/guoliangchen.com"
IDEAS_DIR = os.path.join(SITE_DIR, "ideas")
IDEAS_MD = "/home/lucio/.openclaw/workspace/ideas.md"
SEARCH_INDEX = os.path.join(SITE_DIR, "search-index.json")

os.makedirs(IDEAS_DIR, exist_ok=True)

def slugify(title):
    title = title.strip().strip('"').strip()
    slug = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', title)
    slug = re.sub(r'[-\s]+', '-', slug).strip('-').lower()
    return slug[:60]

def md_to_html(text):
    """Minimal markdown to HTML converter."""
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

def parse_ideas():
    with open(IDEAS_MD, 'r') as f:
        content = f.read()
    
    pattern = r'^## Idea #(\d+):\s*"?([^"\n]+)"?'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    ideas = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
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
        
        ideas.append({'num': num, 'title': title, 'body': body, 'slug': slugify(title)})
    
    # Assign duplicate suffixes (b, c, d...) for duplicate idea numbers
    seen = {}
    for idea in ideas:
        n = idea['num']
        if n in seen:
            seen[n] += 1
            idea['dup'] = chr(ord('a') + seen[n] - 1)
        else:
            seen[n] = 0
            idea['dup'] = ''
    
    return ideas

def idea_url(idea):
    """Return the URL for an idea."""
    return f"/ideas/{idea['num']}{idea['dup']}-{idea['slug']}.html"

def build_idea_html(idea, all_ideas):
    title = idea['title']
    body = idea['body']
    
    # Prev/next by sorted unique (num, dup) keys
    all_keys = sorted([(x['num'], x.get('dup','')) for x in all_ideas])
    current = (idea['num'], idea.get('dup',''))
    idx = all_keys.index(current)
    
    def get_idea_by_key(key):
        return next(x for x in all_ideas if (x['num'], x.get('dup','')) == key)
    
    prev_link = ''
    next_link = ''
    if idx > 0:
        prev = get_idea_by_key(all_keys[idx-1])
        prev_link = f'<a href="{idea_url(prev)}">← #{prev["num"]}{prev["dup"]}</a>'
    if idx < len(all_keys) - 1:
        nxt = get_idea_by_key(all_keys[idx+1])
        next_link = f'<a href="{idea_url(nxt)}" style="float:right">#{nxt["num"]}{nxt["dup"]} →</a>'
    
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
  <nav><a href="/ideas/">← all ideas</a> <span style="float:right;color:#888">#{idea['num']}{idea['dup']}</span></nav>
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

def build_index_html(ideas):
    sorted_ideas = sorted(ideas, key=lambda x: (x['num'], x.get('dup','')), reverse=True)
    
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
  <title>Ideas — lucioclaw_</title>
  <link rel="stylesheet" href="/assets/style.css">
  <style>
    .ideas-list {{ list-style:none; padding:0; margin:0; }}
    .ideas-list li {{
      display:flex; gap:16px; padding:16px 0;
      border-bottom:1px solid #eee;
    }}
    .idea-num {{ color:#888; font-size:13px; min-width:44px; padding-top:3px; }}
    .idea-title {{ font-size:16px; font-weight:600; margin-bottom:4px; }}
    .idea-title a {{ color:#222; text-decoration:none; }}
    .idea-title a:hover {{ color:#007bff; }}
    .idea-preview {{ font-size:13px; color:#666; }}
  </style>
</head>
<body>
  <nav><a href="/">← home</a></nav>
  <div style="padding:40px; max-width:800px; margin:0 auto">
    <h1 style="margin-bottom:8px">Ideas <span style="font-size:18px; color:#888; font-weight:normal">({len(ideas)} entries)</span></h1>
    <p style="color:#666; margin-bottom:32px">A collection of observations, concepts, tangents. Updated continuously.</p>
    <ul class="ideas-list">
      {''.join(cards)}
    </ul>
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
    print(f"Parsing {IDEAS_MD}...")
    ideas = parse_ideas()
    print(f"Found {len(ideas)} ideas (including duplicates)")
    
    for idea in ideas:
        html = build_idea_html(idea, ideas)
        path = os.path.join(IDEAS_DIR, f"{idea['num']}{idea['dup']}-{idea['slug']}.html")
        with open(path, 'w') as f:
            f.write(html)
        print(f"  wrote /ideas/{idea['num']}{idea['dup']}-{idea['slug']}.html")
    
    with open(os.path.join(IDEAS_DIR, 'index.html'), 'w') as f:
        f.write(build_index_html(ideas))
    print("wrote /ideas/index.html")
    
    update_search_index(ideas)
    print("Done!")

if __name__ == '__main__':
    main()
