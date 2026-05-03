# プロジェクト要点と実行ガイド

開発エージェント・自分用メモ向け。**依存関係**は **`apps/demo_web/requirements.txt`**（デモ Web）。サンプル CLI はローカルの **`sample/requirements.txt`**（Git 管理外）。Docker は **`[docker/Dockerfile.web](../docker/Dockerfile.web)`** と **`[docker/docker-compose.yml](../docker/docker-compose.yml)`**（FastAPI デモのみ）。

---

## このプロジェクトは何をするか（現在のリポジトリ）

- **メイン**: **`apps/demo_web`** で **RiskSimulator**（客観／主観リスク・Gap 等）と分岐をブラウザから操作。**LLM** はホストの Ollama に問い合わせ、介入説明文などを返す（任意）。
- **ログ**: `POST /api/log_run` で **`demo_runs.jsonl`** に追記。既定はリポジトリ直下の **`output/`**（ホスト・Docker とも同じ。Compose では `../output:/app/output` と `DEMO_OUTPUT_DIR=/app/output`）。
- **参考実装**: ローカルの **`sample/multi_place_sim`**（2D・火災マルチエージェント CLI）は Git 対象外。必要な人のみ README に従って利用。

詳細な要件モデルは **[docs/design/high_level_design_v2.md](design/high_level_design_v2.md)**、全体説明は **[README.md](../README.md)**。

---

## docker/ の構成

| ファイル | 役割 |
|----------|------|
| **[docker/docker-compose.yml](../docker/docker-compose.yml)** | **`web`** のみ。デモ UI **[http://localhost:8765](http://localhost:8765)**。LLM は **ホストの Ollama**（`OLLAMA_BASE_URL`）。出力は **`../output:/app/output`**。 |
| **[docker/Dockerfile.web](../docker/Dockerfile.web)** | `apps/demo_web` を uvicorn で起動するイメージ。 |

---

## MacBook Pro（M1）・16GB で試すときのモデル（デモ Web）

Apple Silicon では **ホストの Ollama（Metal）** が速くなりやすい。Compose の **`OLLAMA_MODEL`**（既定例 `llama3.2:1b`）に合わせてホストで `ollama pull` する。

| 狙い | 例（タグは [Ollama Library](https://ollama.com/library) で確認） |
|------|----------------------------------------------------------------------------------|
| **負荷低め** | `llama3.2:1b` |
| **バランス** | `llama3.2:3b`、`qwen2.5:3b` など |
| **避けがち** | **7B 超** — メモリ・待ち時間が厳しいことがある |

---

## Docker（ホスト Ollama）

**web** コンテナからホストの Ollama へは **`host.docker.internal:11434`**（Compose の `extra_hosts` と [Docker のホスト接続](https://docs.docker.com/desktop/features/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host)）。

### 手順

1. **Ollama をホストにインストール・起動** … [Ollama のダウンロード](https://ollama.com/download)
2. **モデルをホストに取得** … `docker-compose.yml` の `OLLAMA_MODEL` と揃える（例: `ollama pull llama3.2:1b`）
3. **ビルド・起動**（リポジトリルート）  
   `docker compose -f docker/docker-compose.yml build`  
   `docker compose -f docker/docker-compose.yml up`  
4. ブラウザで **http://localhost:8765**

**コード変更**: `apps/demo_web` はボリュームマウント＋`uvicorn --reload` のため、**Python/HTML/CSS の変更は再ビルド不要**（保存でリロード）。**再ビルドが主に必要なのは** `apps/demo_web/requirements.txt` や **Dockerfile.web** を変えたとき。

### パターン整理

| | 構成 | Ollama の URL の目安 |
|---|------|------------------------|
| **Docker（本リポジトリ）** | **web** のみコンテナ、**Ollama はホスト** | `http://host.docker.internal:11434`（環境変数 `OLLAMA_BASE_URL`） |
| **ホストのみ** | Python も Ollama もホスト | `http://127.0.0.1:11434` |

---

## ホストだけで動かす（デモ Web）

```bash
pip install -r apps/demo_web/requirements.txt
cd apps/demo_web
uvicorn app:app --reload --host 127.0.0.1 --port 8765
```

サンプル CLI（`sample/` に置いた場合）は README の「ローカルの sample」を参照。便利スクリプトは **`scripts/setup_mac.sh`**。

---

## 出力・トラブル・変更履歴

| 種別 | 参照先 |
|------|--------|
| 結果ファイル・後処理 | [README.md](../README.md) |
| Docker / Ollama の障害切り分け（過去の 2D シミュ観点を含む） | [docs/debug/2026-04-19-docker-ollama.md](debug/2026-04-19-docker-ollama.md) |
| 変更の経緯 | [docs/updates/2026-04-19-from-initial-to-current.md](updates/2026-04-19-from-initial-to-current.md) |

**最低限の確認**: `OLLAMA_BASE_URL` に HTTP で届くか、使うモデルが **ホストの** `ollama list` にあるか。

---

## 公式参照（一次情報）

| 内容 | リンク |
|------|--------|
| Ollama の入手（macOS 等） | [ollama.com/download](https://ollama.com/download) |
| Ollama の使い方・CLI（README） | [GitHub: ollama/ollama — README](https://github.com/ollama/ollama/blob/main/README.md) |
| Ollama イメージ・例 | [Docker Hub: ollama/ollama](https://hub.docker.com/r/ollama/ollama) |
| モデル一覧 | [Ollama Library](https://ollama.com/library) |
| コンテナからホストのサービスへ接続（`host.docker.internal`） | [Docker Docs — Networking（Desktop）](https://docs.docker.com/desktop/features/networking/#i-want-to-connect-from-a-container-to-a-service-on-the-host) |
| `--add-host=host.docker.internal:host-gateway`（Linux 等） | [Docker Docs — docker run](https://docs.docker.com/engine/reference/commandline/run/#add-host) |
| NVIDIA Container Toolkit（Linux で GPU をコンテナに渡す） | [NVIDIA ドキュメント](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |

---

## このリポジトリ内の参照

| ファイル・ディレクトリ | 内容 |
|------------------------|------|
| [README.md](../README.md) | 仕様・実行の本流 |
| [docker/](../docker/) | **Dockerfile.web**、**docker-compose.yml**（デモ Web のみ） |
| [LICENSE.txt](../LICENSE.txt) | ライセンス |
