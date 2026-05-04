/**
 * デモ本体 — entry.js から import.meta.url に ?t= 付きで読み込まれる
 */
import { siblingImportQuery } from "./asset-query.js";

const q = siblingImportQuery(import.meta.url);
const [
  util,
  llmPanel,
  metricsBreakdown,
  outcomeModal,
  riskChart,
  trail,
] = await Promise.all([
  import(`./util.js${q}`),
  import(`./llm-panel.js${q}`),
  import(`./metrics-breakdown.js${q}`),
  import(`./outcome-modal.js${q}`),
  import(`./risk-chart.js${q}`),
  import(`./trail.js${q}`),
]);

const { $, api, fmt, escHtml, escAttr } = util;
const { setLlmContent } = llmPanel;
const {
  metricCardSeverityClass,
  renderBreakdownDetail,
  renderRiskFlags,
} = metricsBreakdown;
const { openOutcomeModal } = outcomeModal;
const { drawChart } = riskChart;
const { pulseTrailScene, updateTrail } = trail;

let autoplayTimer = null;
let lastRenderedStep = null;
/** 結果モーダルを二重に出さないためのキー（outcome + step） */
let lastOutcomeModalKey = null;
/** 判断モーダルを同じトリガで連打しないためのキー */
let lastDecisionPromptKey = null;

function setAutoplayIcon(isRunning) {
  const icon = $("btn-autoplay-icon");
  if (!icon) return;
  icon.src = isRunning ? "/static/image/stop.svg" : "/static/image/start.svg";
}

function decisionReasonLabel(reason) {
  switch (reason) {
    case "max_steps":
      return "計画ステップに到達しました。次の方針を選択してください。";
    case "late_gap_danger":
      return "遅い局面で Gap が要注意域に入りました。次の方針を選択してください。";
    case "flag_continue_toggled":
      return "続行ルールが切り替わりました。次の方針を選択してください。";
    case "flag_gap_toggled":
      return "Gap フラグが切り替わりました。次の方針を選択してください。";
    case "flag_both_toggled":
      return "続行ルールと Gap フラグが同時に切り替わりました。次の方針を選択してください。";
    default:
      return "状態が変化したため、次の方針を選択してください。";
  }
}

function getDecisionModal() {
  const root = $("decisionModal");
  if (!root || typeof bootstrap === "undefined" || !bootstrap.Modal) return null;
  return bootstrap.Modal.getOrCreateInstance(root);
}

async function submitDecision(choice) {
  stopAutoplay();
  const data = await api("/api/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice }),
  });
  render(data);
  if (data.llm_message) {
    setLlmContent(data.llm_message);
  } else if (choice === "stop") {
    setLlmContent(
      "Ollama からの応答がありませんでした。数値と分岐はそのまま有効です。"
    );
  }
}

