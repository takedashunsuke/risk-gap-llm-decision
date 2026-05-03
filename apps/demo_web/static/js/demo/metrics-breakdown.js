import { fmt, num01 } from "./util.js";

/** 主要指標カード: 黄（warn）／赤（danger）。主要指標ごとに閾値が異なる */
export function metricCardSeverityClass(key, m) {
  const T = num01(m.T);
  const tRef = T != null ? T : 0.6;
  const rObj = num01(m.R_obj);
  const rSubj = num01(m.R_subj);
  const gap = num01(m.Gap);
  const cost = num01(m.Cost_stop);
  const bias = num01(m.bias);
  const gapDanger = !!m.gap_danger;
  let danger = false;
  let warn = false;
  switch (key) {
    case "R_obj":
      danger = rObj != null && rObj >= 0.4;
      warn = !danger && rObj != null && rObj >= 0.28;
      break;
    case "R_subj":
      danger = rSubj != null && rSubj >= 0.38;
      warn = !danger && rSubj != null && rSubj >= 0.26;
      break;
    case "Gap":
      danger = gapDanger || (gap != null && gap >= 0.2);
      warn = !danger && gap != null && gap >= 0.1;
      break;
    case "T":
      if (rObj != null) {
        danger = rObj >= tRef * 0.92;
        warn = !danger && rObj >= tRef * 0.72;
      }
      break;
    case "Cost_stop":
      danger = cost != null && cost >= 0.32;
      warn = !danger && cost != null && cost >= 0.24;
      break;
    case "bias":
      danger = bias != null && bias >= 0.18;
      warn = !danger && bias != null && bias >= 0.13;
      break;
    default:
      break;
  }
  if (danger) return " metric-card--danger";
  if (warn) return " metric-card--warn";
  return "";
}

function breakdownBarFillClass(val) {
  const n = num01(val);
  if (n == null) return "bd-fill";
  if (n >= 0.45) return "bd-fill bd-fill--high";
  if (n >= 0.28) return "bd-fill bd-fill--mid";
  return "bd-fill";
}

function breakdownBarRow(labelHtml, val) {
  const n = num01(val);
  const pct = n == null ? 0 : Math.round(n * 100);
  const fillCls = breakdownBarFillClass(val);
  return (
    `<div class="bd-item">` +
    `<div class="bd-row bd-row--top">` +
    `<span class="bd-k">${labelHtml}</span>` +
    `<span class="bd-v">${fmt(val)}</span>` +
    `</div>` +
    `<div class="bd-track" role="presentation" aria-hidden="true">` +
    `<div class="${fillCls}" style="width:${pct}%"></div>` +
    `</div>` +
    `</div>`
  );
}

function breakdownBoolRow(labelHtml, cond) {
  return (
    `<div class="bd-row">` +
    `<span class="bd-k">${labelHtml}</span>` +
    `<span class="bd-v">${cond ? "はい" : "いいえ"}</span></div>`
  );
}

export function renderBreakdown(m) {
  const br = m.breakdown || {};
  const env = m.env || {};
  const hum = m.human || {};
  const pr = m.pressure || {};
  let h = `<div class="breakdown-rows">`;
  h +=
    `<p class="bd-legend small text-muted mb-2 mb-md-1">各数値は 0〜1。バーの長さがその因子の強さです（灰＝低め・黄＝中・赤＝高めの目安）。</p>`;
  h += `<div class="bd-section">合成（テーマ平均）</div>`;
  h += breakdownBarRow("環境テーマ平均（環境3項目の平均）", br.environment_avg);
  h += breakdownBarRow("人テーマ平均（疲労・注意の平均）", br.human_avg);
  h += breakdownBarRow("時間プレッシャー（pressure と共通スケール）", br.time_pressure);
  h += `<div class="bd-section">環境リスク（入力）</div>`;
  h += breakdownBarRow(`天候 <span class="mono">weather</span>`, env.weather);
  h += breakdownBarRow(`視界 <span class="mono">visibility</span>`, env.visibility);
  h += breakdownBarRow(`気温リスク <span class="mono">temp_risk</span>`, env.temp_risk);
  h += `<div class="bd-section">人（入力）</div>`;
  h += breakdownBarRow(`疲労 <span class="mono">fatigue</span>`, hum.fatigue);
  h += breakdownBarRow(`注意散漫 <span class="mono">attention_loss</span>`, hum.attention_loss);
  h += `<div class="bd-section">圧力（入力）</div>`;
  h += breakdownBarRow(`時間プレッシャー <span class="mono">time</span>`, pr.time);
  h += breakdownBarRow(`外部プレッシャー <span class="mono">external</span>`, pr.external);
  h += `<div class="bd-section">フラグ</div>`;
  h += breakdownBoolRow(
    `続行ルール成立 <span class="mono">(R_subj−Cost_stop)&lt;T</span>`,
    !!m.continue_rule_holds
  );
  h += breakdownBoolRow("Gap ≥ 0.2（要注意）", !!m.gap_danger);
  h += `</div>`;
  return h;
}
