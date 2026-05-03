/**
 * Risk Gap LLM Decision — デモフロント
 * API ベース URL は同一オリジンの /api（将来 Vite 等に切り出すときは環境変数化）
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const LLM_PLACEHOLDER =
    "中止を選ぶと、ここにコーチからのメッセージが表示されます。";

  function setLlmContent(text) {
    const el = $("llm-text");
    if (!el) return;
    const raw = text != null ? String(text).trim() : "";
    el.textContent = raw || LLM_PLACEHOLDER;
    el.classList.toggle("llm--placeholder", !raw);
  }

  const COLORS = {
    R_obj: "#7c9cff",
    R_subj: "#fbbf24",
    Gap: "#f87171",
    Cost_stop: "#94a3b8",
  };

  let autoplayTimer = null;
  let lastRenderedStep = null;
  /** 結果モーダルを二重に出さないためのキー（outcome + step） */
  let lastOutcomeModalKey = null;

  function breakdownRow(labelHtml, val) {
    return (
      `<div class="bd-row">` +
      `<span class="bd-k">${labelHtml}</span>` +
      `<span class="bd-v">${fmt(val)}</span></div>`
    );
  }

  function breakdownBoolRow(labelHtml, cond) {
    return (
      `<div class="bd-row">` +
      `<span class="bd-k">${labelHtml}</span>` +
      `<span class="bd-v">${cond ? "はい" : "いいえ"}</span></div>`
    );
  }

  function renderBreakdown(m) {
    const br = m.breakdown || {};
    const env = m.env || {};
    const hum = m.human || {};
    const pr = m.pressure || {};
    let h = `<div class="breakdown-rows">`;
    h += `<div class="bd-section">合成（テーマ平均）</div>`;
    h += breakdownRow("環境テーマ平均", br.environment_avg);
    h += breakdownRow("人テーマ平均", br.human_avg);
    h += breakdownRow("時間プレッシャー（内訳行）", br.time_pressure);
    h += `<div class="bd-section">環境リスク（入力）</div>`;
    h += breakdownRow(`天候 <span class="mono">weather</span>`, env.weather);
    h += breakdownRow(`視界 <span class="mono">visibility</span>`, env.visibility);
    h += breakdownRow(`気温リスク <span class="mono">temp_risk</span>`, env.temp_risk);
    h += `<div class="bd-section">人（入力）</div>`;
    h += breakdownRow(`疲労 <span class="mono">fatigue</span>`, hum.fatigue);
    h += breakdownRow(`注意散漫 <span class="mono">attention_loss</span>`, hum.attention_loss);
    h += `<div class="bd-section">圧力（入力）</div>`;
    h += breakdownRow(`時間 <span class="mono">time_pressure</span>`, pr.time);
    h += breakdownRow(`外部 <span class="mono">external_pressure</span>`, pr.external);
    h += `<div class="bd-section">フラグ</div>`;
    h += breakdownBoolRow(
      `続行ルール成立 <span class="mono">(R_subj−Cost_stop)&lt;T</span>`,
      !!m.continue_rule_holds
    );
    h += breakdownBoolRow("Gap ≥ 0.2（要注意）", !!m.gap_danger);
    h += `</div>`;
    return h;
  }

  function openOutcomeModal(data) {
    const o = data.outcome;
    const titleEl = $("outcomeModalTitle");
    const bodyEl = $("outcome-modal-body");
    const headEl = $("outcome-modal-header");
    const modalEl = $("outcomeModal");
    if (!titleEl || !bodyEl || !headEl || !modalEl || !window.bootstrap) return;

    headEl.className =
      "modal-header py-2 outcome-modal-header bg-white border-bottom";
    headEl.classList.remove(
      "outcome-modal-header--danger",
      "outcome-modal-header--success",
      "outcome-modal-header--info"
    );

    let title = "シミュレーション結果";
    let body = "";
    if (o === "accident") {
      title = "続行の結果";
      body =
        "そのまま踏み切り → 森の夜（引き返せないルート）。客観リスクが高い状態での続行とみなします。";
      headEl.classList.add("outcome-modal-header--danger");
    } else if (o === "avoided") {
      title = "中止の結果";
      body = "LLM 介入により中止 → 帰還（ホーム）。";
      headEl.classList.add("outcome-modal-header--success");
    } else if (o === "cleared") {
      title = "ゴール";
      body = "条件良好のままゴール（海）へ到達した想定です。";
      headEl.classList.add("outcome-modal-header--info");
    } else {
      return;
    }

    titleEl.textContent = title;
    bodyEl.textContent = body;
    window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  async function api(path, opt) {
    const res = await fetch(path, opt);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  function fmt(x) {
    if (x === undefined || x === null) return "—";
    return x;
  }

  function drawChart(series, maxSteps) {
    const wrap = $("chart-wrap");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cssW = Math.max(120, wrap.clientWidth || 400);
    const cssH = Math.max(100, wrap.clientHeight || 180);
    const canvas = $("chart");
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    canvas.style.width = cssW + "px";
    canvas.style.height = cssH + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    const W = cssW;
    const H = cssH;
    const pad = { l: 36, r: 10, t: 10, b: 28 };
    ctx.fillStyle = "#111427";
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.t + ((H - pad.t - pad.b) * i) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(W - pad.r, y);
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.font = "11px system-ui";
      ctx.textAlign = "right";
      const val = (1 - i / 4).toFixed(1);
      ctx.fillText(val, pad.l - 4, y + 3);
    }
    const x0 = pad.l;
    const x1 = W - pad.r;
    const y1 = H - pad.b;
    const xScale = (step) =>
      x0 + (maxSteps > 0 ? (step / maxSteps) * (x1 - x0) : 0);
    const yScale = (v) => y1 - Math.min(1, Math.max(0, v)) * (y1 - pad.t);

    function drawLine(key, color, dashed) {
      if (!series.length) return;
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = key === "Gap" ? 2.2 : 2;
      if (dashed) ctx.setLineDash([5, 4]);
      else ctx.setLineDash([]);
      series.forEach((pt, i) => {
        const x = xScale(pt.step);
        const y = yScale(pt[key]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    drawLine("R_obj", COLORS.R_obj, false);
    drawLine("R_subj", COLORS.R_subj, false);
    drawLine("Gap", COLORS.Gap, false);
    drawLine("Cost_stop", COLORS.Cost_stop, true);

    ctx.fillStyle = "rgba(255,255,255,0.45)";
    ctx.font = "11px system-ui";
    ctx.textAlign = "center";
    ctx.fillText("ステップ", W / 2, H - 8);

    if (series.length) {
      const last = series[series.length - 1];
      ["R_obj", "R_subj"].forEach((key) => {
        ctx.beginPath();
        ctx.fillStyle = COLORS[key];
        ctx.arc(xScale(last.step), yScale(last[key]), 3.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }

  function pulseTrailScene() {
    const el = document.querySelector(".trail-scene");
    if (!el) return;
    el.classList.remove("trail-scene--pulse");
    void el.offsetWidth;
    el.classList.add("trail-scene--pulse");
  }

  const RP_BG = {
    yama: "/static/image/yama.jpg",
    mori: "/static/image/mori.jpg",
    kouya: "/static/image/kouya.jpg",
    home: "/static/image/home.jpg",
    mori_yoru: "/static/image/mori_yoru.jpg",
    umi: "/static/image/umi.jpg",
  };

  const RP_LABEL = {
    yama: "山・登山口付近",
    mori: "森の中",
    kouya: "高地・荒野（コウヤ）",
    home: "帰還（ホーム）",
    mori_yoru: "森の夜（引き返せない）",
    umi: "ゴール（海）",
  };

  function inferRpZone(data) {
    const phase = data.phase;
    const oc = data.outcome;
    const ms = Math.max(data.max_steps || 1, 1);
    const step = data.step || 0;
    if (phase === "ended") {
      if (oc === "avoided") return "home";
      if (oc === "accident") return "mori_yoru";
      if (oc === "cleared") return "umi";
    }
    const pr = step / ms;
    if (pr < 0.28) return "yama";
    if (pr < 0.55) return "mori";
    return "kouya";
  }

  const TRI_PARTY = [
    { dx: 0, dy: -5.4 },
    { dx: 6.0, dy: 3.7 },
    { dx: -6.0, dy: 3.7 },
  ];
  const CIRCLE_TURNS = 2.2;
  const CIRCLE_R_PCT = 2.85;
  /** キャラ全体をやや下へ（%） */
  const PARTY_DROP_Y = 3.2;

  function updateTrail(data) {
    const m = data.metrics || {};
    const r = typeof m.R_obj === "number" ? m.R_obj : 0;
    const progress = data.max_steps > 0 ? data.step / data.max_steps : 0;
    const walking =
      data.phase === "running" &&
      data.step < data.max_steps &&
      data.step >= 0;

    const zone = data.rp_zone || inferRpZone(data);
    const bg = $("trail-bg");
    if (bg && RP_BG[zone]) {
      bg.style.backgroundImage = 'url("' + RP_BG[zone] + '")';
    }

    const ang = progress * Math.PI * 2 * CIRCLE_TURNS;
    const baseX = 50 + Math.cos(ang) * CIRCLE_R_PCT;
    const baseY = 50 + Math.sin(ang) * CIRCLE_R_PCT + PARTY_DROP_Y;

    for (let i = 0; i < TRI_PARTY.length; i++) {
      const t = TRI_PARTY[i];
      const charRoot = $("trail-char-" + i);
      if (charRoot) {
        charRoot.style.left = baseX + t.dx + "%";
        charRoot.style.top = baseY + t.dy + "%";
      }
      const anchor = charRoot && charRoot.querySelector(".trail-char-anchor");
      if (anchor) {
        anchor.classList.toggle("trail-char-anchor--walk", !!walking);
      }
    }

    const veil = $("trail-veil");
    if (veil) {
      const op = Math.min(0.78, r * 0.92 + (m.gap_danger ? 0.08 : 0));
      veil.style.opacity = String(op);
    }

    const scene = document.querySelector(".trail-scene");
    if (scene) {
      scene.classList.toggle("trail-scene--danger", !!(m.gap_danger || r >= 0.42));
    }

    const z = data.rp_zone || inferRpZone(data);
    const zj = RP_LABEL[z] || z;
    $("trail-caption").textContent =
      `ステップ ${data.step} / ${data.max_steps} · 場所：${zj} · R_obj ≈ ${
        m.R_obj != null ? m.R_obj.toFixed(2) : "—"
      }`;
  }

  function render(data) {
    const prevStep = lastRenderedStep;
    const stepIncreased =
      prevStep !== null && data.step > prevStep && data.step > 0;

    const m = data.metrics || {};
    $("step-label").textContent = `${data.step} / ${data.max_steps} · ${data.phase}`;
    function metricCol(jaLabel, codeKey, val) {
      return (
        `<div class="col">` +
        `<div class="card metric-card h-100 border shadow-sm">` +
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
      metricCol("客観リスク", "R_obj", m.R_obj) +
      metricCol("主観リスク", "R_subj", m.R_subj) +
      metricCol("ギャップ", "Gap", m.Gap) +
      metricCol("閾値", "T", m.T) +
      metricCol("中止コスト", "Cost_stop", m.Cost_stop) +
      metricCol("過信バイアス", "bias", m.bias);

    const gc = data.guide_config;
    const gRoot = $("guide-config-root");
    if (gRoot && gc) {
      const on = gc.agent_enabled ? "ON" : "OFF";
      const pers = String(gc.personality || "")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      gRoot.innerHTML =
        `<div class="card-body py-2 px-3">` +
        `<h3 class="h6 mb-2 fw-semibold">引率エージェント（DEMO_GUIDE）</h3>` +
        `<p class="small mb-1"><span class="badge ${gc.agent_enabled ? "text-bg-primary" : "text-bg-secondary"}">${on}</span></p>` +
        `<p class="small text-muted mb-0 demo-guide-personality">${pers}</p></div>`;
    }

    const chatLog = $("agent-chat-log");
    const gchat = data.guide_chat;
    if (chatLog && Array.isArray(gchat)) {
      chatLog.innerHTML = gchat
        .slice(-40)
        .map(function (e) {
          const kind = e.kind || "";
          const body = String(e.content || "")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
          const meta =
            "step " +
            (e.step != null ? e.step : "—") +
            (kind ? " · " + kind : "") +
            (e.action ? " · " + e.action : "");
          const cls =
            kind === "guide"
              ? "chat-bubble chat-bubble--guide"
              : kind === "coach"
                ? "chat-bubble chat-bubble--coach"
                : "chat-bubble";
          return (
            `<div class="${cls} mb-2">` +
            `<div class="chat-meta">${meta}</div>` +
            `<div class="chat-body">${body}</div></div>`
          );
        })
        .join("");
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    $("breakdown").innerHTML = renderBreakdown(m);

    const canDecide = !!data.can_decide && data.phase === "running";
    $("btn-advance").disabled =
      data.phase !== "running" || data.step >= data.max_steps;
    $("btn-continue").disabled = !canDecide;
    $("btn-llm").disabled = !canDecide;

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

    const series = data.chart_series || [];
    drawChart(series, data.max_steps || 40);
    updateTrail(data);

    if (stepIncreased) {
      pulseTrailScene();
    }

    if (data.phase !== "running" || data.step >= data.max_steps) {
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
      btn.textContent = "自動再生";
    }
  }

  function toggleAutoplay() {
    if (autoplayTimer) {
      stopAutoplay();
      return;
    }
    $("btn-autoplay").classList.add("active");
    $("btn-autoplay").textContent = "停止";
    autoplayTimer = setInterval(async () => {
      const st = await api("/api/state");
      if (st.phase !== "running" || st.step >= st.max_steps) {
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

    $("btn-advance").addEventListener("click", async () => {
      const data = await api("/api/advance", { method: "POST" });
      render(data);
    });

    $("btn-autoplay").addEventListener("click", () => toggleAutoplay());

    $("btn-continue").addEventListener("click", async () => {
      stopAutoplay();
      const data = await api("/api/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ choice: "continue" }),
      });
      render(data);
    });

    $("btn-llm").addEventListener("click", async () => {
      stopAutoplay();
      const data = await api("/api/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ choice: "llm_stop" }),
      });
      render(data);
      if (data.llm_message) {
        setLlmContent(data.llm_message);
      } else {
        setLlmContent(
          "Ollama からの応答がありませんでした。数値と分岐はそのまま有効です。"
        );
      }
    });

    window.addEventListener("resize", () => {
      api("/api/state").then(render).catch(console.error);
    });
  }

  bind();
  refresh().catch(console.error);
})();
