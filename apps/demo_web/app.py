"""
設計書 v2 向けデモ Web。localhost で数値シミュレーションと分岐を表示する。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

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

DEFAULT_GUIDE_PERSONALITY = (
    "経験が豊富で安全最優先。隊員の疲労を見て無理に詰めず、適宜休憩を挟むタイプ。"
)


class DecideBody(BaseModel):
    choice: str  # "continue" | "llm_stop"


class ResetBody(BaseModel):
    max_steps: int = 40


def _guide_agent_enabled() -> bool:
    v = os.environ.get("DEMO_GUIDE_AGENT", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _guide_personality() -> str:
    raw = os.environ.get("DEMO_GUIDE_PERSONALITY", "").strip()
    return raw or DEFAULT_GUIDE_PERSONALITY


def _guide_config() -> Dict[str, Any]:
    return {
        "agent_enabled": _guide_agent_enabled(),
        "personality": _guide_personality(),
    }


def _enrich(snap: Dict[str, Any]) -> Dict[str, Any]:
    snap["guide_config"] = _guide_config()
    return snap


def _ollama_generate(
    prompt: str,
    *,
    num_predict: int = 220,
    temperature: float = 0.3,
) -> Optional[str]:
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    url = f"{base}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()
    except Exception:
        return None


def _parse_guide_json(text: str) -> Optional[Tuple[Literal["trek", "rest"], str]]:
    if not text:
        return None
    t = text.strip()
    candidates = [t]
    if "{" in t:
        candidates.append(t[t.find("{") :])
    for chunk in candidates:
        start = chunk.find("{")
        end = chunk.rfind("}")
        if start < 0 or end <= start:
            continue
        blob = chunk[start : end + 1]
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        act = str(obj.get("action", "")).lower().strip()
        if act in ("trek", "rest"):
            reason = str(obj.get("reasoning", "") or "").strip()
            if not reason:
                reason = "（理由の記述なし）"
            return act, reason  # type: ignore[return-value]
    # action: trek のような行だけ拾う
    m = re.search(
        r'"action"\s*:\s*"(trek|rest)"',
        t,
        re.I,
    )
    if m:
        act = m.group(1).lower()
        if act in ("trek", "rest"):
            rm = re.search(r'"reasoning"\s*:\s*"([^"]*)"', t)
            reason = rm.group(1) if rm else "（理由を抽出できませんでした）"
            return act, reason  # type: ignore[return-value]
    return None


def _fallback_step_kind(sim: RiskSimulator) -> Literal["trek", "rest"]:
    next_step = sim.step + 1
    is_rest = next_step > 0 and next_step % 6 == 0
    return "rest" if is_rest else "trek"


def _ollama_guide_plan_next_step(sim: RiskSimulator, personality: str) -> Tuple[Literal["trek", "rest"], str]:
    """次の1ステップを trek / rest で選ばせる。失敗時は従来と同じ 6 ステップ周期にフォールバック。"""
    m = sim.metrics()
    br = m.get("breakdown") or {}
    envo = m.get("env") or {}
    hum = m.get("human") or {}
    pr = m.get("pressure") or {}
    prompt = (
        "あなたは登山パーティの引率者です。次の「引率者の人格」に従い、この直後の1ステップだけ"
        "「trek」（登行・移動を続ける）か「rest」（休憩してリカバリ）かを選んでください。\n\n"
        f"【引率者の人格（環境変数 DEMO_GUIDE_PERSONALITY）】\n{personality}\n\n"
        "【現在の状態（数値は事実。捏造しない）】\n"
        f"- ステップ: {sim.step} / {sim.max_steps}（まだ「次のステップ」を踏む前）\n"
        f"- R_obj={m.get('R_obj')}, R_subj={m.get('R_subj')}, Gap={m.get('Gap')}, "
        f"Cost_stop={m.get('Cost_stop')}, bias={m.get('bias')}\n"
        f"- 環境平均={br.get('environment_avg')}, 人平均={br.get('human_avg')}, 時間圧={br.get('time_pressure')}\n"
        f"- 天候={envo.get('weather')}, 視界={envo.get('visibility')}, 気温リスク={envo.get('temp_risk')}\n"
        f"- 疲労={hum.get('fatigue')}, 注意散漫={hum.get('attention_loss')}\n"
        f"- 時間プレッシャー={pr.get('time')}, 外部圧={pr.get('external')}\n\n"
        "【出力】JSON のみ。キーは action と reasoning の2つ。\n"
        '- action は文字列 "trek" または "rest"。\n'
        "- reasoning は日本語で短く（120文字以内）、この1ステップの判断理由。\n\n"
        '例: {"action":"rest","reasoning":"視界と疲労が気になるので岩場手前で短く休憩する。"}\n'
    )
    raw = _ollama_generate(prompt, num_predict=380, temperature=0.35)
    parsed = _parse_guide_json(raw or "")
    if parsed:
        return parsed
    fb = _fallback_step_kind(sim)
    hint = (
        "Ollama から有効な JSON が得られなかったため、既定ルール（6ステップごとに休憩）で進めます。"
        if not raw
        else "モデル応答を JSON として解釈できなかったため、既定ルールで進めます。"
    )
    return fb, hint


@app.get("/api/state")
def get_state() -> Dict[str, Any]:
    return _enrich(_sim.snapshot())


@app.post("/api/reset")
def reset(body: ResetBody = ResetBody()) -> Dict[str, Any]:
    global _sim
    _sim = new_simulator(max_steps=body.max_steps)
    return _enrich(_sim.snapshot())


@app.post("/api/advance")
def advance() -> Dict[str, Any]:
    chat_entry: Optional[Dict[str, Any]] = None
    step_override: Optional[Literal["trek", "rest"]] = None

    if (
        _guide_agent_enabled()
        and _sim.phase == "running"
        and _sim.step < _sim.max_steps
    ):
        action, reasoning = _ollama_guide_plan_next_step(_sim, _guide_personality())
        step_override = action
        chat_entry = {
            "role": "assistant",
            "kind": "guide",
            "content": reasoning,
            "action": action,
        }

    snap = _sim.advance(
        step_kind=step_override if _guide_agent_enabled() else None,
        chat_entry=chat_entry if _guide_agent_enabled() else None,
    )
    return _enrich(snap)


@app.post("/api/decide")
def decide(body: DecideBody) -> Dict[str, Any]:
    text: Optional[str] = None
    if body.choice == "continue":
        snap = _sim.decide_continue()
    elif body.choice == "llm_stop":
        snap = _sim.decide_llm_stop()
        if snap.get("outcome") == "avoided":
            m = snap.get("metrics") or {}
            prompt = (
                "あなたは安全管理のコーチです。次の数値は固定事実として扱い、数値を捏造しないでください。\n"
                f"Objective Risk R_obj={m.get('R_obj')}, Perceived Risk R_subj={m.get('R_subj')}, "
                f"Gap={m.get('Gap')}（客観と主観の差）。Cost_stop={m.get('Cost_stop')}。\n"
                "日本語で3〜5文。過信（Gap）を指摘し、中止（引き返し）を勧める短文。\n"
            )
            text = _ollama_generate(prompt)
            _sim.append_guide_chat(
                {
                    "role": "assistant",
                    "kind": "coach",
                    "step": snap.get("step"),
                    "content": text
                    or "Ollama からの応答がありませんでした。数値と分岐はそのまま有効です。",
                }
            )
            snap = _sim.snapshot()
    else:
        raise HTTPException(status_code=400, detail="choice must be continue or llm_stop")

    snap["llm_message"] = text
    return _enrich(snap)


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
