# プロジェクト運用ルール

## セッション開始時の自動処理（キュー駆動）

**ユーザーが「次の自治体を処理して」「キューを進めて」と言ったとき、または新しいセッションで調査継続を求められたとき**は、以下を実行すること:

1. `python tools/queue_status.py` でキュー状況を確認
2. `status: in_progress` または `status: pending` の先頭自治体の `phases_todo[0]` を実行
3. フェーズ完了後、`workspace/pipeline_queue.json` の `phases_done` に追加、`phases_todo` から削除
4. 全フェーズ完了したら `status: done` に更新
5. `python tools/build_dashboard.py` → `git push` まで実行

### キューへの自治体追加方法
`workspace/pipeline_queue.json` の `municipalities` 配列に以下を追加する:
```json
{
  "name": "〇〇市",
  "prefecture": "〇〇県",
  "theme": "防災",
  "status": "pending",
  "phases_done": [],
  "phases_todo": ["B_budget", "C_minutes", "E_analysis", "F_needs", "G_report"],
  "note": ""
}
```

---

## 調査後の必須処理

### 予算調査（フェーズB）を実行したとき
収集・分析・レポート更新のいずれかが完了したら、**必ずダッシュボードへの反映まで実行すること**。

```bash
python tools/build_dashboard.py
git add docs/index.html workspace/<自治体>/ && git commit -m "Update dashboard: <自治体> <内容>"
git push -u origin <branch>
```

### 議事録調査（フェーズC）を実行したとき
同様に、レポートに反映した後、ダッシュボードを再ビルドしてプッシュすること。

### レポート（report.md）を更新したとき
ダッシュボードを再ビルドしてプッシュすること。

---

## ワークフロー概要

詳細は `docs/workflow.md` を参照。

| フェーズ | 内容 | 出力 |
|---------|------|------|
| A. 計画 | director | workspace/<自治体>/plan.md |
| B. 予算調査 | collector-budget | workspace/<自治体>/budget_raw*.md |
| C. 議事録調査 | collector-minutes | workspace/<自治体>/minutes_raw.md |
| D. 受注実績調査 | collector-budget（受注モード） | workspace/<自治体>/contracts_raw.md |
| E. 予算分析 | analyst-budget | workspace/<自治体>/budget_analysis.md |
| F. ニーズ分析 | analyst-needs | workspace/<自治体>/needs_analysis.md |
| G. レポート作成 | qa-editor | workspace/<自治体>/report.md |
| **→ ダッシュボード反映** | `python tools/build_dashboard.py` + git push | docs/index.html |

---

## PDF抽出

WebFetchでPDFが読めない場合は `curl` + PyMuPDF（fitz）で抽出する:

```bash
curl -sL "<URL>" -o /tmp/target.pdf
python3 -c "import fitz; doc=fitz.open('/tmp/target.pdf'); [print(f'=== p{i+1} ===\n{p.get_text()}') for i,p in enumerate(doc) if p.get_text().strip()]"
```
