import { siblingImportQuery } from "./asset-query.js";

const q = siblingImportQuery(import.meta.url);
const { $ } = await import(`./util.js${q}`);
const { LLM_PLACEHOLDER } = await import(`./constants.js${q}`);

export function setLlmContent(text) {
  const toastEl = $("llm-toast");
  const el = $("llm-text");
  if (!el || !toastEl) return;
  const raw = text != null ? String(text).trim() : "";
  const toast =
    typeof bootstrap !== "undefined" && bootstrap.Toast
      ? bootstrap.Toast.getOrCreateInstance(toastEl, { autohide: false })
      : null;
  el.textContent = raw || LLM_PLACEHOLDER;
  el.classList.toggle("llm--placeholder", !raw);
  if (raw) {
    if (toast) toast.show();
  } else if (toast) {
    toast.hide();
  }
}
