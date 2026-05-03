# Docker / Ollama まわりのデバッグ・トラブルシュートメモ（2026-04-19）

CPU・Docker で動かすときの **障害の切り分け** 用です。変更の経緯（いつ何のために直したか）は **`../updates/2026-04-19-from-initial-to-current.md`** を参照。

---

## `output` が消せない（`Device or resource busy`）

- **原因**: Compose で `../output:/app/output` とバインドマウントしていると、マウント先ディレクトリ自体は `rmtree` できない（errno 16）。
- **対応**: `main.py` の `clear_output_directory()` が、該当時は **ディレクトリ内のファイル・サブディレクトリだけ**削除する。

---

## Ollama が遅い／`Read timed out`／`POST /api/generate` が 500

- **原因**: Docker 内 **CPU 推論**では 1 回の生成に数分かかることがある。クライアントの読み取りタイムアウトが短いと先に切れ、Ollama 側は「クライアントが接続を閉じた」とログすることがある。
- **対応**: `ollama_client` で `request_timeout`（設定値）を `requests` の read timeout に渡す。`docker/config.docker.yaml` では長め（例: 1200 秒）を指定可能。
- **付随**: `num_ctx` を YAML から渡して KV 縮小、`max_tokens` を抑える、`num_agents` / `duration` を減らして呼び出し回数を抑える。

---

## モデルが無い（`llama3.2:1b` not found など）

- **原因**: ホストで `ollama pull` しても **Docker 用 Ollama コンテナのストレージとは別**。
- **対応**: `docker compose ... exec ollama ollama pull <モデル名>`。`main.py` のチェック失敗時ログにも案内を出す。

---

## ログまわり（切り分けのための追加）

- `simulation`: ステップ開始・終了、memory_reasoning 書き込み。
- `ollama_client`: `generate` の開始／成功所要時間／HTTP エラー時の本文スニペット。
- `main`: 起動時にモデル名・`max_tokens`・`request_timeout`・`num_ctx` を表示。

---

## 実行パターン（参考）

| パターン | 構成 | `llm.base_url` の例 |
|----------|------|---------------------|
| A | Ollama のみ Docker（またはホスト）、**シミュレーションはホスト Python** | `http://127.0.0.1:11434` |
| B | Ollama とシミュレーションを **両方 Compose** | `http://ollama:11434` |

---

## Docker 用デフォルト負荷（`docker/config.docker.yaml`）

- **試験・スモーク**：`duration` を短く・`num_agents: 1`・`max_tokens` を小さく・`num_ctx: 512`・プロンプト関連（`memory_size` 等）を抑え・**フレーム保存オフ**。Compose の `command` から **`--save-frames` を外す**と PNG 生成もスキップ。**1 回あたりの数十秒〜数分は Docker 内 CPU の限界**になりやすく、`max_tokens` を下げても劇的には縮まらないことがある。
- **じっくり試す**：`duration` / `num_agents` を増やし、必要なら `--save-frames` を compose に付け直す。
- **`docker/config.docker.yaml` を変えたあとは**、`docker/Dockerfile` でビルドした `simulation` イメージを **再ビルド**する。
