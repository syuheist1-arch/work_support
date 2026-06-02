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
    """攻めどころ表の提案テーマ列を最大3件抽出する。"""
    results = []
    in_table = False
    header_seen = False
    for line in text.splitlines():
        if re.search(r"##.*攻めどころ", line):
            in_table = True
            header_seen = False
            continue
        if in_table:
            if line.startswith("##"):
                break
            if "|" not in line:
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if not header_seen:
                if "提案テーマ" in line or "順位" in line:
                    header_seen = True
                continue
            if re.match(r"^[-|:\s]+$", line):
                continue
            if len(cols) >= 2:
                label = re.sub(r"[*`]", "", cols[1]).strip()
                # remove status prefix like 【公告済み】
                label = re.sub(r"^【[^】]+】\s*", "", label).strip()
                if label and label != "-":
                    results.append(label)
                    if len(results) == 3:
                        break
    return results


def extract_status_counts(text: str) -> dict:
    """攻めどころ表から案件ステータスの件数を集計する。"""
    counts = {"公告済み": 0, "予算化・未公告": 0, "仕込み": 0}
    in_table = False
    header_seen = False
    for line in text.splitlines():
        if re.search(r"##.*攻めどころ", line):
            in_table = True
            header_seen = False
            continue
        if in_table:
            if line.startswith("##"):
                break
            if "|" not in line:
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if not header_seen:
                if "提案テーマ" in line or "順位" in line:
                    header_seen = True
                continue
            if re.match(r"^[-|:\s]+$", line):
                continue
            if len(cols) >= 2:
                theme = cols[1]
                if "公告済み" in theme:
                    counts["公告済み"] += 1
                elif "予算化" in theme or "未公告" in theme:
                    counts["予算化・未公告"] += 1
                elif "仕込み" in theme or "中長期" in theme:
                    counts["仕込み"] += 1
    return counts


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
        status = extract_status_counts(text)
        munis.append({
            "name": d.name,
            "source": source_name,
            "date": extract_date(text),
            "attacks": attacks,
            "top_attack": attacks[0] if attacks else "-",
            "keypersons": extract_keypersons(text),
            "max_opportunity": extract_max_opportunity(text),
            "status": status,
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
body { font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; background: var(--bg); color: var(--text); }
header {
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, var(--surface) 0%, var(--surface2) 100%);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
}
header h1 { font-size: 1.1rem; font-weight: 700; }
header .badge { font-size: .68rem; background: var(--accent2); padding: .2em .7em; border-radius: 99px; color: #fff; }
header .built-at { font-size: .7rem; color: var(--text-muted); margin-left: auto; }

.page { max-width: 1600px; margin: 0 auto; padding: 1.2rem 1.5rem; display: flex; flex-direction: column; gap: 1.2rem; }

/* ── section title ── */
.section-title { font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: .6rem; }

/* ── Cards ── */
.cards { display: flex; gap: .8rem; flex-wrap: wrap; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: .85rem 1rem; cursor: pointer; transition: border-color .15s, transform .1s;
  min-width: 200px; flex: 1 1 200px; max-width: 280px;
}
.card:hover { border-color: var(--accent); transform: translateY(-2px); }
.card.active { border-color: var(--accent); background: var(--surface2); box-shadow: 0 0 0 1px var(--accent); }
.card-name { font-size: 1rem; font-weight: 700; margin-bottom: .2rem; }
.card-date { font-size: .68rem; color: var(--text-muted); margin-bottom: .4rem; }
.status-badges { display: flex; gap: .3rem; flex-wrap: wrap; margin-bottom: .4rem; }
.badge-status { font-size: .62rem; padding: .12em .55em; border-radius: 99px; font-weight: 600; white-space: nowrap; }
.badge-announced { background: color-mix(in srgb,var(--green) 18%,transparent); color: var(--green); border: 1px solid var(--green); }
.badge-budgeted  { background: color-mix(in srgb,var(--yellow) 18%,transparent); color: var(--yellow); border: 1px solid var(--yellow); }
.badge-pipeline  { background: color-mix(in srgb,var(--text-muted) 15%,transparent); color: var(--text-muted); border: 1px solid var(--text-muted); }
.card-attacks { list-style: none; }
.card-attacks li { font-size: .73rem; padding: .12rem 0; display: flex; gap: .35rem; }
.card-attacks li::before { content: "▸"; color: var(--accent); flex-shrink: 0; }

/* ── Compare table ── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .78rem; }
th { background: var(--surface2); padding: .55rem .75rem; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); white-space: nowrap; }
td { padding: .5rem .75rem; border-bottom: 1px solid var(--border); vertical-align: top; line-height: 1.5; }
tr:hover td { background: var(--surface2); }
tr.active-row td { background: color-mix(in srgb,var(--accent) 10%,transparent); }
.muni-link { color: var(--accent); cursor: pointer; font-weight: 600; }
.muni-link:hover { text-decoration: underline; }

/* ── Detail panel ── */
#detail-panel {
  display: none;
  border: 1px solid var(--accent);
  border-radius: 12px;
  background: var(--surface);
  overflow: hidden;
}
#detail-panel.visible { display: block; }

/* header bar */
.dp-header {
  display: flex; align-items: center; gap: .8rem; flex-wrap: wrap;
  padding: .8rem 1.2rem;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
}
.dp-title { font-size: 1rem; font-weight: 700; }
.dp-meta { font-size: .72rem; color: var(--text-muted); }
#detail-close {
  margin-left: auto; background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: .25rem .7rem; border-radius: 6px;
  cursor: pointer; font-size: .75rem;
}
#detail-close:hover { border-color: var(--accent); color: var(--text); }

