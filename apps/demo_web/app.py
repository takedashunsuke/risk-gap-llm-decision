"""
設計書 v2 向けデモ Web。localhost で数値シミュレーションと分岐を表示する。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from risk_simulator import RiskSimulator, new_simulator

app = FastAPI(title="Risk decision demo", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
# 既定: リポジトリルートの output/（Docker の ../output:/app/output と一致）
_OUTPUT_DEFAULT = Path(__file__).resolve().parent.parent.parent / "output"
OUTPUT_DIR = Path(os.environ.get("DEMO_OUTPUT_DIR", str(_OUTPUT_DEFAULT)))
RUN_LOG = OUTPUT_DIR / "demo_runs.jsonl"

_sim: RiskSimulator = new_simulator()


class DecideBody(BaseModel):
    choice: str  # "continue" | "llm_stop"


class ResetBody(BaseModel):
    max_steps: int = 40


def _ollama_generate(prompt: str) -> Optional[str]:
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    url = f"{base}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 220},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()
    except Exception:
        return None


@app.get("/api/state")
def get_state() -> Dict[str, Any]:
    return _sim.snapshot()


@app.post("/api/reset")
def reset(body: ResetBody = ResetBody()) -> Dict[str, Any]:
    global _sim
    _sim = new_simulator(max_steps=body.max_steps)
    return _sim.snapshot()


@app.post("/api/advance")
def advance() -> Dict[str, Any]:
    return _sim.advance()


@app.post("/api/decide")
def decide(body: DecideBody) -> Dict[str, Any]:
    if body.choice == "continue":
        snap = _sim.decide_continue()
    elif body.choice == "llm_stop":
        snap = _sim.decide_llm_stop()
    else:
        raise HTTPException(status_code=400, detail="choice must be continue or llm_stop")

    text: Optional[str] = None
    if body.choice == "llm_stop" and snap.get("outcome") == "avoided":
        m = snap.get("metrics") or {}
        prompt = (
            "あなたは安全管理のコーチです。次の数値は固定事実として扱い、数値を捏造しないでください。\n"
            f"Objective Risk R_obj={m.get('R_obj')}, Perceived Risk R_subj={m.get('R_subj')}, "
            f"Gap={m.get('Gap')}（客観と主観の差）。Cost_stop={m.get('Cost_stop')}。\n"
            "日本語で3〜5文。過信（Gap）を指摘し、中止（引き返し）を勧める短文。\n"
        )
        text = _ollama_generate(prompt)

    snap["llm_message"] = text
    return snap


@app.post("/api/log_run")
def log_run(payload: Dict[str, Any]) -> Dict[str, str]:
    """任意: 実行サマリを JSONL に追記（DBなしで記録する用途）。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"status": "ok", "path": str(RUN_LOG)}


app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="index.html missing")
    return FileResponse(index_path)
