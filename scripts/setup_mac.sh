#!/bin/bash
# リポジトリルートで venv を作成。デモ Web は必須。sample/ はローカルにあればその依存も入れる。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv venv
# shellcheck disable=1091
source venv/bin/activate
pip install --upgrade pip
pip install -r apps/demo_web/requirements.txt
if [[ -f sample/requirements.txt ]]; then
  pip install -r sample/requirements.txt
  pip install -e sample/
fi

echo ""
echo "セットアップ完了。"
echo "  venv: source venv/bin/activate"
echo "  Web:  cd apps/demo_web && uvicorn app:app --reload --host 127.0.0.1 --port 8765"
if [[ -d sample/multi_place_sim ]]; then
  echo "  sample CLI: python -m multi_place_sim"
fi
echo ""
