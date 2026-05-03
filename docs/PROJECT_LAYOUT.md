# ディレクトリ構成と整理方針

**メインは `apps/demo_web/`**。ルート直下の **ファイル**は **`README.md`・`LICENSE.txt`・`.gitignore`** を中心に置く想定です。**ルートの `requirements.txt` は置きません**（依存は `apps/demo_web/requirements.txt` など）。

**`sample/` は `.gitignore` で除外**し、2D マルチエージェント等の参考コードは各自ローカルのみで保持します。

---

## レイアウト（概要）

```text
.
├── README.md
├── LICENSE.txt
├── .gitignore
├── apps/
│   └── demo_web/             # FastAPI + RiskSimulator + 静的 UI
├── scripts/                  # setup_mac.sh / setup_win.bat（リポジトリに含む）
├── docker/                   # Dockerfile.web と compose（デモ Web のみ）
├── output/                   # Compose / ログ用（中身は gitignore、.gitkeep のみ追跡）
├── docs/
└── sample/                   # Git では無視（ローカルのみ置く場合がある）
```

---

## 実行の参照先（早見）

| やりたいこと | コマンドの目安 |
|--------------|----------------|
| デモ Web（ホスト） | `pip install -r apps/demo_web/requirements.txt` のあと `cd apps/demo_web && uvicorn ...` |
| セットアップ補助 | `scripts/setup_mac.sh`（Web 必須、`sample/` があれば追加インストール） |
| サンプル 2D CLI | ローカルに `sample/` がある場合のみ `pip install -e sample/` 等 |

詳細は **`docs/CLAUDE.md`**・**README.md**。

---

## DB を用意するか（判断の目安）

デモの記録は **JSONL 追記**で足りるケースが多い。複数ユーザ検索が要るならその時点で **SQLite** 等を検討。方針のフレームは従来どおり（必要なら README の設計文書を参照）。

---

## 今後の整理候補

- デモ UI のフロント分離（Vite 等）
- サンプル 2D を API 化して `apps/demo_web` から呼び出す
