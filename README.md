# risk-gap-llm-decision

**客観リスクと主観認識のギャップ（Risk Gap）**、および「止まれない意思決定の力学」を扱うためのリポジトリです。設計の全体像は **[docs/design/high_level_design_v2.md](docs/design/high_level_design_v2.md)** を参照してください。

## リポジトリの置き方

- **ルート直下のファイル**は、基本 **`README.md`・`LICENSE.txt`・`.gitignore` のみ**を想定しています（`requirements.txt` は置きません）。
- **`sample/` ディレクトリは `.gitignore` によりリポジトリに含めません。** 2D マルチエージェントの参考実験用コードなどは、各自ローカルで配置してください。
- ソースは **`apps/demo_web/`**（FastAPI デモ）、**`docker/`**、**`docs/`**、セットアップ補助は **`scripts/`** に分かれています。

---

## このプロジェクトの中心

| 位置づけ | 説明 |
|---------|------|
| **メイン** | **`apps/demo_web/`** … FastAPI、ブラウザ UI、`risk_simulator.py`（数値シミュ）、ホストの **Ollama**（説明文生成）。 |
| **参考実装（ローカルのみ）** | **`sample/multi_place_sim/`** … 別プロセスの CLI 実験用。**Git にはコミットせず**、必要な人だけローカルで保持します。 |

---

## 前提環境

- **Python 3.11 以上**
- **Ollama**（デモの LLM 説明文用。数値シミュだけなら未起動でも可）
- ブラウザ

---

## セットアップと起動（メイン: デモ Web）

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r apps/demo_web/requirements.txt

cd apps/demo_web
uvicorn app:app --reload --host 127.0.0.1 --port 8765
```

**http://127.0.0.1:8765** を開きます。

ショートカットは **`scripts/setup_mac.sh`** / **`scripts/setup_win.bat`**（上記に加え、ローカルに **`sample/requirements.txt`** があるときだけサンプル依存もインストール）。

### 環境変数（任意）

| 変数 | 説明 |
|------|------|
| `OLLAMA_BASE_URL` | 既定 `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | 既定 `llama3.2` |
| `DEMO_OUTPUT_DIR` | `demo_runs.jsonl` の出力先（未設定時はリポジトリ直下の **`output/`**） |

### HTTP API（概要）

| メソッド | パス | 説明 |
|---------|------|------|
| `GET` | `/` | 静的 UI |
| `GET` | `/api/state` | 状態取得 |
| `POST` | `/api/reset` | リセット |
| `POST` | `/api/advance` | 1 ステップ進行 |
| `POST` | `/api/decide` | `continue` / `llm_stop` |
| `POST` | `/api/log_run` | JSONL へ追記 |

詳細は **[apps/demo_web/app.py](apps/demo_web/app.py)**。

---

## Docker

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up
```

- **デモ Web**: **http://localhost:8765**
- ログ（`demo_runs.jsonl`）はホストの **`output/`** とコンテナの **`/app/output`** をボリュームで同期します。

詳細は **[docs/CLAUDE.md](docs/CLAUDE.md)**。

---

## ローカルの `sample/`（任意）

Git に含めない **`sample/`** に、`multi_place_sim` パッケージや `requirements.txt`・`pyproject.toml` を置いた場合の例:

```bash
pip install -r sample/requirements.txt
pip install -e sample/
python -m multi_place_sim
```

出力・設定の既定パスは **`sample/multi_place_sim/`** 配下です（パッケージ実装の前提）。

---

## ドキュメント

| 文書 | 内容 |
|------|------|
| [docs/design/high_level_design_v2.md](docs/design/high_level_design_v2.md) | 要件・モデル |
| [docs/CLAUDE.md](docs/CLAUDE.md) | Docker・運用メモ |
| [docs/PROJECT_LAYOUT.md](docs/PROJECT_LAYOUT.md) | ディレクトリ説明 |

---

## ライセンス

GNU General Public License v3.0 — [LICENSE.txt](LICENSE.txt)
