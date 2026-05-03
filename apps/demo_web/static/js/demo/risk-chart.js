import { COLORS } from "./constants.js";
import { $, num01 } from "./util.js";

/** X 軸は常にこの本数（横幅の目安）。max_steps が大きいときは stepsPerBin を増やして収める */
const SLOT_COUNT = 30;

/** #chart-wrap ライトグレー向けの軸・グリッド色 */
const CHART_AXIS = {
  tick: "#475569",
  tickMuted: "#64748b",
  gridY: "rgba(15, 23, 42, 0.09)",
  gridX: "rgba(15, 23, 42, 0.06)",
  title: "#64748b",
  gapTick: "#b91c1c",
  gapTitle: "#b91c1c",
};

/** Chart.js インスタンス（同一設定なら destroy せず update） */
let riskChart = null;

/** @typedef {{ maxSteps: number, stepsPerBin: number }} RiskChartMeta */

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
 * max_steps を SLOT_COUNT 本以下に収める最小の「何ステップを1帯にまとめるか」
 * （例: 50 → 2 で 25 帯、さらに 30 スロットまで右側は空帯）
 */
function stepsPerBinForMaxSteps(maxSteps) {
  const ms = Math.max(1, maxSteps);
  let per = 1;
  while (Math.ceil(ms / per) > SLOT_COUNT) {
    per++;
  }
  return per;
}

function slotLabel(slotIndex, stepsPerBin, maxSteps) {
  const lo = slotIndex * stepsPerBin;
  if (lo >= maxSteps) return "—";
  const hi = Math.min(maxSteps - 1, lo + stepsPerBin - 1);
  if (stepsPerBin === 1) return String(lo);
  return lo + "–" + hi;
}

/**
 * 系列を固定スロットへ集約（同一帯に複数点があるときは履歴の後勝ち）
 */
function aggregateSeriesToSlots(series, maxSteps, stepsPerBin) {
  const slots = Array.from({ length: SLOT_COUNT }, () => null);
  for (let i = 0; i < series.length; i++) {
    const pt = series[i];
    const step = parseInt(pt.step, 10);
    if (Number.isNaN(step) || step < 0 || step >= maxSteps) continue;
    const bin = Math.min(SLOT_COUNT - 1, Math.floor(step / stepsPerBin));
    slots[bin] = pt;
  }
  return slots;
}

function zVal(pt, key) {
  if (!pt) return 0;
  const n = num01(pt[key]);
  return n == null ? 0 : n;
}

/**
 * @returns {{ labels: string[], rObj: number[], rSubj: number[], costStop: number[], gap: (number|null)[], ySuggestedMax: number, empty: boolean, maxSteps: number, stepsPerBin: number }}
 */
function computeSlotData(series, maxSteps) {
  const stepsPerBin = stepsPerBinForMaxSteps(maxSteps);
  const slots =
    series.length > 0
      ? aggregateSeriesToSlots(series, maxSteps, stepsPerBin)
      : Array.from({ length: SLOT_COUNT }, () => null);
  const labels = Array.from({ length: SLOT_COUNT }, (_, i) =>
    slotLabel(i, stepsPerBin, maxSteps)
  );
  const rObj = slots.map((pt) => zVal(pt, "R_obj"));
  const rSubj = slots.map((pt) => zVal(pt, "R_subj"));
  const costStop = slots.map((pt) => zVal(pt, "Cost_stop"));
  const gap = slots.map((pt) => (pt == null ? null : zVal(pt, "Gap")));
  let maxStack = 0.01;
  for (let i = 0; i < slots.length; i++) {
    const pt = slots[i];
    if (!pt) continue;
    maxStack = Math.max(
      maxStack,
      zVal(pt, "R_obj") + zVal(pt, "R_subj") + zVal(pt, "Cost_stop")
    );
  }
  const ySuggestedMax = Math.min(3, Math.max(0.25, maxStack * 1.06));
  return {
    labels,
    rObj,
    rSubj,
    costStop,
    gap,
    ySuggestedMax,
    empty: !series.length,
    maxSteps,
    stepsPerBin,
  };
}

function chartNeedsRebuild(pack) {
  if (!riskChart || !riskChart.$demoMeta) return true;
  const m = riskChart.$demoMeta;
  return m.maxSteps !== pack.maxSteps || m.stepsPerBin !== pack.stepsPerBin;
}

function applyDataToChart(pack) {
  const d = riskChart.data;
  d.labels = pack.labels;
  d.datasets[0].data = pack.empty ? Array(SLOT_COUNT).fill(0) : pack.rObj;
  d.datasets[1].data = pack.empty ? Array(SLOT_COUNT).fill(0) : pack.rSubj;
  d.datasets[2].data = pack.empty ? Array(SLOT_COUNT).fill(0) : pack.costStop;
  d.datasets[3].data = pack.empty ? Array(SLOT_COUNT).fill(null) : pack.gap;
  riskChart.options.scales.y.suggestedMax = pack.ySuggestedMax;
  riskChart.options.scales.x.title.text =
    "ステップ（横 " +
    SLOT_COUNT +
    " 帯" +
    (pack.stepsPerBin > 1 ? "・" + pack.stepsPerBin + " ステップ/帯" : "") +
    "）";
  riskChart.$demoMeta = {
    maxSteps: pack.maxSteps,
    stepsPerBin: pack.stepsPerBin,
  };
}

