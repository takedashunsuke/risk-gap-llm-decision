/**
 * Risk Gap LLM Decision — デモフロント
 * API ベース URL は同一オリジンの /api（将来 Vite 等に切り出すときは環境変数化）
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const COLORS = {
    R_obj: "#7c9cff",
    R_subj: "#fbbf24",
    Gap: "#f87171",
    Cost_stop: "#94a3b8",
  };

  let autoplayTimer = null;
  let lastRenderedStep = null;

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
      ctx.font = "10px system-ui";
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
    ctx.font = "10px system-ui";
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

  function buildTrailPath() {
    const pts = [];
    const segments = 28;
    for (let i = 0; i <= segments; i++) {
      const t = i / segments;
      const x = 22 + t * (400 - 44);
      const y = 62 + Math.sin(t * Math.PI * 1.55) * 16 - t * 8;
      pts.push([x, y]);
    }
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) d += ` L ${pts[i][0]} ${pts[i][1]}`;
    $("trail-path").setAttribute("d", d);
    return pts;
  }

  const trailPts = buildTrailPath();

  function trailPosition(progress01) {
    const t = Math.min(1, Math.max(0, progress01));
    const idx = t * (trailPts.length - 1);
    const i = Math.floor(idx);
    const f = idx - i;
    const p0 = trailPts[i];
    const p1 = trailPts[Math.min(i + 1, trailPts.length - 1)];
    return [p0[0] + f * (p1[0] - p0[0]), p0[1] + f * (p1[1] - p0[1])];
  }

  function pulseTrailScene() {
    const el = document.querySelector(".trail-scene");
    if (!el) return;
    el.classList.remove("trail-scene--pulse");
    void el.offsetWidth;
    el.classList.add("trail-scene--pulse");
  }

  function updateTrail(data) {
    const m = data.metrics || {};
    const r = typeof m.R_obj === "number" ? m.R_obj : 0;
    const progress = data.max_steps > 0 ? data.step / data.max_steps : 0;
    const [cx, cy] = trailPosition(progress);
    const footOy = 18;
    const hiker = $("trail-hiker-root");
    if (hiker) {
      hiker.setAttribute("transform", `translate(${cx}, ${cy - footOy})`);
    }

    const inner = $("trail-hiker-inner");
    const walking =
      data.phase === "running" &&
      data.step < data.max_steps &&
      data.step >= 0;
    if (inner) {
      inner.classList.toggle("trail-hiker-inner--walk", !!walking);
    }

    const veil = $("trail-veil");
    if (veil) {
      const op = Math.min(0.78, r * 0.92 + (m.gap_danger ? 0.08 : 0));
      veil.setAttribute("opacity", String(op));
    }

    const scene = document.querySelector(".trail-scene");
    if (scene) {
      scene.classList.toggle("trail-scene--danger", !!(m.gap_danger || r >= 0.42));
    }

    $("trail-caption").textContent =
      `ステップ ${data.step} / ${data.max_steps} · ロール：登山途中 · 客観 R_obj ≈ ${m.R_obj != null ? m.R_obj.toFixed(2) : "—"}`;
  }

  function render(data) {
    const prevStep = lastRenderedStep;
    const stepIncreased =
      prevStep !== null && data.step > prevStep && data.step > 0;

    const m = data.metrics || {};
    const br = m.breakdown || {};
    $("step-label").textContent = `${data.step} / ${data.max_steps} · ${data.phase}`;
    $("metrics-root").innerHTML = `
        <div class="card"><h3>R_obj</h3><div class="val">${fmt(m.R_obj)}</div></div>
        <div class="card"><h3>R_subj</h3><div class="val">${fmt(m.R_subj)}</div></div>
        <div class="card"><h3>Gap</h3><div class="val">${fmt(m.Gap)}</div></div>
        <div class="card"><h3>T</h3><div class="val">${fmt(m.T)}</div></div>
        <div class="card"><h3>Cost_stop</h3><div class="val">${fmt(m.Cost_stop)}</div></div>
        <div class="card"><h3>バイアス</h3><div class="val">${fmt(m.bias)}</div></div>
      `;
    $("breakdown").innerHTML =
      `環境 ${fmt(br.environment_avg)} · 人 ${fmt(br.human_avg)} · 時間 ${fmt(br.time_pressure)}<br/>` +
      `Gap≥0.2: ${m.gap_danger ? "はい" : "いいえ"}`;

    const canDecide = !!data.can_decide && data.phase === "running";
    $("btn-advance").disabled =
      data.phase !== "running" || data.step >= data.max_steps;
    $("btn-continue").disabled = !canDecide;
    $("btn-llm").disabled = !canDecide;

    const ban = $("banner");
    ban.className = "banner";
    if (data.outcome === "accident") {
      ban.classList.add("show", "accident");
      ban.textContent = "結果：続行 → 事故シナリオ（デモ）。";
    } else if (data.outcome === "avoided") {
      ban.classList.add("show", "avoided");
      ban.textContent = "結果：中止 → 回避。";
    } else {
      ban.classList.remove("show");
      ban.textContent = "";
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
    render(data);
    const lw = $("llm-wrap");
    lw.classList.remove("show");
    $("llm-text").textContent = "";
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
      render(data);
      $("llm-wrap").classList.remove("show");
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
      const lw = $("llm-wrap");
      lw.classList.add("show");
      if (data.llm_message) {
        $("llm-text").textContent = data.llm_message;
      } else {
        $("llm-text").textContent =
          "Ollama からの応答がありませんでした。数値と分岐はそのまま有効です。";
      }
    });

    window.addEventListener("resize", () => {
      api("/api/state").then(render).catch(console.error);
    });
  }

  bind();
  refresh().catch(console.error);
})();
