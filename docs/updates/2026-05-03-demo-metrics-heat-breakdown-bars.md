# demo_web：主要指標の段階色・リスク内訳バー（2026-05 前後）

主要指標カードをリスクの目安で **黄／赤** にし、リスク内訳を **0〜1 の横バー** で比較しやすくした変更です。

---

## 背景

- 数値だけでは「今どこが効いているか」が把握しづらいという課題があった。
- 内訳パネルは項目が多く、スケール（0〜1）の読み取りに負荷があった。

---

## 主な変更

### 主要指標カード（`demo.js` / `demo.css`）

- **`metricCardSeverityClass`** を追加。指標ごとに **warn（黄系）** と **danger（赤系）** のクラスを付与。
  - 例: **R_obj** は約 0.28 以上で warn、約 0.4 以上で danger。**Gap** は約 0.1 / 0.2 付近、**T** は **R_obj** と **T** の比率で「閾値接近」を表現、など。
- `.metric-card--warn` / `.metric-card--danger` で背景グラデ・枠線・数値色を変更（トランジションあり）。

### リスク内訳パネル（`demo.js` / `demo.css`）

- 数値行を **`breakdownBarRow`** に変更。**バーの長さ ≒ 値（0〜1）**。
- **バー色の三段**: 灰（低め）／黄系（中）／赤系（高め）。主要指標カードの閾値とは別の「大小」の目安。
- 先頭に **凡例**（`bd-legend`）。合成・環境・人・圧力のラベルを補足文言で整理。
- フラグ行は従来どおり「はい／いいえ」のみ。

### ドキュメント・キャッシュ

- **`demo-guide.html`**: `#main-metrics` にカード色の説明、`#breakdown` にバー・構成の読み方を追記。
- **`index.html`**: `demo.css` のクエリを **`?v=rp-v16`** に更新。

---

## 関連パス

| 種別 | パス |
|------|------|
| ロジック | `apps/demo_web/static/js/demo.js` |
| スタイル | `apps/demo_web/static/css/demo.css` |
| デモ説明 | `apps/demo_web/static/demo-guide.html` |
| エントリ | `apps/demo_web/static/index.html` |

---

## 関連する過去メモ

- チャット枠の高さ調整など UI 微調整が続く場合は、同時期の `demo.css` の `.agent-chat-scroll` / `.llm-panel-scroll` も参照。
