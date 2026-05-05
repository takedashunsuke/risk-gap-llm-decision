"""
設計書 v2 向けデモ Web。localhost で数値シミュレーションと分岐を表示する。
"""
from __future__ import annotations

import json
import os
import random
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

CHAT_STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    # 口調と重複回避の強さ（low/medium/high）
    "safety_first": {"tone": "落ち着いた安全優先の口調", "anti_repeat": "high"},
    "pace_push": {"tone": "手短でテンポ重視の口調", "anti_repeat": "medium"},
    "optimist": {"tone": "前向きだが軽すぎない口調", "anti_repeat": "high"},
    "weather_watch": {"tone": "観測事実を丁寧に共有する口調", "anti_repeat": "high"},
}


def _chat_style_profile() -> Dict[str, Any]:
    base = {"tone": "自然で簡潔な現場口調", "anti_repeat": "medium"}
    row = CHAT_STYLE_PRESETS.get(_selected_guide_persona_id) or {}
    out = dict(base)
    for k in ("tone", "anti_repeat"):
        if k in row:
            out[k] = row[k]
    return out


def _recent_lines_for_repeat_guard(sim: RiskSimulator, anti_repeat: str) -> List[str]:
    n = 8
    if anti_repeat == "high":
        n = 12
    elif anti_repeat == "low":
        n = 4
    rows = sim.guide_chat[-n:]
    out: List[str] = []
    for row in rows:
        ct = str(row.get("content") or "").strip()
        if ct:
            out.append(ct)
    return out


def _rng_for_chat(sim: RiskSimulator, action: Literal["trek", "rest"]) -> random.Random:
    """同じ状態ならほぼ同じ会話を返すための軽い決定論乱数。"""
    m = sim.metrics()
    seed = (
        sim.step * 1000
        + sim.max_steps * 31
        + int((m.get("R_obj") or 0) * 10000)
        + int((m.get("Gap") or 0) * 10000) * 7
        + (17 if action == "rest" else 29)
    )
    return random.Random(seed)


def _leader_fallback_line(
    sim: RiskSimulator,
    action: Literal["trek", "rest"],
    reasoning_hint: str = "",
    tone_hint: str = "",
) -> str:
    m = sim.metrics()
    gap_d = bool(m.get("gap_danger"))
    ro = float(m.get("R_obj") or 0)
    hum = m.get("human") or {}
    envo = m.get("env") or {}
    fatigue = float(hum.get("fatigue") or 0)
    vis = float(envo.get("visibility") or 0)
    rng = _rng_for_chat(sim, action)
    if reasoning_hint.strip():
        # LLM の判断理由をそのまま見せると「引率の即時判断感」が出る
        return reasoning_hint.strip()
    is_push = "テンポ重視" in tone_hint
    is_fact = "観測事実" in tone_hint
    if action == "rest":
        pool = [
            "ここで一息入れよう。水分・体温・呼吸を整えてから再開する。",
            "焦らず休憩を取る。肩と足をほぐして、次の区間に備えよう。",
            "立ち止まる判断にする。隊形を整えて状況確認を先にやる。",
        ]
        if is_push:
            pool = [
                "ここで短く休む。整えたらすぐ再開しよう。",
                "1回だけ止まる。呼吸と装備を整えて次へ行く。",
                "休憩を挟む。確認を済ませたらテンポを戻す。",
            ]
        elif is_fact:
            pool = [
                "視界と疲労の数値を見て、ここで休憩に切り替える。",
                "観測上、無理は得策じゃない。回復を優先しよう。",
                "現状の変化量を踏まえて、いったん停止して整える。",
            ]
        if fatigue > 0.34 or vis < 0.28:
            pool = [
                "疲労と視界が気になる。短くても休憩を入れてから動こう。",
                "無理に詰めない。いったん止まって足元と風を確認する。",
                "今は回復優先。ここで整えないと次の判断が鈍る。",
            ]
        return pool[rng.randrange(len(pool))]
    pool = [
        "このまま進む。足場と間隔を守って、声かけは短く続ける。",
        "進行を継続する。ペースは抑えめで、変化があればすぐ共有。",
        "前進しよう。焦らず一定リズムで行く。異変があれば即停止。",
    ]
    if is_push:
        pool = [
            "進む。ピッチは維持しつつ、確認ポイントだけは外さない。",
            "この区間は前進。短い合図でテンポを合わせていく。",
            "進行継続。詰めすぎず、変化が出たらすぐ修正しよう。",
        ]
    elif is_fact:
        pool = [
            "現時点の条件なら前進可能。確認頻度を上げて進もう。",
            "観測値を踏まえれば進行できる。隊列を保っていこう。",
            "前進判断。視界と疲労の変化を都度確認しながら行く。",
        ]
    if gap_d or ro >= 0.4:
        pool = [
            "進むが慎重にいく。楽観は捨てて、変化が出たらすぐ止める。",
            "前進判断。ただし警戒モードで、隊列と視界確認を優先する。",
            "ここは進む。けれど無理はしない。危険サインが出たら即切り替える。",
        ]
    return pool[rng.randrange(len(pool))]


