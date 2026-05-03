import { $ } from "./util.js";
import { LLM_PLACEHOLDER } from "./constants.js";

export function setLlmContent(text) {
  const el = $("llm-text");
  if (!el) return;
  const raw = text != null ? String(text).trim() : "";
  el.textContent = raw || LLM_PLACEHOLDER;
  el.classList.toggle("llm--placeholder", !raw);
}
