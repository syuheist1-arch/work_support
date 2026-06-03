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
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "workspace"
OUTPUT = Path(__file__).parent.parent / "docs" / "index.html"
QUEUE = Path(__file__).parent.parent / "workspace" / "pipeline_queue.json"
JST = timezone(timedelta(hours=9))


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


def has_musen_budget(text: str) -> bool:
    """防災行政無線の設計・更新・改修が攻めどころ表で予算化・公告済みとなっているか判定する。
    過去の随意契約実績行（R6.x.x / R7.x.x 契約日を含む行）は対象外。
    """
    actions = ["設計", "更新", "改修", "整備", "部分更新", "機器更新", "システム更新"]
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
            if not header_seen:
                if "提案テーマ" in line or "順位" in line:
                    header_seen = True
                continue
            if re.match(r"^[-|:\s]+$", line):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) < 2:
                continue
            theme = cols[1]
            # 予算化・未公告 または 公告済み の行のみ対象
            if not re.search(r"予算化|未公告|公告済み", theme):
                continue
            if "防災行政無線" in theme and any(a in theme for a in actions):
                return True
    return False


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


def load_prefecture_map() -> dict[str, str]:
    """pipeline_queue.json から {自治体名: 都道府県名} のマップを返す。"""
    if not QUEUE.exists():
        return {}
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    return {m["name"]: m["prefecture"] for m in q.get("municipalities", [])}


def collect_municipalities() -> list[dict]:
    pref_map = load_prefecture_map()
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
            "prefecture": pref_map.get(d.name, ""),
            "source": source_name,
            "date": extract_date(text),
            "attacks": attacks,
            "top_attack": attacks[0] if attacks else "-",
            "keypersons": extract_keypersons(text),
            "max_opportunity": extract_max_opportunity(text),
            "status": status,
            "musen_alert": has_musen_budget(text),
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

.section-title { font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: .6rem; }

/* ── Prefecture groups ── */
.pref-groups { display: flex; flex-direction: column; gap: 1rem; }
.pref-group {}
.pref-label {
  font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: .45rem; padding-left: .1rem;
}
.cards { display: flex; gap: .4rem; flex-wrap: wrap; }

/* ── Cards (name-only chips) ── */
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: .35rem .75rem; cursor: pointer; transition: border-color .15s, background .15s;
  white-space: nowrap;
}
.card:hover { border-color: var(--accent); background: var(--surface2); }
.card.active { border-color: var(--accent); background: var(--surface2); box-shadow: 0 0 0 1px var(--accent); }
/* 防災行政無線 予算化強調 */
.card.musen-alert {
  border-color: var(--yellow);
  background: color-mix(in srgb,var(--yellow) 10%,var(--surface));
  box-shadow: 0 0 0 1px color-mix(in srgb,var(--yellow) 40%,transparent),
              0 0 10px color-mix(in srgb,var(--yellow) 15%,transparent);
}
.card.musen-alert .card-name { color: var(--yellow); }
.card.musen-alert:hover {
  border-color: var(--yellow);
  background: color-mix(in srgb,var(--yellow) 16%,var(--surface));
}
.card-name { font-size: .85rem; font-weight: 700; }

/* badge helpers (still used in modal/table) */
.status-badges { display: flex; gap: .25rem; flex-wrap: wrap; }
.badge-status { font-size: .6rem; padding: .1em .5em; border-radius: 99px; font-weight: 600; white-space: nowrap; }
.badge-announced { background: color-mix(in srgb,var(--green) 18%,transparent); color: var(--green); border: 1px solid var(--green); }
.badge-budgeted  { background: color-mix(in srgb,var(--yellow) 18%,transparent); color: var(--yellow); border: 1px solid var(--yellow); }
.badge-pipeline  { background: color-mix(in srgb,var(--text-muted) 15%,transparent); color: var(--text-muted); border: 1px solid var(--text-muted); }

/* ── Compare table ── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .78rem; }
th { background: var(--surface2); padding: .55rem .75rem; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); white-space: nowrap; }
td { padding: .5rem .75rem; border-bottom: 1px solid var(--border); vertical-align: top; line-height: 1.5; }
tr:hover td { background: var(--surface2); }
tr.active-row td { background: color-mix(in srgb,var(--accent) 10%,transparent); }
.muni-link { color: var(--accent); cursor: pointer; font-weight: 600; }
.muni-link:hover { text-decoration: underline; }

/* ══════════════════════════════════════════
   MODAL
══════════════════════════════════════════ */
#modal-overlay {
  display: none;
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,.65);
  backdrop-filter: blur(2px);
}
#modal-overlay.open { display: flex; align-items: flex-start; justify-content: center; padding: 1.5vh 1vw; }

#modal {
  background: var(--surface);
  border: 1px solid var(--accent);
  border-radius: 14px;
  width: 100%;
  max-width: 1400px;
  max-height: 96vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* modal header */