def _party_member_lines(
    sim: RiskSimulator, action: Literal["trek", "rest"], tone_hint: str = ""
) -> Tuple[str, str]:
    """隊員ふたりの返答（テンプレ固定を避け、状態に応じて複数候補から選ぶ）。"""
    m = sim.metrics()
    hum = m.get("human") or {}
    envo = m.get("env") or {}
    fatigue = float(hum.get("fatigue") or 0)
    vis = float(envo.get("visibility") or 0)
    gap_d = bool(m.get("gap_danger"))
    rng = _rng_for_chat(sim, action)
    is_push = "テンポ重視" in tone_hint
    is_fact = "観測事実" in tone_hint
    if action == "rest":
        a_pool = [
            "休めるなら助かる。肩がこってきてた。",
            "いい判断だと思う。足が固まってきてた。",
            "短くでも止まれるのはありがたい。呼吸が楽になる。",
        ]
        b_pool = [
            "了解。風向きも見とく。",
            "わかった。周囲の足場を先に確認しておく。",
            "オーケー。視界の変化とルート目印を見ておくね。",
        ]
        if fatigue > 0.38:
            a_pool = [
                "正直キツかった…休憩ありがたい。",
                "助かった、脚が攣りそうだった。",
                "いったん止まれて本当に助かる。集中が切れかけてた。",
            ]
        elif fatigue > 0.28:
            a_pool = [
                "足が重い。ここで詰めなくて正解だと思う。",
                "この休憩でだいぶ違う。次に備えられる。",
                "ちょうど止まりたかった。判断が冴えるはず。",
            ]
        if is_push:
            b_pool = [
                "了解、装備だけ素早く見直しておく。",
                "わかった。次に動きやすい形で整えるね。",
                "オーケー、短時間で要点だけ確認する。",
            ]
        elif is_fact:
            b_pool = [
                "了解。風と視界の変化を記録しておく。",
                "わかった、足場と目印の状態を確認する。",
                "了解。観測した変化をすぐ共有するね。",
            ]
        return a_pool[rng.randrange(len(a_pool))], b_pool[rng.randrange(len(b_pool))]
    a_pool = [
        "進むなら荷重心は低めで。岩屑あるから。",
        "前に出る。段差は一歩ずつ確認していく。",
        "進行了解。足場優先でピッチは上げすぎない。",
    ]
    b_pool = [
        "視界、ちゃんと確認してからね。",
        "ガイドロープの間隔、狭めに取ろう。",
        "前方だけじゃなく横風も見ながら行こう。",
    ]
    if vis < 0.28:
        b_pool = [
            "ガスってきてる？ピッチ長くしないほうがいいんじゃ。",
            "視界が薄い。間隔を詰めて進もう。",
            "遠くが見えない。確認回数を増やしたい。",
        ]
    if gap_d:
        a_pool = [
            "楽観ムード強くない？様子、ちゃんと見てる？",
            "いける雰囲気だけで押すのは怖い。確認しながら行こう。",
            "進むのは賛成だけど、危険サインは見落としたくない。",
        ]
    if is_push:
        b_pool = [
            "了解、合図は短くして進もう。",
            "わかった。リズム維持で行く。",
            "オーケー、隊列を詰めすぎないようにする。",
        ]
    elif is_fact:
        b_pool = [
            "了解。視界と足場を順に確認して進む。",
            "わかった。変化があれば即共有する。",
            "了解、観測ベースで慎重に進める。",
        ]
    return a_pool[rng.randrange(len(a_pool))], b_pool[rng.randrange(len(b_pool))]


def _party_chat_entries(
    sim: RiskSimulator,
    action: Literal["trek", "rest"],
    leader_content: str,
    member_lines: Optional[Tuple[str, str]] = None,
    tone_hint: str = "",
) -> List[Dict[str, Any]]:
    ma, mb = (
        member_lines
        if member_lines is not None
        else _party_member_lines(sim, action, tone_hint=tone_hint)
    )
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