/* section grid — 3 columns on wide screens */
.dp-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}
@media (min-width: 900px)  { .dp-grid { grid-template-columns: 1fr 1fr; } }
@media (min-width: 1280px) { .dp-grid { grid-template-columns: 2fr 1fr 1fr; } }

.dp-section {
  padding: 1rem 1.2rem;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  overflow: hidden;
}
.dp-section:last-child { border-right: none; }
.dp-section-title {
  font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--accent); margin-bottom: .6rem;
}

/* rendered markdown inside sections */
.dp-body p { font-size: .82rem; line-height: 1.75; margin: .35em 0; }
.dp-body ul, .dp-body ol { padding-left: 1.3em; font-size: .82rem; line-height: 1.75; margin: .35em 0; }
.dp-body li { margin: .15em 0; }
.dp-body strong { color: var(--yellow); }
.dp-body a { color: var(--accent); word-break: break-all; }
.dp-body code { background: var(--surface2); padding: .1em .35em; border-radius: 3px; font-size: .8em; }
/* tables in detail */
.dp-body .tbl-wrap { overflow-x: auto; margin: .5em 0; }
.dp-body table { width: 100%; border-collapse: collapse; font-size: .75rem; white-space: nowrap; }
.dp-body th { background: var(--surface2); padding: .4rem .6rem; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); }
.dp-body td { padding: .38rem .6rem; border-bottom: 1px solid var(--border); vertical-align: top; white-space: normal; }
.dp-body td:first-child { white-space: nowrap; }
/* confirmed/budgeted/pipeline color in table cells */
.dp-body td:first-child { font-weight: 600; }

