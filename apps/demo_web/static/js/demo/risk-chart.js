import { COLORS } from "./constants.js";
import { $, num01 } from "./util.js";

/** Chart.js インスタンス（再描画時に destroy） */
let riskChart = null;

function hexToRgba(hex, alpha) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return hex;
  return (
    "rgba(" +
    parseInt(m[1], 16) +
    "," +
    parseInt(m[2], 16) +
    "," +
    parseInt(m[3], 16) +
    "," +
    alpha +
    ")"
  );
}

/**
 * リスク推移: Chart.js の積み上げバー（R_obj / R_subj / Cost_stop）＋ Gap 折れ線（右軸）。
 * @see https://www.chartjs.org/docs/latest/samples/other-charts/combo-bar-line.html
 */
export function drawChart(series, _maxSteps) {
  const canvas = $("chart");
  const ChartCtor = typeof Chart !== "undefined" ? Chart : null;
  if (!canvas) return;
  if (riskChart) {
    riskChart.destroy();
    riskChart = null;
  }
  if (!ChartCtor) return;

  const labels = series.length ? series.map((s) => String(s.step)) : ["0"];
  const z = (pt, key) => {
    const n = num01(pt[key]);
    return n == null ? 0 : n;
  };
  const rObj = series.map((pt) => z(pt, "R_obj"));
  const rSubj = series.map((pt) => z(pt, "R_subj"));
  const costStop = series.map((pt) => z(pt, "Cost_stop"));
  const gap = series.map((pt) => z(pt, "Gap"));
  let maxStack = 0.01;
  for (let i = 0; i < series.length; i++) {
    const pt = series[i];
    maxStack = Math.max(
      maxStack,
      z(pt, "R_obj") + z(pt, "R_subj") + z(pt, "Cost_stop")
    );
  }
  const ySuggestedMax = Math.min(3, Math.max(0.25, maxStack * 1.06));
  const stackId = "risk";
  const empty = !series.length;

  riskChart = new ChartCtor(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "R_obj",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.R_obj,
          backgroundColor: hexToRgba(COLORS.R_obj, 0.55),
          borderWidth: 1,
          data: empty ? [0] : rObj,
        },
        {
          type: "bar",
          label: "R_subj",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.R_subj,
          backgroundColor: hexToRgba(COLORS.R_subj, 0.55),
          borderWidth: 1,
          data: empty ? [0] : rSubj,
        },
        {
          type: "bar",
          label: "Cost_stop",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.Cost_stop,
          backgroundColor: hexToRgba(COLORS.Cost_stop, 0.55),
          borderWidth: 1,
          data: empty ? [0] : costStop,
        },
        {
          type: "line",
          label: "Gap",
          yAxisID: "y1",
          order: 0,
          borderColor: COLORS.Gap,
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.2,
          fill: false,
          data: empty ? [0] : gap,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 220 },
      interaction: { mode: "index", intersect: false },
      font: {
        family: "system-ui, -apple-system, 'Segoe UI', sans-serif",
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const py =
                ctx.parsed && typeof ctx.parsed.y === "number"
                  ? ctx.parsed.y
                  : null;
              const name = ctx.dataset.label || "";
              return name + ": " + (py != null ? py.toFixed(2) : "—");
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { color: "rgba(255,255,255,0.55)", maxRotation: 0 },
          grid: { color: "rgba(255,255,255,0.06)" },
          title: {
            display: true,
            text: "ステップ",
            color: "rgba(255,255,255,0.45)",
            font: { size: 10 },
          },
        },
        y: {
          stacked: true,
          min: 0,
          suggestedMax: ySuggestedMax,
          ticks: { color: "rgba(255,255,255,0.55)" },
          grid: { color: "rgba(255,255,255,0.08)" },
          title: {
            display: true,
            text: "積み上げ",
            color: "rgba(255,255,255,0.45)",
            font: { size: 10 },
          },
        },
        y1: {
          position: "right",
          min: 0,
          max: 1,
          grid: { drawOnChartArea: false },
          ticks: { color: "rgba(248,113,113,0.9)" },
          title: {
            display: true,
            text: "Gap（0〜1）",
            color: "rgba(248,113,113,0.7)",
            font: { size: 10 },
          },
        },
      },
    },
  });
}
