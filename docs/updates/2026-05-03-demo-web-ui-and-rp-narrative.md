# demo_web UI とロールプレイナラティブの変更（2026-05 前後）

`apps/demo_web` の静的フロントと、バックエンドの **地名・エンディング連動** を一連で整えた経緯です。

---

## 背景

- Bootstrap 導入後に **3 カラム崩れ**・**文字サイズのばらつき**・**100vh からのはみ出し** が表面化した。
- 「登山」メタファを **背景画像（`static/image/*.jpg`）** と **ピクセルキャラ CSS（`character{1,2,3}.css`）** で表現したいという要望があった。
- 結果メッセージをインラインで出すとレイアウトが伸びるため、**モーダル表示**と**スクロール方針**を整理した。

---

## 主な変更（機能・挙動）

### レイアウト・タイポグラフィ

- **3 カラム**: `container-fluid` + `col-lg-3` / `col-lg-5` / `col-lg-4`（主要指標・内訳／グラフ・登山／判断・引率・チャット）。
- **主要指標**: 日本語ラベル + 変数名（`metric-heading` / `metric-ja` / `metric-code`）。
- **ヘッダー**: 説明文と **「i」ボタン** → **`#demoInfoModal`**（デモ説明）。
- **タイポ**: `body` ベース `0.875rem` 周りでボタン・凡例・内訳などを揃えた。

### パーティ登山（可視化）

- SVG の **雲・道を削除**。背景は **`#trail-bg` の `background-image`**、危険度は **`#trail-veil`（div + opacity）**。
- **`character*.css`** の `.dot-1`〜`.dot-3` を配置し、**1・2 を約 1.7 倍**、**三角形隊形（上・右・左）** + 進捗に応じた **円運動**。
- 縦位置調整用に **`PARTY_DROP_Y`**（JS 定数）あり。

### バックエンド連動（`risk_simulator.py`）

- **`rp_zone()`** とスナップショットの **`rp_zone`**（`yama` / `mori` / `kouya` / `home` / `mori_yoru` / `umi`）。
- **`decide_continue`**: 危険側は **`accident`**、それ以外は **`cleared`**（海ゴール）。中止は従来どおり **`avoided`**。
- 設計の整理: **`docs/design/rp_simulation.md`**。

### リスク内訳・結果表示・右カラム

- **内訳**: テーマ平均に加え **`env` / `human` / `pressure`** の各入力と **`continue_rule_holds` / `gap_danger`** を **`renderBreakdown()`** で表形式表示。
- **結果**: 中央の **`#banner` は廃止**。**`#outcomeModal`** で表示（キー重複でモーダル連打を抑制）。
- **右カラム**: 「続行／中止」を **上部カード**へ移動。**エージェントチャット**・**LLM** は **固定の高さ枠 + 内部スクロール**（外側の `.chat-stack--scroll` は縦スクロールしない方針）。

### レイアウト安定化（はみ出し対策）

- **トレイル枠**: **`aspect-ratio: 400 / 110`** と **`max-height`** で、画像差やモーダル時の reflow で縦に伸びすぎないようにした。
- **`trail-box` の過剰 flex 成長**をやめ、ページ全体は **`html` / `body` で縦スクロール可能**（`app-layout` の `100vh` + `overflow:hidden` をやめる）。
- 静的アセットはキャッシュ対策で **`?v=rp-v6`** などクエリを付与（運用上はリリース単位で更新でよい）。

---

## 関連パス

| 種別 | パス |
|------|------|
| 画面 | `apps/demo_web/static/index.html` |
| スタイル | `apps/demo_web/static/css/demo.css` |
| フロントロジック | `apps/demo_web/static/js/demo.js` |
| シミュレータ | `apps/demo_web/risk_simulator.py` |
| RP ナラティブ設計 | `docs/design/rp_simulation.md` |

---

## このあと読むなら

- アプリ全体の配置: **`docs/PROJECT_LAYOUT.md`**
- エージェント運用メモ: **`docs/CLAUDE.md`**