function createRiskChart(canvas, ChartCtor, pack) {
  const stackId = "risk";
  return new ChartCtor(canvas, {
    type: "bar",
    data: {
      labels: pack.labels,
      datasets: [
        {
          type: "bar",
          label: "R_obj",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.R_obj,
          backgroundColor: hexToRgba(COLORS.R_obj, 0.62),
          borderWidth: 1,
          data: pack.empty ? Array(SLOT_COUNT).fill(0) : pack.rObj,
        },
        {
          type: "bar",
          label: "R_subj",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.R_subj,
          backgroundColor: hexToRgba(COLORS.R_subj, 0.62),
          borderWidth: 1,
          data: pack.empty ? Array(SLOT_COUNT).fill(0) : pack.rSubj,
        },
        {
          type: "bar",
          label: "Cost_stop",
          stack: stackId,
          yAxisID: "y",
          order: 2,
          borderColor: COLORS.Cost_stop,
          backgroundColor: hexToRgba(COLORS.Cost_stop, 0.62),
          borderWidth: 1,
          data: pack.empty ? Array(SLOT_COUNT).fill(0) : pack.costStop,
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
          spanGaps: false,
          data: pack.empty ? Array(SLOT_COUNT).fill(null) : pack.gap,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      /** 差分 update では 'none' を使うため、既定は短めのみ */
      animation: { duration: 180 },
      interaction: { mode: "index", intersect: false },
      color: CHART_AXIS.tickMuted,
      font: {
        family: "system-ui, -apple-system, 'Segoe UI', sans-serif",
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title(items) {
              if (!items.length) return "";
              const ch = items[0].chart;
              const meta = ch.$demoMeta || {
                maxSteps: pack.maxSteps,
                stepsPerBin: pack.stepsPerBin,
              };
              const idx = items[0].dataIndex;
              const lo = idx * meta.stepsPerBin;
              if (lo >= meta.maxSteps) return "シミュレーション外";
              const hi = Math.min(
                meta.maxSteps - 1,
                lo + meta.stepsPerBin - 1
              );
              const range =
                meta.stepsPerBin === 1
                  ? "ステップ " + lo
                  : "ステップ " + lo + "–" + hi;
              return (
                range +
                (meta.stepsPerBin > 1
                  ? "（" + meta.stepsPerBin + " ステップ/帯）"
                  : "")
              );
            },
            label(ctx) {
              const py =
                ctx.parsed && typeof ctx.parsed.y === "number"
                  ? ctx.parsed.y
                  : null;
              const name = ctx.dataset.label || "";
              if (ctx.dataset.type === "line" && py == null) {
                return name + ": （未計測）";
              }
              return name + ": " + (py != null ? py.toFixed(2) : "—");
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { color: CHART_AXIS.tick, maxRotation: 0 },
          grid: { color: CHART_AXIS.gridX },
          border: { color: CHART_AXIS.gridY },
          title: {
            display: true,
            text:
              "ステップ（横 " +
              SLOT_COUNT +
              " 帯" +
              (pack.stepsPerBin > 1 ? "・" + pack.stepsPerBin + " ステップ/帯" : "") +
              "）",
            color: CHART_AXIS.title,
            font: { size: 10 },
          },
        },
        y: {
          stacked: true,
          min: 0,
          suggestedMax: pack.ySuggestedMax,
          ticks: { color: CHART_AXIS.tick },
          grid: { color: CHART_AXIS.gridY },
          border: { color: CHART_AXIS.gridY },
          title: { display: false },
        },
        y1: {
          position: "right",
          min: 0,
          max: 1,
          grid: { drawOnChartArea: false },
          ticks: { color: CHART_AXIS.gapTick },
          border: { color: CHART_AXIS.gridY },
          title: {
            display: true,
            text: "Gap",
            color: CHART_AXIS.gapTitle,
            font: { size: 10 },
          },
        },
      },
    },
  });
}

/**
 * リスク推移: Chart.js の積み上げバー（R_obj / R_subj / Cost_stop）＋ Gap 折れ線（右軸）。
 * X 軸は常に SLOT_COUNT 本。max_steps が大きいときは複数ステップを1帯にまとめる。
 * 同一 max_steps／まとめ幅のあいだは destroy せず update のみ（全体の作り直しを避ける）。
 * @see https://www.chartjs.org/docs/latest/samples/other-charts/combo-bar-line.html
 */
export function drawChart(series, maxStepsArg) {
  const canvas = $("chart");
  const ChartCtor = typeof Chart !== "undefined" ? Chart : null;
  if (!canvas || !ChartCtor) return;

  const maxSteps = Math.max(1, parseInt(maxStepsArg, 10) || 40);
  const pack = computeSlotData(series, maxSteps);

  if (chartNeedsRebuild(pack)) {
    if (riskChart) {
      riskChart.destroy();
      riskChart = null;
    }
    riskChart = createRiskChart(canvas, ChartCtor, pack);
    riskChart.$demoMeta = {
      maxSteps: pack.maxSteps,
      stepsPerBin: pack.stepsPerBin,
    };
    return;
  }

  applyDataToChart(pack);
  /** アニメ無しでデータ差分のみ反映（毎ステップの「全消し→再描画」感を抑える） */
  riskChart.update("none");
}
