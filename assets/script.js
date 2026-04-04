// guoliangchen.com — Shared JS
(function() {
  // Load ideas list
  const ideasList = document.getElementById('ideas-list');
  if (ideasList) {
    fetch('/search-index.json?v=5')
      .then(r => r.json())
      .then(items => {
        const ideas = items.filter(x => x.type === 'idea').slice(0, 5);
        if (ideas.length === 0) {
          ideasList.innerHTML = '<li style="color:#444">No ideas yet</li>';
          return;
        }
        ideasList.innerHTML = ideas.map(i => {
          const m = i.title.match(/^#?(\d+[a-z]?):?\s*(.*)/);
          const num = m ? m[1] : '';
          const title = m ? m[2] : i.title;
          return `<li style="padding:8px 0;border-bottom:1px solid #333">
            <span style="color:#777;font-size:12px;margin-right:8px">#${num}</span>
            <a href="${i.url}" style="color:#e0e0e0;text-decoration:none">${escapeHtml(title)}</a>
          </li>`;
        }).join('');
      })
      .catch(() => {
        ideasList.innerHTML = '<li style="color:#444">Failed to load</li>';
      });
  }

  // Load post list
  const postList = document.getElementById('post-list');
  if (postList) {
    fetch('/search-index.json?v=5')
      .then(r => r.json())
      .then(posts => {
        if (posts.length === 0) {
          postList.innerHTML = '<li style="color:#444">No posts yet</li>';
          return;
        }
        // Only show type=post, newest first (by timestamp)
        const blogPosts = posts.filter(p => p.type === 'post').sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)).slice(0, 10);
        postList.innerHTML = blogPosts.map(p => `
          <li style="padding:8px 0;border-bottom:1px solid #333">
            <span style="color:#777;font-size:12px;margin-right:8px">${p.date}</span>
            <a href="${p.url}" style="color:#e0e0e0;text-decoration:none">${escapeHtml(p.title)}</a>
          </li>
        `).join('');
      })
      .catch(() => {
        postList.innerHTML = '<li style="color:#444">No posts yet</li>';
      });
  }

  // Client-side search
  const searchInput = document.getElementById('search');
  const searchResults = document.getElementById('search-results');

  if (searchInput && searchResults) {
    let index = [];
    fetch('/search-index.json?v=5')
      .then(r => r.json())
      .then(data => { index = data; })
      .catch(() => {});

    searchInput.addEventListener('input', function() {
      const q = this.value.toLowerCase().trim();
      searchResults.innerHTML = '';
      if (q.length < 2) return;

      const results = index.filter(item =>
        item.title.toLowerCase().includes(q) ||
        item.text.toLowerCase().includes(q)
      ).slice(0, 10);

      if (results.length === 0) {
        searchResults.innerHTML = '<li style="color:#444">No results</li>';
        return;
      }

      results.forEach(r => {
        const li = document.createElement('li');
        li.innerHTML = `<a href="${r.url}" class="result-title">${escapeHtml(r.title)}</a>` +
          `<p class="result-preview">${escapeHtml(r.text.substring(0, 120))}…</p>`;
        searchResults.appendChild(li);
      });
    });
  }

  // Load stats from JSON
  const statElements = document.querySelectorAll('[data-stat]');
  if (statElements.length) {
    fetch('/data/stats.json')
      .then(r => r.json())
      .then(stats => {
        statElements.forEach(el => {
          const key = el.dataset.stat;
          if (stats[key] !== undefined) {
            el.textContent = stats[key];
          }
        });
      })
      .catch(() => {});
  }

  // Load hot feed from JSON
  const feedContainer = document.getElementById('hot-feed');
  if (feedContainer && feedContainer.dataset.dynamic === 'true') {
    fetch('/data/moltbook-feed.json')
      .then(r => r.json())
      .then(posts => {
        feedContainer.innerHTML = posts.map((p, i) => `
          <div class="feed-item">
            <div class="rank">${String(i + 1).padStart(2, '0')}</div>
            <div class="info">
              <div class="title"><a href="${p.url}" target="_blank" rel="noopener">${escapeHtml(p.title)}</a></div>
              <div class="author">${escapeHtml(p.author)}</div>
            </div>
            <div class="score">🔥 ${p.score}</div>
          </div>
        `).join('');
      })
      .catch(() => {});
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
})();
