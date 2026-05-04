# 主要指標・リスク内訳の見方（設計メモ）

デモ UI 左カラムに表示する数値の意味。**ソース・オブ・トゥルース**は `apps/demo_web/risk_simulator.py` の `metrics()`。

ユーザー向けの読み物は **`/static/guide/`** 配下を参照し、設計メモと齟齬が出ないよう同期する。

| 正式URL | 内容 |
|--------|------|
| `/static/guide/index.html` | 目次 |
| `/static/guide/about.html` | デモについて |
| `/static/guide/usage.html` | 操作と引率 |
| `/static/guide/metrics.html` | 主要指標 |
| `/static/guide/breakdown.html` | 客観リスク内訳 |
| `/static/guide/state-flags.html` | 状態フラグ（判断用） |
| `/static/guide/subjective.html` | 主観リスク（LLM エージェント） |
| `/static/guide/simulator.html` | シミュレーターパターン |
| `/static/guide/legacy.html` | ハッシュ付きリンク互換（`#main-metrics` → `metrics.html` 等へ振り分け） |

---

## 主要指標（カード 6 枚）

| 表示名 | キー | 意味 |
|--------|------|------|
| 客観リスク | `R_obj` | 環境・人・時間プレッシャーを重み付き合成した **客観側リスク**（0〜1 にクリップ）。 |
| 主観リスク | `R_subj` | 過信バイアスにより **R_obj より低め**に見える側のリスク（`R_obj - bias` ベース、0〜1）。 |
| ギャップ | `Gap` | `R_obj - R_subj`。客観と主観のずれ。 |
| 閾値 | `T` | 設計書の閾値 **T**（ルール判定に使用）。 |
| 中止コスト | `Cost_stop` | ここで止める／引き返すことの「心理的・状況的コスト」を 0〜1 で表したモデル値。 |
| 過信バイアス | `bias` | 主観が客観より楽観になる度合いのパラメータ。 |

---

## リスク内訳パネル

### 合成（テーマ平均）

`breakdown` の 3 値。各入力テーマをグループ化した平均で、`R_obj` の合成に使われる構成要素の見える化。

### 環境リスク（入力）

| キー | 意味 |
|------|------|
| `weather` | 天候系 |
| `visibility` | 視界 |
| `temp_risk` | 気温関連リスク |

### 人（入力）

| キー | 意味 |
|------|------|
| `fatigue` | 疲労 |
| `attention_loss` | 注意散漫 |

### 圧力（入力）

| キー | 意味 |
|------|------|
| `time` | 時間プレッシャー（`time_pressure` と同系列） |
| `external` | 外部からのプレッシャー |

### フラグ

| キー | 意味 |
|------|------|
| `continue_rule_holds` | 設計書の続行／中止ルールに対応する条件が **成立しているか**（真偽）。 |
| `gap_danger` | `Gap ≥ 0.2` として「要注意」とみなすフラグ。 |

---

## 関連

- 全体設計: `high_level_design_v2.md`
- ロールプレイ地名: `rp_simulation.md`