.modal-header {
  display: flex; align-items: center; gap: .8rem; flex-wrap: wrap;
  padding: .75rem 1.2rem;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.modal-title { font-size: 1.05rem; font-weight: 700; }
.modal-meta  { font-size: .72rem; color: var(--text-muted); }
.modal-nav   { display: flex; gap: .4rem; margin-left: auto; align-items: center; }
.modal-nav button {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: .22rem .65rem; border-radius: 6px;
  cursor: pointer; font-size: .75rem;
}
.modal-nav button:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
.modal-nav button:disabled { opacity: .35; cursor: default; }
.modal-close {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: .22rem .7rem; border-radius: 6px;
  cursor: pointer; font-size: .75rem;
}
.modal-close:hover { border-color: var(--red); color: var(--red); }

/* tab bar */
.tab-bar {
  display: flex; gap: 0; overflow-x: auto; flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
  scrollbar-width: none;
}
.tab-bar::-webkit-scrollbar { display: none; }
.tab-btn {
  padding: .55rem 1.1rem; font-size: .78rem; white-space: nowrap;
  background: none; border: none; border-bottom: 2px solid transparent;
  color: var(--text-muted); cursor: pointer; transition: color .15s, border-color .15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }

/* tab content */
.tab-content {
  flex: 1; overflow-y: auto; padding: 1.4rem 1.6rem;
}
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* rendered markdown */
.dp-body { max-width: 100%; }
.dp-body h3 { font-size: .92rem; font-weight: 700; margin: 1em 0 .4em; color: var(--accent); }
.dp-body p  { font-size: .85rem; line-height: 1.8; margin: .4em 0; }
.dp-body ul, .dp-body ol { padding-left: 1.4em; font-size: .85rem; line-height: 1.8; margin: .4em 0; }
.dp-body li { margin: .2em 0; }
.dp-body strong { color: var(--yellow); }
.dp-body a { color: var(--accent); word-break: break-all; }
.dp-body code { background: var(--surface2); padding: .1em .35em; border-radius: 3px; font-size: .8em; }
.dp-body blockquote { border-left: 3px solid var(--accent2); padding-left: .9em; color: var(--text-muted); margin: .5em 0; }
/* tables — full width, scrollable on narrow screens */
.dp-body .tbl-wrap { overflow-x: auto; margin: .7em 0; border-radius: 6px; border: 1px solid var(--border); }
.dp-body table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.dp-body th { background: var(--surface2); padding: .45rem .75rem; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); white-space: nowrap; text-align: left; }
.dp-body td { padding: .42rem .75rem; border-bottom: 1px solid var(--border); vertical-align: top; line-height: 1.6; }
.dp-body tr:last-child td { border-bottom: none; }
.dp-body tr:hover td { background: var(--surface2); }
</style>
</head>
<body>
<header>
  <h1>🛡 営業支援 防災ダッシュボード</h1>
  <span class="badge">Phase 1</span>
  <span class="built-at">生成: __BUILT_AT__</span>
</header>

<div class="page">
  <section>
    <div class="section-title" id="cards-title">自治体一覧 (__COUNT__ 件)</div>
    <div class="pref-groups" id="pref-groups"></div>
  </section>

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
</div>

<!-- ══ MODAL ══ -->
<div id="modal-overlay" onclick="overlayClick(event)">
  <div id="modal">
    <div class="modal-header">
      <span class="modal-title" id="modal-title">-</span>
      <span class="modal-meta"  id="modal-meta"></span>
      <div class="modal-nav">
        <button id="btn-prev" onclick="navigate(-1)">◀ 前</button>
        <button id="btn-next" onclick="navigate(+1)">次 ▶</button>
        <button class="modal-close" onclick="closeModal()">✕ 閉じる</button>
      </div>
    </div>
    <div class="tab-bar" id="tab-bar"></div>
    <div class="tab-content" id="tab-content"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
let currentIdx = -1;

const SECTIONS = [
  { key: 'summary',  label: 'サマリー',       re: /エグゼクティブ|サマリ/ },
  { key: 'attacks',  label: '攻めどころ',      re: /攻めどころ/ },
  { key: 'budget',   label: '防災予算',        re: /防災予算/ },
  { key: 'minutes',  label: '議会・首長の関心', re: /議会|首長/ },
  { key: 'actions',  label: '次アクション',    re: /次アクション/ },
  { key: 'issues',   label: '要確認事項',      re: /要確認/ },
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
  for (const k of Object.keys(result)) {
    while (result[k].length && !result[k][0].trim()) result[k].shift();
    while (result[k].length && !result[k][result[k].length-1].trim()) result[k].pop();
  }
  return result;
}

function renderMd(lines) {
  const md = lines.join('\n');
  let html = marked.parse(md);
  html = html.replace(/<table>/g, '<div class="tbl-wrap"><table>').replace(/<\/table>/g, '</table></div>');
  return `<div class="dp-body">${html}</div>`;
}

