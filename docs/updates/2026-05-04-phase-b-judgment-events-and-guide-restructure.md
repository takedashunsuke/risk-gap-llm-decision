# フェーズB判断イベント化とガイド再編（2026-05-04）

`apps/demo_web` で、フェーズBの判断ロジックとデモ説明導線をまとめて更新した記録です。

---

## 背景

- 旧仕様の「最終判断」は `max_steps` 到達時のみ有効で、状態変化に応じた判断停止ができなかった。
- `step` が 40 を超えて進む場合にグラフが計画上限で見切れる問題があった。
- 説明ページは `static` 直下に散在しており、構成とリンクの保守性が低かった。

---

## 主な変更

### 1) シミュレータ（フェーズB）

- `RiskSimulator` に判断イベント層を拡張。
  - `judgment_trigger_reason` を利用し、`max_steps` 以外にフラグ切替でも判断を発火。
  - 追加 reason:
    - `flag_continue_toggled`
    - `flag_gap_toggled`
    - `flag_both_toggled`
- 判断待ち中は `can_advance = false` とし、手動・自動とも停止。
- 中止方針を変更。
  - `stop`（互換 `llm_stop`）で即 `outcome=avoided` で終了。
  - 同時に `fatigue` / `attention_loss` を各 `-0.1`。
- 続行方針を変更。
  - 続行のたびに `gap_danger_threshold` を `+0.1`（0.2 -> 0.3 -> 0.4 ...）。
  - 早期終了しすぎないよう、続行後の終了条件を緩和。
- 続行ルール式を見直し。
  - `continue_rule_holds = (R_subj + Cost_stop) < T`
  - UI表示式も同じ式に同期。

### 2) UI（判断モーダル）

- 中央カラムを「最終判断」から「判断イベント」へ変更。
- 判断はボタン直押しではなくモーダルで選択。
  - `続行（過信）`
  - `中止`
- `judgment_trigger_reason` に応じてモーダル文言を出し分け。
- LLMラベルを「LLM サポートメッセージ」に変更（判断主体ではなく補助）。

### 3) グラフ表示

- `risk-chart.js` で描画ドメインの扱いを調整し、`step > max_steps` 区間も表示。
- 不要な全再構築を抑え、差分 update 中心の挙動に寄せた。

### 4) 説明ページ再編（`static/guide` 集約）

- ガイドHTMLを `apps/demo_web/static/guide/` 配下に集約し、短い名前に整理。
  - `index.html`, `about.html`, `usage.html`, `metrics.html`, `breakdown.html`,
    `state-flags.html`, `subjective.html`, `simulator.html`, `legacy.html`
- `guide` 内リンクは相対パスで統一。
- 旧 `static` 直下の `demo-guide*.html` / `metrics-guide.html` は削除。
- ヘッダーの説明リンクを `/static/guide/index.html` へ統一。

---

## ドキュメント同期

- `docs/design/rp_simulation.md`
  - 判断トリガと判断後挙動を新方針へ更新。
- `docs/design/rp_ui_and_simulation_vnext.md`
  - 「最終判断」前提を「判断イベント」前提へ更新。
  - Gap 閾値可変・中止即終了・LLM補助の方針を反映。
- `docs/design/metrics_and_breakdown_guide.md`
  - `static/guide` 正式URL群を記載。

---

## 関連パス

| 種別 | パス |
|------|------|
| シミュ本体 | `apps/demo_web/risk_simulator.py` |
| API | `apps/demo_web/app.py` |
| 画面 | `apps/demo_web/static/index.html` |
| フロント | `apps/demo_web/static/js/demo/app.js` |
| フラグ表示 | `apps/demo_web/static/js/demo/metrics-breakdown.js` |
| グラフ | `apps/demo_web/static/js/demo/risk-chart.js` |
| ガイド | `apps/demo_web/static/guide/` |
