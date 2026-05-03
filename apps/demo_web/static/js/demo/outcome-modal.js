import { $ } from "./util.js";

export function openOutcomeModal(data) {
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