/* summary bullets */
.summary-list { list-style: none; padding: 0; }
.summary-list li {
  font-size: .82rem; line-height: 1.7;
  padding: .3rem 0 .3rem .9rem;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.summary-list li:last-child { border-bottom: none; }
.summary-list li::before { content: "●"; color: var(--accent); position: absolute; left: 0; font-size: .55rem; top: .55rem; }
</style>
</head>
<body>
<header>
  <h1>🛡 営業支援 防災ダッシュボード</h1>
  <span class="badge">Phase 1</span>
  <span class="built-at">生成: __BUILT_AT__</span>
</header>

<div class="page">
  <!-- カード一覧 -->
  <section>
    <div class="section-title" id="cards-title">自治体一覧 (__COUNT__ 件)</div>
    <div class="cards" id="cards"></div>
  </section>

  <!-- 比較表 -->
  <section>
    <div class="section-title">横断比較</div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>自治体</th><th>ステータス</th><th>攻めどころ Top</th>
          <th>想定キーパーソン</th><th>更新日</th>
        </tr></thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </section>

  <!-- 詳細パネル（フル幅・横並びグリッド） -->
  <div id="detail-panel">
    <div class="dp-header">
      <span class="dp-title" id="dp-title">-</span>
      <span class="dp-meta" id="dp-meta"></span>
      <button id="detail-close" onclick="closeDetail()">✕ 閉じる</button>
    </div>
    <div class="dp-grid" id="dp-grid"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;

/* Section order for detail panel: label → regex that matches the ## heading */
const SECTIONS = [
  { key: 'summary',   label: 'エグゼクティブサマリー', re: /エグゼクティブ|サマリ/ },
  { key: 'attacks',   label: '攻めどころ',             re: /攻めどころ/ },
  { key: 'budget',    label: '防災予算',               re: /防災予算/ },
  { key: 'minutes',   label: '議会・首長の関心',        re: /議会|首長/ },
  { key: 'actions',   label: '次アクション',            re: /次アクション/ },
  { key: 'issues',    label: '要確認事項',              re: /要確認/ },
];

function parseSections(markdown) {
  const result = {};
  const lines = markdown.split('\n');
  let cur = null;
  for (const line of lines) {
    if (line.startsWith('## ')) {
      const heading = line.slice(3).trim();
      cur = null;
      for (const s of SECTIONS) {
        if (s.re.test(heading)) { cur = s.key; result[cur] = result[cur] || []; break; }
      }
    } else if (cur) {
      result[cur].push(line);
    }
  }
  // trim leading/trailing blank lines
  for (const k of Object.keys(result)) {
    while (result[k].length && !result[k][0].trim()) result[k].shift();
    while (result[k].length && !result[k][result[k].length-1].trim()) result[k].pop();
  }
  return result;
}

function renderSection(lines) {
  const md = lines.join('\n');
  let html = marked.parse(md);
  // wrap tables in scrollable div
  html = html.replace(/<table>/g, '<div class="tbl-wrap"><table>').replace(/<\/table>/g, '</table></div>');
  return `<div class="dp-body">${html}</div>`;
}

function badgesHtml(s, size) {
  return [
    s['公告済み'] > 0       ? `<span class="badge-status badge-announced">公告済み ${s['公告済み']}件</span>` : '',
    s['予算化・未公告'] > 0  ? `<span class="badge-status badge-budgeted">予算化・未公告 ${s['予算化・未公告']}件</span>` : '',
    s['仕込み'] > 0          ? `<span class="badge-status badge-pipeline">仕込み ${s['仕込み']}件</span>` : '',
  ].filter(Boolean).join('');
}

function showDetail(idx) {
  const d = DATA[idx];
  document.getElementById('dp-title').textContent = d.name + ' / 防災';
  document.getElementById('dp-meta').textContent = '更新: ' + d.date;

  const sections = parseSections(d.markdown);
  const grid = document.getElementById('dp-grid');
  grid.innerHTML = '';

  for (const s of SECTIONS) {
    if (!sections[s.key] || !sections[s.key].length) continue;
    const div = document.createElement('div');
    div.className = 'dp-section';
    div.innerHTML = `<div class="dp-section-title">${s.label}</div>${renderSection(sections[s.key])}`;
    grid.appendChild(div);
  }

  const panel = document.getElementById('detail-panel');
  panel.classList.add('visible');
  document.querySelectorAll('.card').forEach((c, i) => c.classList.toggle('active', i === idx));
  document.querySelectorAll('#table-body tr').forEach((r, i) => r.classList.toggle('active-row', i === idx));
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('visible');
  document.getElementById('dp-grid').innerHTML = '';
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
      <div class="card-date">更新: ${d.date}</div>
      <div class="status-badges">${badgesHtml(d.status || {})}</div>
      <ul class="card-attacks">${d.attacks.map(a => `<li>${a}</li>`).join('')}</ul>`;
    el.addEventListener('click', () => showDetail(i));
    wrap.appendChild(el);
  });
  document.getElementById('cards-title').textContent = `自治体一覧 (${DATA.length} 件)`;
}

function buildTable() {
  const tbody = document.getElementById('table-body');
  DATA.forEach((d, i) => {
    const s = d.status || {};
    const b = [
      s['公告済み'] > 0      ? `<span class="badge-status badge-announced">公告済み ${s['公告済み']}</span>` : '',
      s['予算化・未公告'] > 0 ? `<span class="badge-status badge-budgeted">予算化 ${s['予算化・未公告']}</span>` : '',
      s['仕込み'] > 0         ? `<span class="badge-status badge-pipeline">仕込み ${s['仕込み']}</span>` : '',
    ].filter(Boolean).join(' ');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><a class="muni-link" onclick="showDetail(${i})">${d.name}</a></td>
      <td style="white-space:nowrap">${b || '-'}</td>
      <td>${d.top_attack}</td>
      <td>${d.keypersons}</td>
      <td style="white-space:nowrap">${d.date}</td>`;
    tbody.appendChild(tr);
  });
}

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
            "status": m["status"],
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