function render(data) {
  const prevStep = lastRenderedStep;
  const stepIncreased =
    prevStep !== null && data.step > prevStep && data.step > 0;

  const m = data.metrics || {};
  $("step-label").textContent = `${data.step} / ${data.max_steps}（進捗／計画）`;
  function metricCol(jaLabel, codeKey, val, metrics) {
    const sev = metricCardSeverityClass(codeKey, metrics);
    return (
      `<div class="col">` +
      `<div class="card metric-card h-100 border shadow-sm${sev}">` +
      `<div class="card-body py-2 px-2">` +
      `<h3 class="h6 metric-heading mb-1">` +
      `<span class="metric-ja">${jaLabel}</span>` +
      `<span class="metric-code">${codeKey}</span>` +
      `</h3>` +
      `<div class="val metric-val">${fmt(val)}</div>` +
      `</div></div></div>`
    );
  }
  $("metrics-root").innerHTML =
    metricCol("客観リスク", "R_obj", m.R_obj, m) +
    metricCol("主観リスク", "R_subj", m.R_subj, m) +
    metricCol("ギャップ", "Gap", m.Gap, m) +
    metricCol("閾値", "T", m.T, m) +
    metricCol("中止コスト", "Cost_stop", m.Cost_stop, m) +
    metricCol("過信バイアス", "bias", m.bias, m);

  const gc = data.guide_config;
  const gRoot = $("guide-config-root");
  if (gRoot && gc) {
    const pers = escHtml(String(gc.personality || ""));
    const personas = Array.isArray(gc.personas) ? gc.personas : [];
    const selId = String(gc.selected_persona_id || "");
    const envOv = !!gc.personality_env_override;
    let opts = "";
    for (let i = 0; i < personas.length; i++) {
      const p = personas[i];
      const id = String(p.id != null ? p.id : "");
      const lab = escHtml(String(p.label != null ? p.label : id));
      const sel = id === selId ? " selected" : "";
      opts += `<option value="${escAttr(id)}"${sel}>${lab}</option>`;
    }
    let desc = "";
    for (let j = 0; j < personas.length; j++) {
      if (String(personas[j].id) === selId) {
        desc = String(personas[j].description || "");
        break;
      }
    }
    const envNote = envOv
      ? `<p class="small text-warning mb-2 mb-lg-1">環境変数 <code class="small">DEMO_GUIDE_PERSONALITY</code> が優先され、プリセットの人格文は無視されます（数値プリセットはリセット時に反映）。</p>`
      : "";
    const switchHint = gc.agent_enabled
      ? "ON: 各ステップで Ollama が登山か休憩を選び、理由をチャットに表示します。このスイッチで OFF にできます。"
      : "OFF: Ollama は使わず、約6ステップごとの自動休憩のみ。このスイッチで ON にできます。";
    const agentChecked = gc.agent_enabled ? " checked" : "";
    let personaBlurb = "";
    if (desc) {
      personaBlurb += `<p class="guide-persona-lead small text-muted mb-2 mb-md-1">${escHtml(
        desc
      )}</p>`;
    }
    personaBlurb += `<p class="guide-persona-body small text-muted mb-0">${pers}</p>`;
    gRoot.innerHTML =
      `<div class="card-body py-2 px-3">` +
      `<div class="guide-card-head d-flex flex-wrap align-items-center gap-2 mb-2 min-w-0">` +
      `<span class="guide-card-title fw-semibold text-body">引率人格選択</span>` +
      `<div class="form-check form-switch guide-agent-switch mb-0">` +
      `<input class="form-check-input" type="checkbox" role="switch" id="guide-agent-switch"${agentChecked} title="${escAttr(switchHint)}" aria-label="Ollama による引率を有効にする" />` +
      `<label class="form-check-label guide-agent-switch-label mb-0" for="guide-agent-switch">Ollama</label>` +
      `</div>` +
      `</div>` +
      `<select id="guide-persona-select" class="form-select form-select-sm guide-persona-select mb-2" aria-label="引率人格とリセット時の初期パラメータ">` +
      opts +
      `</select>` +
      envNote +
      `<div class="guide-persona-block">${personaBlurb}</div>` +
      `</div>`;
  }

  const chatLog = $("agent-chat-log");
  const gchat = data.guide_chat;
  if (chatLog && Array.isArray(gchat)) {
    chatLog.innerHTML = gchat
      .slice(-48)
      .map(function (e) {
        const kind = e.kind || "";
        const speaker = String(e.speaker || "");
        const body = String(e.content || "")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
        const meta =
          "step " +
          (e.step != null ? e.step : "—") +
          (e.action ? " · " + e.action : "") +
          (kind === "coach" ? " · 中止コーチ" : "");
        let cls = "chat-bubble mb-2";
        if (kind === "coach") {
          cls += " chat-bubble--coach";
        } else if (kind === "party") {
          cls += " chat-bubble--party";
          if (speaker === "member_a") cls += " chat-bubble--party-a";
          else if (speaker === "member_b") cls += " chat-bubble--party-b";
          else cls += " chat-bubble--party-leader";
        } else if (kind === "guide") {
          cls += " chat-bubble--party chat-bubble--party-leader";
        } else {
          cls += " chat-bubble--neutral";
        }
        const labelRaw = e.speaker_label;
        const speakerHead =
          labelRaw != null && String(labelRaw).trim() !== ""
            ? `<div class="chat-speaker">${escHtml(String(labelRaw))}</div>`
            : "";
        return (
          `<div class="${cls}">` +
          speakerHead +
          `<div class="chat-meta">${meta}</div>` +
          `<div class="chat-body">${body}</div></div>`
        );
      })
      .join("");
    chatLog.scrollTop = chatLog.scrollHeight;
  }

    const bFl = $("risk-flags-strip");
    const bDet = $("breakdown-detail");
    if (bFl) bFl.innerHTML = renderRiskFlags(m);
    if (bDet) bDet.innerHTML = renderBreakdownDetail(m);

  const canDecide = !!data.can_decide && data.phase === "running";
  const canAdvance = !!data.can_advance && data.phase === "running";
  $("btn-advance").disabled = !canAdvance;
  $("btn-open-decision").disabled = !canDecide;
  const reason = data.judgment_trigger_reason;
  const hint = $("decision-hint");
  if (hint) {
    hint.textContent = canDecide
      ? decisionReasonLabel(reason)
      : "※状態フラグが切り替わると判断を促します。";
  }
  const reasonNode = $("decision-modal-reason");
  if (reasonNode) {
    reasonNode.textContent = decisionReasonLabel(reason);
  }

  const endKey =
    data.phase === "ended" && data.outcome
      ? String(data.outcome) + "-" + String(data.step)
      : "";
  if (endKey && endKey !== lastOutcomeModalKey) {
    lastOutcomeModalKey = endKey;
    openOutcomeModal(data);
  }
  if (data.phase === "running" && !data.outcome) {
    lastOutcomeModalKey = null;
  }

  $("decision-row").style.display =
    data.phase === "ended" ? "none" : "flex";
  $("decision-hint").style.display =
    data.phase === "ended" ? "none" : "block";
  if (canDecide) {
    const promptKey = `${data.step}:${reason || "unknown"}`;
    if (promptKey !== lastDecisionPromptKey) {
      lastDecisionPromptKey = promptKey;
      const m = getDecisionModal();
      if (m) m.show();
    }
  } else if (!canAdvance) {
    lastDecisionPromptKey = null;
  }

  const series = data.chart_series || [];
  drawChart(series, data.max_steps || 40);
  updateTrail(data);

  if (stepIncreased) {
    pulseTrailScene();
  }

  if (!canAdvance) {
    stopAutoplay();
  }

  lastRenderedStep = data.step;
}

