# work_support

個人の営業活動を支援するためのAIサポートチーム。WEB上の公開情報を整理する。

## フェーズ1：防災 × 予算/議事録分析

防災領域に特化し、自治体の **予算資料** と **議会議事録** を収集・分析して、
営業の「攻めどころ」を導く専門エージェントチーム。対象自治体は実行時に指定する汎用設計。

### 構成（収集／分析／検証を分離した6エージェント）

| エージェント | 役割 |
|---|---|
| `director` | 調査計画(リサーチプラン)を立てる |
| `collector-budget` | 防災予算を出典付きで収集 |
| `collector-minutes` | 議会の防災関連発言を出典付きで収集 |
| `analyst-budget` | 予算から案件化の兆候を分析 |
| `analyst-needs` | 議事録から課題・切り口・キーパーソンを分析 |
| `qa-editor` | 検証し営業向けレポートに統合 |

詳細は [`docs/architecture.md`](docs/architecture.md) を参照。

### 使い方

メインセッションに対して、例えば次のように依頼する:

> 「○○市の防災について調査して。まず director で計画を立てて、その計画どおりに
>  各エージェントを順に動かし、最後にレポートを作って。」

成果物は `workspace/<自治体名>/` に保存される。

### ダッシュボード（GitHub Pages）

`workspace/` 配下の全自治体レポートを横断閲覧できる静的ダッシュボードを提供。

```bash
python tools/build_dashboard.py
# → docs/index.html を再生成
```

**GitHub Pages の有効化手順:**

1. リポジトリの **Settings → Pages** を開く。
2. **Source** を `Deploy from a branch` に設定。
3. **Branch** を `claude/blissful-planck-lsvFa`（または main にマージ後は `main`）、フォルダを `/docs` に設定して Save。
4. 数分後に表示される URL でアクセス可能になる。

> 新しい自治体のレポートを追加したら `python tools/build_dashboard.py` を実行して
> `docs/index.html` をコミット・プッシュすることでダッシュボードが更新される。

### ロードマップ

- フェーズ2: 入札公告クローラー・入札過去実績・入札傾向分析を追加
- フェーズ3: 競合分析・コンサル比較を追加、対象分野を拡張