def _parse_party_chat_json(text: str) -> Optional[Tuple[str, str, str]]:
    """leader/member_a/member_b を JSON から抽出。"""
    if not text:
        return None
    t = text.strip()
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end <= start:
        return None
    blob = t[start : end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    leader = str(obj.get("leader", "") or "").strip()
    ma = str(obj.get("member_a", "") or "").strip()
    mb = str(obj.get("member_b", "") or "").strip()
    if leader and ma and mb:
        return leader, ma, mb
    return None


def _ollama_party_chat_lines(
    sim: RiskSimulator,
    action: Literal["trek", "rest"],
    personality: str,
    leader_hint: str,
    tone_preset: str,
    anti_repeat: str,
) -> Optional[Tuple[str, str, str]]:
    """3人分の会話を LLM で生成。失敗時は None。"""
    m = sim.metrics()
    hum = m.get("human") or {}
    envo = m.get("env") or {}
    pr = m.get("pressure") or {}
    recent = sim.guide_chat[-6:]
    recent_lines = []
    for row in recent:
        sp = str(row.get("speaker_label") or row.get("speaker") or "")
        ct = str(row.get("content") or "").strip()
        if ct:
            recent_lines.append(f"- {sp}: {ct}")
    recent_block = "\n".join(recent_lines) if recent_lines else "- （直近会話なし）"
    repeat_guard_lines = _recent_lines_for_repeat_guard(sim, anti_repeat)
    repeat_guard = "\n".join(f"- {x}" for x in repeat_guard_lines) if repeat_guard_lines else "- （なし）"
    prompt = (
        "あなたは登山パーティの会話生成アシスタントです。"
        "以下の状況で、引率1行・隊員2行の自然な短い会話を作ってください。\n\n"
        f"【引率者人格】\n{personality}\n\n"
        f"【口調プリセット】\n{tone_preset}\n"
        f"【重複回避の強さ】{anti_repeat}\n\n"
        f"【このステップの行動】{action}\n"
        f"【引率の判断理由（参考）】{leader_hint}\n\n"
        "【数値（事実）】\n"
        f"- step={sim.step}/{sim.max_steps}, R_obj={m.get('R_obj')}, R_subj={m.get('R_subj')}, Gap={m.get('Gap')}\n"
        f"- 疲労={hum.get('fatigue')}, 注意散漫={hum.get('attention_loss')}, 視界={envo.get('visibility')}\n"
        f"- 時間圧={pr.get('time')}, 外部圧={pr.get('external')}\n\n"
        "【直近の会話（重複回避用）】\n"
        f"{recent_block}\n\n"
        "【なるべく言い換える対象（避けたい重複）】\n"
        f"{repeat_guard}\n\n"
        "【制約】\n"
        "- 日本語。各行は25〜80文字程度。\n"
        "- 引率は命令口調に偏りすぎず、状況判断がにじむ言い方。\n"
        "- 隊員2人は口調を少し変える（同じ文体にしない）。\n"
        "- 同じ表現・語尾・言い回しの連続を避ける。\n"
        "- 危険を煽りすぎない。淡々と現場会話にする。\n"
        "- 数値は捏造しない（本文に数値を出さなくてもよい）。\n\n"
        "【出力】JSONのみ。キーは leader, member_a, member_b。\n"
        '例: {"leader":"ここで短く整えてから進もう。","member_a":"助かる、足が重かった。","member_b":"了解、風と視界を先に見ておく。"}'
    )
    raw = _ollama_generate(prompt, num_predict=260, temperature=0.7)
    return _parse_party_chat_json(raw or "")


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
        style = _chat_style_profile()
        tone_hint = str(style.get("tone") or "")
        anti_repeat = str(style.get("anti_repeat") or "medium")
        if _guide_agent_enabled():
            action, reasoning = _ollama_guide_plan_next_step(_sim, _guide_personality())
            step_override = action
            llm_lines = _ollama_party_chat_lines(
                _sim,
                action,
                _guide_personality(),
                reasoning,
                tone_preset=tone_hint,
                anti_repeat=anti_repeat,
            )
            if llm_lines:
                leader, ma, mb = llm_lines
                chat_entries = _party_chat_entries(
                    _sim,
                    action,
                    leader,
                    member_lines=(ma, mb),
                    tone_hint=tone_hint,
                )
            else:
                leader = _leader_fallback_line(
                    _sim, action, reasoning, tone_hint=tone_hint
                )
                chat_entries = _party_chat_entries(
                    _sim, action, leader, tone_hint=tone_hint
                )
        else:
            fb = _fallback_step_kind(_sim)
            chat_entries = _party_chat_entries(
                _sim,
                fb,
                _leader_fallback_line(_sim, fb, tone_hint=tone_hint),
                tone_hint=tone_hint,
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
