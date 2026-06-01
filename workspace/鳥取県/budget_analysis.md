# 予算分析: 鳥取県 / 防災

- 分析日: 2026-06-01
- 根拠ファイル: budget_raw.md（収集日 2026-06-01）

## 判定: 分析不能（収集データ不足）

根拠ファイル budget_raw.md に、出典付きで確定した防災関連費目が **0件** のため、
analyst-budget の鉄則（一次情報のみで分析・推測の混入禁止）に従い、分析を行わない。

## 不足の原因（収集役の報告より）
- 実行環境から鳥取県公式ドメイン（pref.tottori.lg.jp 等）および外部PDF全般へ
  WebFetch が HTTP 403 となり、予算書本文・金額を取得できなかった。

## 必要な追加収集（collector-budget への依頼）
- WebFetch が機能する環境で、下記を起点に防災関連事業名・金額・年度を取得:
  - 令和7年度当初予算: https://www.pref.tottori.lg.jp/321465.htm
  - 令和7年度予算公開DB: https://db.pref.tottori.jp/yosan/R7Yosan_Koukai.nsf/index.htm
  - 令和6年度当初予算（推移用）: https://www.pref.tottori.lg.jp/313023.htm