function stopAutoplay() {
  if (autoplayTimer) {
    clearInterval(autoplayTimer);
    autoplayTimer = null;
  }
  const btn = $("btn-autoplay");
  if (btn) {
    btn.classList.remove("active");
    btn.setAttribute("aria-label", "自動再生");
    btn.setAttribute("title", "自動再生");
    setAutoplayIcon(false);
  }
}

function toggleAutoplay() {
  if (autoplayTimer) {
    stopAutoplay();
    return;
  }
  $("btn-autoplay").classList.add("active");
  $("btn-autoplay").setAttribute("aria-label", "自動再生を停止");
  $("btn-autoplay").setAttribute("title", "自動再生を停止");
  setAutoplayIcon(true);
  autoplayTimer = setInterval(async () => {
    const st = await api("/api/state");
    if (st.phase !== "running" || !st.can_advance) {
      stopAutoplay();
      return;
    }
    const data = await api("/api/advance", { method: "POST" });
    render(data);
  }, 420);
}

async function refresh() {
  const data = await api("/api/state");
  $("max-steps").value = data.max_steps;
  $("max-steps-val").textContent = data.max_steps;
  lastRenderedStep = null;
  setLlmContent("");
  render(data);
}

function bind() {
  $("max-steps").addEventListener("input", (e) => {
    $("max-steps-val").textContent = e.target.value;
  });

  $("btn-reset").addEventListener("click", async () => {
    stopAutoplay();
    const ms = parseInt($("max-steps").value, 10);
    const data = await api("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_steps: ms }),
    });
    lastRenderedStep = null;
    setLlmContent("");
    render(data);
  });

  document.addEventListener("change", async (ev) => {
    const t = ev.target;
    if (!t) return;
    if (t.id === "guide-agent-switch") {
      stopAutoplay();
      try {
        const data = await api("/api/guide_agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: !!t.checked }),
        });
        render(data);
      } catch (err) {
        console.error(err);
      }
      return;
    }
    if (t.id !== "guide-persona-select") return;
    stopAutoplay();
    try {
      const data = await api("/api/guide_persona", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: t.value }),
      });
      render(data);
    } catch (err) {
      console.error(err);
    }
  });

  $("btn-advance").addEventListener("click", async () => {
    const data = await api("/api/advance", { method: "POST" });
    render(data);
  });

  $("btn-autoplay").addEventListener("click", () => toggleAutoplay());

  $("btn-open-decision").addEventListener("click", () => {
    const m = getDecisionModal();
    if (m) m.show();
  });

  $("btn-modal-continue").addEventListener("click", async () => {
    const m = getDecisionModal();
    if (m) m.hide();
    await submitDecision("continue");
  });

  $("btn-modal-stop").addEventListener("click", async () => {
    const m = getDecisionModal();
    if (m) m.hide();
    await submitDecision("stop");
  });

  window.addEventListener("resize", () => {
    api("/api/state").then(render).catch(console.error);
  });
}

bind();
refresh().catch(console.error);
