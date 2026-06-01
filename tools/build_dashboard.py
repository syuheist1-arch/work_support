#!/usr/bin/env python3
"""
tools/build_dashboard.py
workspace/<自治体>/ を走査して docs/index.html を生成する。
Python 標準ライブラリのみ使用。
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "workspace"
OUTPUT = Path(__file__).parent.parent / "docs" / "index.html"


def find_report(muni_dir: Path) -> tuple[str, Path]:
    """report.md → budget_analysis.md → needs_analysis.md の優先順で返す。"""
    for name in ("report.md", "budget_analysis.md", "needs_analysis.md"):
        p = muni_dir / name
        if p.exists():
            return name, p
    return "", Path()


def extract_date(text: str) -> str:
    m = re.search(r"作成日[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text[:300])
    return m.group(1) if m else "-"


def extract_top_attacks(text: str) -> list[str]:
    """攻めどころ Top3 の見出し行を最大3件抽出する。"""
    results = []
    for line in text.splitlines():
        if re.search(r"第[123一二三]位[：:]?\s*(.+)", line):
            m = re.search(r"第[123一二三]位[：:]?\s*(.+)", line)
            label = re.sub(r"[#*`]", "", m.group(1)).strip()
            label = re.sub(r"\s*／\s*確度.*$", "", label).strip()
            results.append(label)
            if len(results) == 3:
                break
    return results


def extract_keypersons(text: str) -> str:
    """キーパーソン節の最初の表行から名前を最大3件カンマ区切りで返す。"""
    in_section = False
    names = []
    for line in text.splitlines():
        if re.search(r"##.*(キーパーソン)", line):
            in_section = True
            continue
        if in_section:
            if line.startswith("##"):
                break
            if line.startswith("|") and not re.search(r"[-|]{3,}", line) and "名前" not in line:
                cols = [c.strip() for c in line.strip("|").split("|")]
                if cols:
                    name = re.sub(r"\*+", "", cols[0]).strip()
                    if name:
                        names.append(name)
                        if len(names) == 3:
                            break
    return "、".join(names) if names else "-"


def extract_max_opportunity(text: str) -> str:
    """エグゼクティブサマリー or 攻めどころから「最大の機会」キーワード行を返す。"""
    for line in text.splitlines():
        if "最大" in line and ("機会" in line or "好機" in line or "イベント" in line):
            clean = re.sub(r"^[-*\s]+", "", line).strip()
            clean = re.sub(r"\*+", "", clean).strip()
            return clean[:80] + ("…" if len(clean) > 80 else "")
    return "-"


def collect_municipalities() -> list[dict]:
    munis = []
    if not WORKSPACE.exists():
        return munis
    for d in sorted(WORKSPACE.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        source_name, source_path = find_report(d)
        if not source_path.exists():
            continue
        text = source_path.read_text(encoding="utf-8")
        attacks = extract_top_attacks(text)
        munis.append({
            "name": d.name,
            "source": source_name,
            "date": extract_date(text),
            "attacks": attacks,
            "top_attack": attacks[0] if attacks else "-",
            "keypersons": extract_keypersons(text),
            "max_opportunity": extract_max_opportunity(text),
            "markdown": text,
        })
    return munis


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>営業支援 防災ダッシュボード</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #232637;
  --border: #2e3250;
  --accent: #4f8ef7;
  --accent2: #7c5af7;
  --text: #e2e4f0;
  --text-muted: #8b8fa8;
  --green: #3ecf8e;
  --yellow: #f5a623;
  --red: #f76262;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}
header {
  padding: 1.2rem 1.5rem;
  background: linear-gradient(135deg, var(--surface) 0%, var(--surface2) 100%);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
header h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: .03em; }
header .badge {
  font-size: .7rem;
  background: var(--accent2);
  padding: .2em .7em;
  border-radius: 99px;
  color: #fff;
}
header .built-at { font-size: .72rem; color: var(--text-muted); margin-left: auto; }

.main-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* ── Cards ── */
.section-title {
  font-size: .8rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: .8rem;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem;
  cursor: pointer;
  transition: border-color .15s, transform .1s;
}
.card:hover { border-color: var(--accent); transform: translateY(-2px); }
.card.active { border-color: var(--accent); background: var(--surface2); }
.card-name { font-size: 1.1rem; font-weight: 700; margin-bottom: .3rem; }
.card-date { font-size: .72rem; color: var(--text-muted); margin-bottom: .6rem; }
.card-attacks { list-style: none; }
.card-attacks li {
  font-size: .78rem;
  padding: .18rem 0;
  color: var(--text);
  display: flex;
  gap: .4rem;
}
.card-attacks li::before { content: "▸"; color: var(--accent); flex-shrink: 0; }

/* ── Table ── */
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: .8rem;
}
th {
  background: var(--surface2);
  padding: .6rem .8rem;
  text-align: left;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
td {
  padding: .55rem .8rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  line-height: 1.5;
}
tr:hover td { background: var(--surface2); }
tr.active-row td { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.muni-link {
  color: var(--accent);
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
}
.muni-link:hover { text-decoration: underline; }

/* ── Detail panel ── */
#detail-panel {
  display: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.5rem;
}
#detail-panel.visible { display: block; }
#detail-panel h2 {
  font-size: 1rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: .6rem;
}
/* marked.js 出力スタイル */
#detail-content h1,#detail-content h2,#detail-content h3 {
  margin: 1.2em 0 .4em;
  line-height: 1.3;
}
#detail-content h1 { font-size: 1.3rem; }
#detail-content h2 { font-size: 1.1rem; border-bottom: 1px solid var(--border); padding-bottom: .3rem; }
#detail-content h3 { font-size: .95rem; color: var(--accent); }
#detail-content p { margin: .5em 0; line-height: 1.8; font-size: .88rem; }
#detail-content ul,#detail-content ol { padding-left: 1.4em; margin: .5em 0; font-size: .88rem; line-height: 1.8; }
#detail-content table { margin: .8em 0; }
#detail-content th { font-size: .78rem; }
#detail-content td { font-size: .78rem; }
#detail-content a { color: var(--accent); }
#detail-content strong { color: var(--yellow); }
#detail-content code {
  background: var(--surface2);
  padding: .1em .4em;
  border-radius: 4px;
  font-size: .85em;
}
#detail-close {
  float: right;
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: .3rem .8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: .8rem;
}
#detail-close:hover { border-color: var(--accent); color: var(--text); }

@media (min-width: 1024px) {
  .main-layout {
    grid-template-columns: 1fr 420px;
    grid-template-rows: auto auto 1fr;
  }
  .cards-section { grid-column: 1 / 2; }
  .table-section { grid-column: 1 / 2; }
  #detail-panel { grid-column: 2; grid-row: 1 / 4; display: block; position: sticky; top: 1rem; max-height: 90vh; overflow-y: auto; }
  #detail-panel:not(.visible) #detail-content { display: none; }
  #detail-panel:not(.visible)::after { content: "← 自治体を選ぶとレポートを表示"; display: block; color: var(--text-muted); font-size: .88rem; text-align: center; padding: 2rem; }
  #detail-close { display: none; }
}
</style>
</head>
<body>
<header>
  <h1>🛡 営業支援 防災ダッシュボード</h1>
  <span class="badge">Phase 1</span>
  <span class="built-at">生成: __BUILT_AT__</span>
</header>

<div class="main-layout">
  <!-- カード一覧 -->
  <section class="cards-section">
    <div class="section-title">自治体一覧 (__COUNT__ 件)</div>
    <div class="cards" id="cards"></div>
  </section>

  <!-- 比較表 -->
  <section class="table-section">
    <div class="section-title">横断比較表</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>自治体</th>
            <th>攻めどころ Top</th>
            <th>想定キーパーソン</th>
            <th>最大の機会</th>
            <th>更新日</th>
          </tr>
        </thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </section>

  <!-- 詳細パネル -->
  <div id="detail-panel">
    <h2 id="detail-title">レポート</h2>
    <button id="detail-close" onclick="closeDetail()">✕ 閉じる</button>
    <div id="detail-content"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;

function showDetail(idx) {
  const d = DATA[idx];
  document.getElementById('detail-title').textContent = d.name + ' / ' + d.source;
  document.getElementById('detail-content').innerHTML = marked.parse(d.markdown);
  const panel = document.getElementById('detail-panel');
  panel.classList.add('visible');
  // card highlight
  document.querySelectorAll('.card').forEach((c, i) => c.classList.toggle('active', i === idx));
  document.querySelectorAll('#table-body tr').forEach((r, i) => r.classList.toggle('active-row', i === idx));
  // mobile scroll
  if (window.innerWidth < 1024) panel.scrollIntoView({ behavior: 'smooth' });
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('visible');
  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('#table-body tr').forEach(r => r.classList.remove('active-row'));
}

function buildCards() {
  const wrap = document.getElementById('cards');
  DATA.forEach((d, i) => {
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div class="card-name">${d.name}</div>
      <div class="card-date">更新: ${d.date} &nbsp;|&nbsp; ${d.source}</div>
      <ul class="card-attacks">${d.attacks.map(a => `<li>${a}</li>`).join('')}</ul>
    `;
    el.addEventListener('click', () => showDetail(i));
    wrap.appendChild(el);
  });
}

function buildTable() {
  const tbody = document.getElementById('table-body');
  DATA.forEach((d, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><a class="muni-link" onclick="showDetail(${i})">${d.name}</a></td>
      <td>${d.top_attack}</td>
      <td>${d.keypersons}</td>
      <td style="max-width:240px;font-size:.75rem">${d.max_opportunity}</td>
      <td style="white-space:nowrap">${d.date}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById('cards').closest('.cards-section')
  .querySelector('.section-title').textContent =
  `自治体一覧 (${DATA.length} 件)`;

buildCards();
buildTable();
</script>
</body>
</html>
"""


def build():
    munis = collect_municipalities()
    if not munis:
        print("警告: workspace/ 配下に読み込めるレポートが見つかりませんでした。", file=sys.stderr)

    # JS に埋め込む用に markdown ごと JSON 化（HTMLエスケープはmarked.jsが処理）
    data_for_js = [
        {
            "name": m["name"],
            "source": m["source"],
            "date": m["date"],
            "attacks": m["attacks"],
            "top_attack": m["top_attack"],
            "keypersons": m["keypersons"],
            "max_opportunity": m["max_opportunity"],
            "markdown": m["markdown"],
        }
        for m in munis
    ]

    html = HTML_TEMPLATE
    html = html.replace("__BUILT_AT__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__COUNT__", str(len(munis)))
    html = html.replace("__DATA_JSON__", json.dumps(data_for_js, ensure_ascii=False))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"✅  生成完了: {OUTPUT}  ({len(munis)} 自治体)")


if __name__ == "__main__":
    build()
