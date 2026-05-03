# demo_web：デモ説明・引率人格・パーティチャットなど（2026-05 前後）

主要指標の読み物整理から、**引率人格の選択**・**Ollama 引率の UI トグル**・**パーティ三人のチャット**までを一連で入れた経緯です。

---

## 背景

- 主要指標・リスク内訳の意味を **別ページで読める**ようにしたいという要望があった。
- **引率エージェント**を環境変数だけでなく **画面上で ON/OFF** したい、かつ **人格とシミュ初期値をセットで選びたい**という要望があった。
- **チャットが引率のみ**ではなく、登山パーティの **三人の掛け合い**として見せたいという要望があった。

---

## 主な変更（機能・挙動）

### デモ説明・ヘルプページ

- **`/static/demo-guide.html`** に **デモ概要・操作と引率・主要指標・リスク内訳** を一括記載。ページ内ナビあり。
- **`/static/metrics-guide.html`** は **`demo-guide.html` + ハッシュ維持でリダイレクト**（旧リンク互換）。
- **ヘッダー右上**に **「デモ使用説明」**（別タブ・リンク強調）。左カラムの個別「説明」リンクと **`#demoInfoModal` は廃止**（内容は `demo-guide` に集約）。
- 設計メモ **`docs/design/metrics_and_breakdown_guide.md`** のユーザー向け参照先を `demo-guide.html` に更新。

### 引率人格・シミュ初期値・Ollama トグル

- **`GUIDE_PERSONAS`**（複数プリセット）と **`POST /api/guide_persona`**、起動時 **`DEMO_GUIDE_PERSONA_ID`**。
- **`new_simulator(..., **overrides)`** でプリセットに応じた **`RiskSimulator` 初期フィールド**を上書き。**リセット時**に数値へ反映。
- **`_guide_agent_ui`** と **`POST /api/guide_agent`** で **`DEMO_GUIDE_AGENT` 相当を画面から切替**（プロセス内で保持。起動時は環境変数が初期値）。
- カード見出しを **「引率人格選択」**。ドロップダウン下は **概要（description）と LLM 用全文（personality）を 1 ブロック**に統合。
- 見出し行に **Ollama スイッチ**、長い脚注は `demo-guide` へ集約の方針。

### パーティチャット（三人）

- 各 **`advance`** で **`chat_entries`**（最大 3 件）を **`RiskSimulator.advance`** から追加。
- **引率・朔**（Ollama ON 時は LLM の `reasoning`、OFF 時は定型）、**隊員・遥・隊員・楓**（状態に応じた短文ルール）。
- チャット UI：**話者名**・**役ごとの左ボーダー色**。見出しは **「パーティチャット」** など。中止時は **中止コーチ** に `speaker_label`。
- フロントは **`kind: party` / `speaker` / `speaker_label`** を解釈。

### UI の細部（抜粋）

- **最終判断**ブロックを **中央カラム**（登山ブロック直下）へ移動。
- **エージェントチャット**見出しを **1 行化**、サブ文言のフォント縮小。**最終判断**の注記も小さめ。
- **引率カード**見出し行の短縮、**「プリセット」表記の撤去**（`aria-label` で補足）。

### ドキュメント・Docker

- **`docker-compose.yml`** コメントに `DEMO_GUIDE_PERSONA_ID` / 引率トグルの説明を追記。
- **`demo-guide.html`** にパーティチャットの挙動を追記。

---

## 関連パス

| 種別 | パス |
|------|------|
| 画面 | `apps/demo_web/static/index.html` |
| デモ説明（静的） | `apps/demo_web/static/demo-guide.html`、旧 URL `static/metrics-guide.html` |
| スタイル | `apps/demo_web/static/css/demo.css` |
| フロント | `apps/demo_web/static/js/demo.js` |
| API・引率・パーティ行生成 | `apps/demo_web/app.py` |
| シミュレータ | `apps/demo_web/risk_simulator.py` |
| 人格・数値プリセット定義 | `app.py` 内 `GUIDE_PERSONAS` |
| 設計（指標） | `docs/design/metrics_and_breakdown_guide.md` |

---

## このあと読むなら

- 地名・エンディング: **`docs/design/rp_simulation.md`**
- 直前の UI・登山・`rp_zone` 整理: **`docs/updates/2026-05-03-demo-web-ui-and-rp-narrative.md`**
