import { siblingImportQuery } from "./asset-query.js";

const q = siblingImportQuery(import.meta.url);
const { $ } = await import(`./util.js${q}`);
const { LLM_PLACEHOLDER } = await import(`./constants.js${q}`);

export function setLlmContent(text) {
  const el = $("llm-text");
  if (!el) return;
  const raw = text != null ? String(text).trim() : "";
  el.textContent = raw || LLM_PLACEHOLDER;
  el.classList.toggle("llm--placeholder", !raw);
}
