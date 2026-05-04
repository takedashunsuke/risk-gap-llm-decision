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

/** 客観リスク内訳・上部固定：R_obj の合成材料となる3本のバー */
export function renderBreakdownSummary(m) {
  const br = m.breakdown || {};
  let h = `<div class="breakdown-rows breakdown-rows--summary">`;
  h += breakdownBarRow("環境テーマ平均", br.environment_avg);
  h += breakdownBarRow("人テーマ平均", br.human_avg);
  h += breakdownBarRow("時間プレッシャー", br.time_pressure);
  h += `</div>`;
  return h;
}

/**
 * タブ切替：環境 / 人 / 圧力 / フラグ（Bootstrap の tab。スクロールなし）
 */
export function renderBreakdownDetail(m) {
  const env = m.env || {};
  const hum = m.human || {};
  const pr = m.pressure || {};
  const envRows =
    breakdownBarRow("天候", env.weather) +
    breakdownBarRow("視界", env.visibility) +
    breakdownBarRow("気温リスク", env.temp_risk);
  const humRows =
    breakdownBarRow("疲労", hum.fatigue) +
    breakdownBarRow("注意散漫", hum.attention_loss);
  const prRows =
    breakdownBarRow("時間プレッシャー", pr.time) +
    breakdownBarRow("外部プレッシャー", pr.external);
  const flagRows =
    breakdownBoolRow("続行ルール成立", !!m.continue_rule_holds) +
    breakdownBoolRow("Gap ≥ 0.2", !!m.gap_danger);

  return (
    `<div class="breakdown-tabs">` +
    `<ul class="nav nav-tabs nav-tabs-sm breakdown-detail-nav" role="tablist">` +
    `<li class="nav-item" role="presentation">` +
    `<button class="nav-link active" id="bd-tab-env" type="button" role="tab" data-bs-toggle="tab" data-bs-target="#bd-pane-env" aria-controls="bd-pane-env" aria-selected="true">環境</button>` +
    `</li>` +
    `<li class="nav-item" role="presentation">` +
    `<button class="nav-link" id="bd-tab-human" type="button" role="tab" data-bs-toggle="tab" data-bs-target="#bd-pane-human" aria-controls="bd-pane-human" aria-selected="false">人</button>` +
    `</li>` +
    `<li class="nav-item" role="presentation">` +
    `<button class="nav-link" id="bd-tab-pressure" type="button" role="tab" data-bs-toggle="tab" data-bs-target="#bd-pane-pressure" aria-controls="bd-pane-pressure" aria-selected="false">圧力</button>` +
    `</li>` +
    `<li class="nav-item" role="presentation">` +
    `<button class="nav-link" id="bd-tab-flags" type="button" role="tab" data-bs-toggle="tab" data-bs-target="#bd-pane-flags" aria-controls="bd-pane-flags" aria-selected="false">フラグ</button>` +
    `</li>` +
    `</ul>` +
    `<div class="tab-content breakdown-detail-panels pt-2">` +
    `<div class="tab-pane fade show active" id="bd-pane-env" role="tabpanel" aria-labelledby="bd-tab-env" tabindex="0">` +
    `<div class="breakdown-rows">${envRows}</div>` +
    `</div>` +
    `<div class="tab-pane fade" id="bd-pane-human" role="tabpanel" aria-labelledby="bd-tab-human" tabindex="0">` +
    `<div class="breakdown-rows">${humRows}</div>` +
    `</div>` +
    `<div class="tab-pane fade" id="bd-pane-pressure" role="tabpanel" aria-labelledby="bd-tab-pressure" tabindex="0">` +
    `<div class="breakdown-rows">${prRows}</div>` +
    `</div>` +
    `<div class="tab-pane fade" id="bd-pane-flags" role="tabpanel" aria-labelledby="bd-tab-flags" tabindex="0">` +
    `<div class="breakdown-rows">${flagRows}</div>` +
    `</div>` +
    `</div>` +
    `</div>`
  );
}