function badgesHtml(s) {
  return [
    s['公告済み'] > 0      ? `<span class="badge-status badge-announced">公告済み ${s['公告済み']}件</span>` : '',
    s['予算化・未公告'] > 0 ? `<span class="badge-status badge-budgeted">予算化・未公告 ${s['予算化・未公告']}件</span>` : '',
    s['仕込み'] > 0         ? `<span class="badge-status badge-pipeline">仕込み ${s['仕込み']}件</span>` : '',
  ].filter(Boolean).join('');
}

function openModal(idx) {
  currentIdx = idx;
  const d = DATA[idx];

  document.getElementById('modal-title').textContent = d.name + ' / 防災';
  document.getElementById('modal-meta').textContent  = '更新: ' + d.date;
  document.getElementById('btn-prev').disabled = idx === 0;
  document.getElementById('btn-next').disabled = idx === DATA.length - 1;

  const sections = parseSections(d.markdown);

  // build tabs
  const tabBar     = document.getElementById('tab-bar');
  const tabContent = document.getElementById('tab-content');
  tabBar.innerHTML = '';
  tabContent.innerHTML = '';

  let firstKey = null;
  for (const s of SECTIONS) {
    if (!sections[s.key] || !sections[s.key].length) continue;
    if (!firstKey) firstKey = s.key;

    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.dataset.key = s.key;
    btn.textContent = s.label;
    btn.onclick = () => switchTab(s.key);
    tabBar.appendChild(btn);

    const pane = document.createElement('div');
    pane.className = 'tab-pane';
    pane.id = 'pane-' + s.key;
    pane.innerHTML = renderMd(sections[s.key]);
    tabContent.appendChild(pane);
  }

  if (firstKey) switchTab(firstKey);

  // highlight cards / table rows
  document.querySelectorAll('.card').forEach(c => c.classList.toggle('active', +c.dataset.idx === idx));
  document.querySelectorAll('#table-body tr').forEach((r, i) => r.classList.toggle('active-row', i === idx));

  document.getElementById('modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function switchTab(key) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.key === key));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-' + key));
  document.getElementById('tab-content').scrollTop = 0;
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('#table-body tr').forEach(r => r.classList.remove('active-row'));

  currentIdx = -1;
}

function navigate(dir) {
  const next = currentIdx + dir;
  if (next >= 0 && next < DATA.length) openModal(next);
}

function overlayClick(e) {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
}

document.addEventListener('keydown', e => {
  const overlay = document.getElementById('modal-overlay');
  if (!overlay.classList.contains('open')) return;
  if (e.key === 'Escape')      closeModal();
  if (e.key === 'ArrowRight')  navigate(+1);
  if (e.key === 'ArrowLeft')   navigate(-1);
});

function buildCards() {
  // group by prefecture preserving insertion order
  const groups = [];
  const groupMap = {};
  DATA.forEach((d, i) => {
    const pref = d.prefecture || '—';
    if (!groupMap[pref]) {
      groupMap[pref] = [];
      groups.push({ pref, items: groupMap[pref] });
    }
    groupMap[pref].push({ d, i });
  });

  const container = document.getElementById('pref-groups');
  groups.forEach(({ pref, items }) => {
    const groupEl = document.createElement('div');
    groupEl.className = 'pref-group';

    const label = document.createElement('div');
    label.className = 'pref-label';
    label.textContent = pref;
    groupEl.appendChild(label);

    const cardsEl = document.createElement('div');
    cardsEl.className = 'cards';
    items.forEach(({ d, i }) => {
      const el = document.createElement('div');
      el.className = 'card' + (d.musen_alert ? ' musen-alert' : '');
      el.dataset.idx = i;
      el.innerHTML = `<div class="card-name">${d.name}</div>`;
      el.addEventListener('click', () => openModal(i));
      cardsEl.appendChild(el);
    });
    groupEl.appendChild(cardsEl);
    container.appendChild(groupEl);
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
      <td><a class="muni-link" onclick="openModal(${i})">${d.name}</a></td>
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
            "prefecture": m["prefecture"],
            "source": m["source"],
            "date": m["date"],
            "attacks": m["attacks"],
            "top_attack": m["top_attack"],
            "keypersons": m["keypersons"],
            "max_opportunity": m["max_opportunity"],
            "status": m["status"],
            "musen_alert": m["musen_alert"],
            "markdown": m["markdown"],
        }
        for m in munis
    ]

    html = HTML_TEMPLATE
    html = html.replace("__BUILT_AT__", datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"))
    html = html.replace("__COUNT__", str(len(munis)))
    html = html.replace("__DATA_JSON__", json.dumps(data_for_js, ensure_ascii=False))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"✅  生成完了: {OUTPUT}  ({len(munis)} 自治体)")


if __name__ == "__main__":
    build()
