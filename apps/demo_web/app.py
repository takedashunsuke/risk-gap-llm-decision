"""
設計書 v2 向けデモ Web。localhost で数値シミュレーションと分岐を表示する。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

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

DEFAULT_GUIDE_PERSONALITY = (
    "経験が豊富で安全最優先。隊員の疲労を見て無理に詰めず、適宜休憩を挟むタイプ。"
)

# 引率プリセット: UI のプルダウンとリセット時のシミュ初期値 + LLM 人格テキスト
# 「sim」は RiskSimulator のフィールドのサブセット（指定したものだけ上書き）
GUIDE_PERSONAS: Dict[str, Dict[str, Any]] = {
    "safety_first": {
        "label": "安全重視・慎重",
        # 実験パターン（Riskモデルの初期値の狙い）: 数値・条件の説明に限定する
        "description": "過信バイアスと中止コストを抑えた出発点。途中で判断が入りやすい条件寄せ。",
        "personality": (
            "経験が豊富で安全最優先。隊員の疲労と視界を細かく見て、"
            "無理に行程を詰めず適宜休憩を挟む。タイトな日程より隊の余裕を選ぶ。"
        ),
        "sim": {
            "bias": 0.08,
            "cost_stop": 0.14,
            "weather": 0.12,
            "visibility": 0.18,
            "fatigue": 0.12,
            "time_pressure": 0.16,
            "external_pressure": 0.12,
        },
    },
    "pace_push": {
        "label": "行程・締切重視",
        "description": "時間圧と外部プレッシャーを高めた出発点。進行が速くなりやすい条件。",
        "personality": (
            "行程表と締切を意識しがちで、少しペースを押し気味。"
            "それでも危険シグナル（視界・疲労の急上昇）が出たら減速はするが、"
            "最初は「まだ行ける」寄りに読みがち。"
        ),
        "sim": {
            "bias": 0.14,
            "cost_stop": 0.2,
            "time_pressure": 0.3,
            "external_pressure": 0.24,
            "weather": 0.14,
            "visibility": 0.19,
            "fatigue": 0.14,
        },
    },
    "optimist": {
        "label": "楽観・実績過信",
        "description": "過信バイアスを高めた出発点。主観が先行しやすくGapが出やすい条件。",
        "personality": (
            "過去の成功体験を信じ「だいたい大丈夫」と読みがち。"
            "隊の余裕はあるが、ギャップが開きやすい楽観ムードを引率に反映する。"
        ),
        "sim": {
            "bias": 0.2,
            "cost_stop": 0.22,
            "weather": 0.13,
            "visibility": 0.16,
            "fatigue": 0.11,
            "attention_loss": 0.09,
        },
    },
    "weather_watch": {
        "label": "天候・視界警戒",
        "description": (
            "環境系の入力（weather / visibility / temp_risk）を高めに置いた出発点。"
            "客観側の初期リスクが積み上がりやすい条件。"
        ),
        "personality": (
            "天候・視界の悪化を敏感に拾い、早めに待機やリカバリを検討する話し方。"
            "数値の意味づけはシミュレーション側の初期条件に合わせる。"
        ),
        "sim": {
            "weather": 0.24,
            "visibility": 0.28,
            "temp_risk": 0.17,
            "fatigue": 0.14,
            "attention_loss": 0.12,
            "time_pressure": 0.18,
            "bias": 0.1,
        },
    },
}


def _initial_guide_persona_id() -> str:
    env_id = os.environ.get("DEMO_GUIDE_PERSONA_ID", "").strip()
    if env_id and env_id in GUIDE_PERSONAS:
        return env_id
    return next(iter(GUIDE_PERSONAS))


_selected_guide_persona_id: str = _initial_guide_persona_id()


def _persona_sim_kw(persona_id: str) -> Dict[str, Any]:
    entry = GUIDE_PERSONAS.get(persona_id) or {}
    sim = entry.get("sim")
    if not isinstance(sim, dict):
        return {}
    return dict(sim)


def _rounded_sim_preset(sim_kw: Dict[str, Any]) -> Dict[str, Any]:
    """UI表示用: persona の sim 上書きを、そのまま読みやすく並べる。"""
    keys = [
        "weather",
        "visibility",
        "temp_risk",
        "fatigue",
        "attention_loss",
        "time_pressure",
        "external_pressure",
        "bias",
        "cost_stop",
        "gap_danger_threshold",
    ]
    out: Dict[str, Any] = {}
    for k in keys:
        if k not in sim_kw:
            continue
        try:
            v = float(sim_kw[k])
        except (TypeError, ValueError):
            continue
        out[k] = round(v, 4)
    return out


def _initial_guide_agent_from_env() -> bool:
    v = os.environ.get("DEMO_GUIDE_AGENT", "").strip().lower()
    return v in ("1", "true", "yes", "on")


# Ollama 引率の ON/OFF（環境変数でプロセス起動時の初期値。画面スイッチで上書き）
_guide_agent_ui: bool = _initial_guide_agent_from_env()


_sim: RiskSimulator = new_simulator(max_steps=40, **_persona_sim_kw(_selected_guide_persona_id))


class DecideBody(BaseModel):
    choice: str  # "continue" | "stop" (互換: "llm_stop")


class ResetBody(BaseModel):
    max_steps: int = 40


class GuidePersonaBody(BaseModel):
    id: str
    # step==0 のとき、プリセット変更を「リセット相当」にするため任意指定（UI の計画スライダーと整合）
    max_steps: Optional[int] = None


class GuideAgentBody(BaseModel):
    enabled: bool


def _guide_agent_enabled() -> bool:
    return _guide_agent_ui


def _guide_personality() -> str:
    raw = os.environ.get("DEMO_GUIDE_PERSONALITY", "").strip()
    if raw:
        return raw
    entry = GUIDE_PERSONAS.get(_selected_guide_persona_id) or {}
    return str(entry.get("personality") or DEFAULT_GUIDE_PERSONALITY)


def _guide_config() -> Dict[str, Any]:
    personas_list = [
        {
            "id": kid,
            "label": str(v.get("label") or kid),
            "description": str(v.get("description") or ""),
            "sim_preset": _rounded_sim_preset(_persona_sim_kw(kid)),
        }
        for kid, v in GUIDE_PERSONAS.items()
    ]
    env_personality = bool(os.environ.get("DEMO_GUIDE_PERSONALITY", "").strip())
    return {
        "agent_enabled": _guide_agent_enabled(),
        "personality": _guide_personality(),
        "selected_persona_id": _selected_guide_persona_id,
        "selected_sim_preset": _rounded_sim_preset(
            _persona_sim_kw(_selected_guide_persona_id)
        ),
        "personas": personas_list,
        "personality_env_override": env_personality,
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


PARTY_LEADER_LABEL = "引率・朔"
PARTY_MEMBER_A_LABEL = "隊員・遥"
PARTY_MEMBER_B_LABEL = "隊員・楓"


def _leader_fallback_line(action: Literal["trek", "rest"]) -> str:
    if action == "rest":
        return "ここで一息つこう。荷物を下ろして水分と体温を整える。"
    return "このまま進む。足元と間隔に注意して、報連相は省略しない。"


def _party_member_lines(sim: RiskSimulator, action: Literal["trek", "rest"]) -> Tuple[str, str]:
    """隊員ふたりの返答（現在メトリクスに応じて文言を少し変える）。"""
    m = sim.metrics()
    hum = m.get("human") or {}
    envo = m.get("env") or {}
    fatigue = float(hum.get("fatigue") or 0)
    vis = float(envo.get("visibility") or 0)
    gap_d = bool(m.get("gap_danger"))
    if action == "rest":
        line_a = "休めるなら助かる。肩がこってきてた。"
        line_b = "了解。風向きも見とく。"
        if fatigue > 0.38:
            line_a = "正直キツかった…休憩ありがたい。"
        elif fatigue > 0.28:
            line_a = "足が重い。ここで詰めなくて正解だと思う。"
        return line_a, line_b
    line_a = "進むなら荷重心は低めで。岩屑あるから。"
    line_b = "視界、ちゃんと確認してからね。"
    if vis < 0.28:
        line_b = "ガスってきてる？ピッチ長くしないほうがいいんじゃ。"
    if gap_d:
        line_a = "楽観ムード強くない？様子、ちゃんと見てる？"
    return line_a, line_b


def _party_chat_entries(
    sim: RiskSimulator,
    action: Literal["trek", "rest"],
    leader_content: str,
) -> List[Dict[str, Any]]:
    ma, mb = _party_member_lines(sim, action)
    return [
        {
            "role": "assistant",
            "kind": "party",
            "speaker": "leader",
            "speaker_label": PARTY_LEADER_LABEL,
            "content": leader_content.strip(),
            "action": action,
        },
        {
            "role": "assistant",
            "kind": "party",
            "speaker": "member_a",
            "speaker_label": PARTY_MEMBER_A_LABEL,
            "content": ma,
            "action": action,
        },
        {
            "role": "assistant",
            "kind": "party",
            "speaker": "member_b",
            "speaker_label": PARTY_MEMBER_B_LABEL,
            "content": mb,
            "action": action,
        },
    ]


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
        f"【選択中の引率者人格】\n{personality}\n\n"
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
    _sim = new_simulator(max_steps=body.max_steps, **_persona_sim_kw(_selected_guide_persona_id))
    return _enrich(_sim.snapshot())


@app.post("/api/guide_persona")
def set_guide_persona(body: GuidePersonaBody) -> Dict[str, Any]:
    global _selected_guide_persona_id, _sim
    pid = body.id.strip()
    if pid not in GUIDE_PERSONAS:
        raise HTTPException(status_code=400, detail="unknown guide_persona id")

    if _sim.step > 0:
        raise HTTPException(
            status_code=409,
            detail="進行中のため変更できません（プリセットはリセット後に変更できます）。",
        )

    _selected_guide_persona_id = pid
    ms = body.max_steps if body.max_steps is not None else int(_sim.max_steps)
    # step が進んでいないときだけ、プリセット変更をリセット相当として適用
    _sim = new_simulator(max_steps=ms, **_persona_sim_kw(_selected_guide_persona_id))
    return _enrich(_sim.snapshot())


@app.post("/api/guide_agent")
def set_guide_agent(body: GuideAgentBody) -> Dict[str, Any]:
    global _guide_agent_ui
    _guide_agent_ui = bool(body.enabled)
    return _enrich(_sim.snapshot())


@app.post("/api/advance")
def advance() -> Dict[str, Any]:
    chat_entries: Optional[List[Dict[str, Any]]] = None
    step_override: Optional[Literal["trek", "rest"]] = None

    if _sim.can_advance():
        if _guide_agent_enabled():
            action, reasoning = _ollama_guide_plan_next_step(_sim, _guide_personality())
            step_override = action
            leader = reasoning.strip() if reasoning.strip() else _leader_fallback_line(action)
            chat_entries = _party_chat_entries(_sim, action, leader)
        else:
            fb = _fallback_step_kind(_sim)
            chat_entries = _party_chat_entries(
                _sim, fb, _leader_fallback_line(fb)
            )

    snap = _sim.advance(
        step_kind=step_override if _guide_agent_enabled() else None,
        chat_entries=chat_entries,
    )
    return _enrich(snap)


@app.post("/api/decide")
def decide(body: DecideBody) -> Dict[str, Any]:
    text: Optional[str] = None
    if body.choice == "continue":
        snap = _sim.decide_continue()
    elif body.choice in ("stop", "llm_stop"):
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
                    "speaker": "coach",
                    "speaker_label": "中止コーチ",
                    "step": snap.get("step"),
                    "content": text
                    or "Ollama からの応答がありませんでした。数値と分岐はそのまま有効です。",
                }
            )
            snap = _sim.snapshot()
    else:
        raise HTTPException(status_code=400, detail="choice must be continue or stop")

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
