# 調査ワークフロー ― フェーズ別実行ガイド

トークン消費を抑えるため、調査を独立した**フェーズ**に分割して実行します。
各フェーズは単独で完結し、前フェーズの出力ファイルを次フェーズが読み込む構造です。

---

## フェーズ一覧

| フェーズ | 目的 | 使うエージェント | 入力 | 出力ファイル |
|---------|------|-----------------|------|------------|
| **A. 計画** | 調査計画を立てる | `director` | 自治体名・テーマ | `workspace/<自治体>/plan.md` |
| **B. 予算調査** | 予算書・財政資料を収集 | `collector-budget` | plan.md の指示 | `workspace/<自治体>/budget_raw.md` |
| **C. 議事録調査** | 議会会議録を収集 | `collector-minutes` | plan.md の指示 | `workspace/<自治体>/minutes_raw.md` |
| **D. 受注実績調査** | 入札結果・随意契約を収集 | `collector-budget`（受注モード） | 自治体名・調達DB URL | `workspace/<自治体>/contracts_raw.md` |
| **E. 予算分析** | 予算データを分析 | `analyst-budget` | budget_raw.md | `workspace/<自治体>/budget_analysis.md` |
| **F. ニーズ分析** | 議事録から課題を抽出 | `analyst-needs` | minutes_raw.md | `workspace/<自治体>/needs_analysis.md` |
| **G. レポート作成** | 最終営業レポートを統合 | `qa-editor` | budget_analysis.md + needs_analysis.md | `workspace/<自治体>/report.md` |

---

## 各フェーズの実行方法

### フェーズA ― 計画（director）

```
directorエージェントを呼び出してください。
対象自治体: ○○市
テーマ: 防災
目的: 新規提案先の発掘
出力先: workspace/○○市/plan.md
```

**目安トークン**: 小〜中（計画のみ）

---

### フェーズB ― 予算調査（collector-budget）

```
collector-budgetエージェントを呼び出してください。
workspace/○○市/plan.md の「→ collector-budget」指示に従い、
予算資料を収集して workspace/○○市/budget_raw.md に保存してください。
```

**目安トークン**: 中〜大（PDF/HTML取得を伴う）
**ポイント**: 予算DBがShift-JIS文字化けする場合は金額・電話番号から補完検索

---

### フェーズC ― 議事録調査（collector-minutes）

```
collector-minutesエージェントを呼び出してください。
workspace/○○市/plan.md の「→ collector-minutes」指示に従い、
防災関連発言を収集して workspace/○○市/minutes_raw.md に保存してください。
```

**目安トークン**: 中〜大（PDF/HTML取得を伴う）
**ポイント**: 会議録がスキャン画像PDFの場合は「テキスト取得不可」と明記し、議会だよりで代替

---

### フェーズD ― 受注実績調査（collector-budget 受注モード）

```
collector-budgetエージェントを呼び出してください。
対象: ○○市の入札結果・随意契約（直近2年）
防災関連案件（通信・情報システム・備蓄・耐震・測量等）を抽出し、
workspace/○○市/contracts_raw.md に保存してください。
主な調査先:
  - 自治体の随意契約公表ページ
  - 入札結果公表ページ
  - 都道府県の物品調達情報
```

**目安トークン**: 中（ページ取得のみ）
**ポイント**: フェーズBと切り離すことで1回の実行量を抑えられる

---

### フェーズE ― 予算分析（analyst-budget）

```
analyst-budgetエージェントを呼び出してください。
入力: workspace/○○市/budget_raw.md
出力: workspace/○○市/budget_analysis.md
```

**目安トークン**: 小（ファイル読み込み＋分析のみ、Web検索なし）

---

### フェーズF ― ニーズ分析（analyst-needs）

```
analyst-needsエージェントを呼び出してください。
入力: workspace/○○市/minutes_raw.md
出力: workspace/○○市/needs_analysis.md
```

**目安トークン**: 小（ファイル読み込み＋分析のみ、Web検索なし）

---

### フェーズG ― レポート作成（qa-editor）

```
qa-editorエージェントを呼び出してください。
入力:
  - workspace/○○市/budget_analysis.md
  - workspace/○○市/needs_analysis.md
  - （あれば）workspace/○○市/contracts_raw.md
出力: workspace/○○市/report.md
```

**目安トークン**: 小〜中（ファイル読み込み＋統合のみ）
**注意**: qa-editorがファイル保存に失敗する場合、返答テキストをコピーして手動で保存

---

## ダッシュボード更新

レポート作成後、以下を実行してダッシュボードに反映します：

```bash
python tools/build_dashboard.py
git add docs/index.html && git commit -m "Update dashboard: ○○市"
git push -u origin <branch>
```

---

## フェーズ選択の目安

| やりたいこと | 実行するフェーズ |
|------------|---------------|
| はじめて自治体を調査する | A → B → C → E → F → G |
| 受注実績だけ追加調査する | D のみ |
| 補正予算が出たので更新する | B → E → G |
| 議会が終わったので議事録追加 | C → F → G |
| レポートだけ作り直す | G のみ |
