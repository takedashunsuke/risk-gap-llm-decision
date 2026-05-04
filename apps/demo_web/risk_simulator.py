"""
high_level_design_v2.md に沿った最小リスク意思決定モデル（デモ用）。
数値のソース・オブ・トゥルースは Python 側。LLM は説明文のみに使う。
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
import random
from typing import Any, Dict, List, Literal, Optional

MIN_STEPS = 10
MAX_STEPS = 70
# 8 ステップ相当の累積悪化を max_steps に分散するための基準
_REF_STEPS = 8.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# judgment_events[].reason_code および内部トリガ判定で共通利用
JUDGMENT_MAX_STEPS = "max_steps"
# 計画ステップ手前の遅い局面で Gap が危険域に入ったときの一回限り提示（advance 内でセット）
JUDGMENT_LATE_GAP_DANGER = "late_gap_danger"
JUDGMENT_FLAG_CONTINUE_TOGGLED = "flag_continue_toggled"
JUDGMENT_FLAG_GAP_TOGGLED = "flag_gap_toggled"
JUDGMENT_FLAG_BOTH_TOGGLED = "flag_both_toggled"


@dataclass
class RiskSimulator:
    """環境・人間・圧力から R_obj / R_subj / Gap を計算し、分岐結果を返す。"""

    T: float = 0.6
    w1: float = 1 / 3
    w2: float = 1 / 3
    w3: float = 1 / 3

    # Environment（設計書 4.1）
    weather: float = 0.15
    visibility: float = 0.2
    temp_risk: float = 0.1

    # Human
    fatigue: float = 0.15
    attention_loss: float = 0.1

    # Pressure
    time_pressure: float = 0.2
    external_pressure: float = 0.15

    # バイアス（過信）— 成功体験などで初期値を少し持つ
    bias: float = 0.12
    # 中止コスト（引き返し困難さ）
    cost_stop: float = 0.18
    # Gap 要注意判定のしきい値（続行判断後に緩和する）
    gap_danger_threshold: float = 0.2

    step: int = 0
    max_steps: int = 40
    phase: Literal["running", "ended"] = "running"
    outcome: Optional[Literal["accident", "avoided", "cleared"]] = None
    last_decision: Optional[Literal["continue", "llm_stop"]] = None
    # 再現性確保のための乱数シード（同じ操作列なら同じ結果を再現しやすくする）
    rng_seed: int = 20260504
    # true の場合は従来どおり（判断ボタン押下で即終了）
    legacy_decision: bool = False
    # 直近の advance が「通常登山」か「休憩（リカバリ）」か（ステップ0では None）
    last_advance_event: Optional[Literal["trek", "rest"]] = None

    history: List[Dict[str, Any]] = field(default_factory=list)
    # 判断イベント履歴（フェーズBでの多段判断拡張に備える）
    judgment_events: List[Dict[str, Any]] = field(default_factory=list)
    # max_steps 未到達でも判断 UI を出す場合の理由（1回提示したらクリア）
    judgment_prompt_reason: Optional[str] = None
    # max_steps 到達時の判断は既定モードでは 1 回だけ要求する
    max_steps_decision_done: bool = False
    # 引率エージェント／中止コーチなど UI 用チャット（デモの表示のみ）
    guide_chat: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.max_steps = max(MIN_STEPS, min(MAX_STEPS, int(self.max_steps)))
        self._rng = random.Random(self.rng_seed)
        m = self.metrics()
        self.history = [{"step": 0, "event": "start", **m}]

    def append_guide_chat(self, entry: Dict[str, Any]) -> None:
        """クライアント表示用のチャット行を追加（アプリ層から呼ぶ）。"""
        self.guide_chat.append(entry)
        if len(self.guide_chat) > 120:
            self.guide_chat = self.guide_chat[-120:]

    def _scale(self) -> float:
        """1 ステップあたりの悪化量（ステップ数が多いほど小さく）。"""
        return _REF_STEPS / float(self.max_steps)

    def _env_avg(self) -> float:
        return (self.weather + self.visibility + self.temp_risk) / 3.0

    def _human_avg(self) -> float:
        return (self.fatigue + self.attention_loss) / 2.0

    def metrics(self) -> Dict[str, Any]:
        env_avg = self._env_avg()
        human_avg = self._human_avg()
        r_obj = self.w1 * env_avg + self.w2 * human_avg + self.w3 * self.time_pressure
        r_obj = _clamp01(r_obj)
        r_subj = _clamp01(r_obj - self.bias)
        gap = r_obj - r_subj
        # 続行ルール: (R_subj + Cost_stop) < T
        continue_if = (r_subj + self.cost_stop) < self.T
        gap_danger = gap >= self.gap_danger_threshold
        return {
            "R_obj": round(r_obj, 4),
            "R_subj": round(r_subj, 4),
            "Gap": round(gap, 4),
            "T": self.T,
            "Cost_stop": round(self.cost_stop, 4),
            "bias": round(self.bias, 4),
            "continue_rule_holds": continue_if,
            "gap_danger": gap_danger,
            "gap_danger_threshold": round(self.gap_danger_threshold, 4),
            "breakdown": {
                "environment_avg": round(env_avg, 4),
                "human_avg": round(human_avg, 4),
                "time_pressure": round(self.time_pressure, 4),
            },
            "env": {
                "weather": round(self.weather, 4),
                "visibility": round(self.visibility, 4),
                "temp_risk": round(self.temp_risk, 4),
            },
            "human": {
                "fatigue": round(self.fatigue, 4),
                "attention_loss": round(self.attention_loss, 4),
            },
            "pressure": {
                "time": round(self.time_pressure, 4),
                "external": round(self.external_pressure, 4),
            },
        }

    def rp_zone(self) -> Literal[
        "yama", "mori", "kouya", "home", "mori_yoru", "umi"
    ]:
        """ロールプレイ地名（フロントの背景画像と連動）。"""
        if self.phase == "ended":
            if self.outcome == "avoided":
                return "home"
            if self.outcome == "accident":
                return "mori_yoru"
            if self.outcome == "cleared":
                return "umi"
        ms = max(self.max_steps, 1)
        r = self.step / ms
        if r < 0.28:
            return "yama"
        if r < 0.55:
            return "mori"
        return "kouya"

    def chart_series(self) -> List[Dict[str, Any]]:
        """グラフ用の時系列（各 history 行から主要指標のみ）。"""
        rows = []
        for h in self.history:
            ev = h.get("event")
            row = {
                "step": int(h["step"]),
                "R_obj": float(h["R_obj"]),
                "R_subj": float(h["R_subj"]),
                "Gap": float(h["Gap"]),
                "Cost_stop": float(h["Cost_stop"]),
            }
            if isinstance(ev, str):
                row["event"] = ev
            rows.append(row)
        return rows

    def _late_gap_judgment_threshold_step(self) -> int:
        """計画上限の 85% 以降を「遅い局面」とみなす（最低 1 ステップ）。"""
        return max(1, int(self.max_steps * 0.85))

    def _judgment_trigger_reason(self) -> Optional[str]:
        """判断ボタンを出すべきなら理由コードを返す。優先: 計画上限 > 遅い局面の Gap。"""
        if self.phase != "running":
            return None
        if self.step >= self.max_steps and not self.max_steps_decision_done:
            return JUDGMENT_MAX_STEPS
        return self.judgment_prompt_reason

    def _maybe_set_flag_toggle_prompt(
        self, prev_m: Dict[str, Any], now_m: Dict[str, Any]
    ) -> None:
        """続行ルール/GAP の真偽が切り替わったら判断待ちにする。"""
        if self.legacy_decision:
            return
        if self.judgment_prompt_reason is not None:
            return
        prev_continue = bool(prev_m.get("continue_rule_holds"))
        prev_gap = bool(prev_m.get("gap_danger"))
        now_continue = bool(now_m.get("continue_rule_holds"))
        now_gap = bool(now_m.get("gap_danger"))
        continue_changed = prev_continue != now_continue
        gap_changed = prev_gap != now_gap
        if continue_changed and gap_changed:
            self.judgment_prompt_reason = JUDGMENT_FLAG_BOTH_TOGGLED
        elif continue_changed:
            self.judgment_prompt_reason = JUDGMENT_FLAG_CONTINUE_TOGGLED
        elif gap_changed:
            self.judgment_prompt_reason = JUDGMENT_FLAG_GAP_TOGGLED

    def _maybe_set_late_gap_prompt(self, m: Dict[str, Any]) -> None:
        """上限手前で Gap が危険なら、一回だけ判断提示フラグを立てる。"""
        if self.legacy_decision:
            return
        if self.judgment_prompt_reason is not None:
            return
        if self.step >= self.max_steps:
            return
        if self.step < self._late_gap_judgment_threshold_step():
            return
        if bool(m.get("gap_danger")):
            self.judgment_prompt_reason = JUDGMENT_LATE_GAP_DANGER

    def _sync_late_gap_prompt(self, m: Dict[str, Any]) -> None:
        """遅い局面の Gap 提示中にメトリクスが改善したら、提示を下ろす。"""
        if self.judgment_prompt_reason == JUDGMENT_LATE_GAP_DANGER and not bool(
            m.get("gap_danger")
        ):
            self.judgment_prompt_reason = None

    def _decision_mode(self) -> Literal["none", "hard_choice"]:
        """フロントの判断ボタン表示制御用。"""
        return "hard_choice" if self._judgment_trigger_reason() else "none"

    def can_advance(self) -> bool:
        if self.phase != "running":
            return False
        if self.legacy_decision:
            return self.step < self.max_steps
        if self._judgment_trigger_reason() is not None:
            return False
        return self.step < MAX_STEPS

    def _append_judgment_event(
        self, *, reason_code: str, choice: Optional[Literal["continue", "llm_stop"]] = None
    ) -> None:
        self.judgment_events.append(
            {
                "step": self.step,
                "reason_code": reason_code,
                "choice": choice,
            }
        )
        if len(self.judgment_events) > 120:
            self.judgment_events = self.judgment_events[-120:]

    def snapshot(self) -> Dict[str, Any]:
        decision_mode = self._decision_mode()
        return {
            "step": self.step,
            "max_steps": self.max_steps,
            "phase": self.phase,
            "outcome": self.outcome,
            "last_decision": self.last_decision,
            "last_advance_event": self.last_advance_event,
            "metrics": self.metrics(),
            "can_decide": decision_mode == "hard_choice",
            "can_advance": self.can_advance(),
            "decision_mode": decision_mode,
            "rng_seed": self.rng_seed,
            "judgment_events": list(self.judgment_events),
            "judgment_trigger_reason": self._judgment_trigger_reason(),
            "chart_series": self.chart_series(),
            "guide_chat": list(self.guide_chat),
            "rp_zone": self.rp_zone(),
        }

    def advance(
        self,
        step_kind: Optional[Literal["trek", "rest"]] = None,
        chat_entry: Optional[Dict[str, Any]] = None,
        chat_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """状態悪化・過信・中止コスト増（設計書セクション6の②〜④を簡略化）。
        step_kind が None のときは step%6==0 で休憩。Ollama 引率時は "trek"/"rest" を渡す。
        chat_entries があれば複数行をチャットに追加（パーティ会話用）。chat_entry は単一行の互換用。
        """
        if not self.can_advance():
            return self.snapshot()

        prev_m = self.metrics()
        s = self._scale()
        self.step += 1
        if step_kind is not None:
            is_rest = step_kind == "rest"
        else:
            # 一定間隔で休憩ステップ：疲労・プレッシャーなどが下がり、曲線が単調増加にならない
            is_rest = self.step > 0 and self.step % 6 == 0
        if is_rest:
            self.last_advance_event = "rest"
            self.fatigue = _clamp01(self.fatigue - 0.14 * s)
            self.attention_loss = _clamp01(self.attention_loss - 0.12 * s)
            self.time_pressure = _clamp01(self.time_pressure - 0.09 * s)
            self.external_pressure = _clamp01(self.external_pressure - 0.07 * s)
            self.bias = _clamp01(self.bias - 0.05 * s)
            self.cost_stop = _clamp01(self.cost_stop - 0.06 * s)
            self.visibility = _clamp01(self.visibility + 0.05 * s)
            self.temp_risk = _clamp01(self.temp_risk - 0.04 * s)
            self.weather = _clamp01(self.weather - 0.03 * s)
        else:
            self.last_advance_event = "trek"
            # 悪化（参照 8 ステップと同等の総量になるようスケール）
            self.weather = _clamp01(self.weather + 0.07 * s)
            self.visibility = _clamp01(self.visibility - 0.06 * s)
            self.temp_risk = _clamp01(self.temp_risk + 0.05 * s)
            self.fatigue = _clamp01(self.fatigue + 0.06 * s)
            self.attention_loss = _clamp01(self.attention_loss + 0.05 * s)
            self.time_pressure = _clamp01(self.time_pressure + 0.06 * s)
            self.external_pressure = _clamp01(self.external_pressure + 0.05 * s)
            self.bias = _clamp01(self.bias + 0.035 * s)
            self.cost_stop = _clamp01(self.cost_stop + 0.045 * s)

        m = self.metrics()
        self._maybe_set_flag_toggle_prompt(prev_m, m)
        self._maybe_set_late_gap_prompt(m)
        self._sync_late_gap_prompt(m)
        self.history.append({"step": self.step, "event": "rest" if is_rest else "trek", **m})
        if chat_entries is not None:
            for entry in chat_entries:
                row = {**entry, "step": self.step}
                self.append_guide_chat(row)
        elif chat_entry is not None:
            row = {**chat_entry, "step": self.step}
            self.append_guide_chat(row)
        self._resolve_post_decision_outcome()
        return self.snapshot()

    def _resolve_post_decision_outcome(self) -> None:
        if self.phase != "running" or self.legacy_decision:
            return
        if self.step <= self.max_steps:
            return
        if self.last_decision == "continue":
            m = self.metrics()
            gap = float(m.get("Gap") or 0.0)
            r_obj = float(m.get("R_obj") or 0.0)
            continue_holds = bool(m.get("continue_rule_holds"))
            th = float(self.gap_danger_threshold)
            # 続行直後の早すぎる終了を避けるため短い猶予を設ける
            if self.step < min(MAX_STEPS, self.max_steps + 3):
                return
            # Gap が広がる、または続行ルールが崩れるまでは基本継続
            if continue_holds and gap < (th + 0.1) and r_obj < 0.58:
                return
            if (not continue_holds and gap >= (th + 0.1)) or gap >= (th + 0.2) or r_obj >= 0.62:
                self.phase = "ended"
                self.outcome = "accident"
                return
            if self.step >= MAX_STEPS:
                self.phase = "ended"
                self.outcome = "cleared" if continue_holds else "accident"
                return
        elif self.last_decision == "llm_stop":
            if self.step >= min(MAX_STEPS, self.max_steps + 2):
                self.phase = "ended"
                self.outcome = "avoided"

    def decide_continue(self) -> Dict[str, Any]:
        """分岐①：続行。危険要素が強ければ森の夜（事故）、問題なければ海ゴール。"""
        trig = self._judgment_trigger_reason()
        if self.phase != "running" or trig is None:
            return self.snapshot()
        self._append_judgment_event(reason_code=trig, choice="continue")
        self.last_decision = "continue"
        self.judgment_prompt_reason = None
        # 続行（過信）するたびに Gap 判定しきい値を +0.1 緩和
        self.gap_danger_threshold = _clamp01(self.gap_danger_threshold + 0.1)
        if trig == JUDGMENT_MAX_STEPS:
            self.max_steps_decision_done = True
        if self.legacy_decision:
            m = self.metrics()
            self.phase = "ended"
            if bool(m.get("gap_danger")) or float(m.get("R_obj") or 0) >= 0.42:
                self.outcome = "accident"
            else:
                self.outcome = "cleared"
        return self.snapshot()

    def decide_llm_stop(self) -> Dict[str, Any]:
        """分岐②：中止。ここでエンディングし、人テーマ平均を下げる。"""
        trig = self._judgment_trigger_reason()
        if self.phase != "running" or trig is None:
            return self.snapshot()
        self._append_judgment_event(reason_code=trig, choice="llm_stop")
        self.last_decision = "llm_stop"
        self.judgment_prompt_reason = None
        if trig == JUDGMENT_MAX_STEPS:
            self.max_steps_decision_done = True
        # 方針変更: 中止は即終了。客観リスク（人テーマ平均）を 0.1 下げる。
        self.fatigue = _clamp01(self.fatigue - 0.1)
        self.attention_loss = _clamp01(self.attention_loss - 0.1)
        self.phase = "ended"
        self.outcome = "avoided"
        return self.snapshot()


def new_simulator(max_steps: int = 40, **overrides: Any) -> RiskSimulator:
    """max_steps に加え、指定キーのみ RiskSimulator の初期値を上書き（引率プリセット用）。"""
    field_names = {f.name for f in fields(RiskSimulator)}
    kw: Dict[str, Any] = {"max_steps": max_steps}
    for k, v in overrides.items():
        if k in field_names and k != "max_steps":
            kw[k] = v
    return RiskSimulator(**kw)
