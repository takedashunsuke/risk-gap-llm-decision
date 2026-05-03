/** DOM id ショートカット */
export function $(id) {
  return document.getElementById(id);
}

export function fmt(x) {
  if (x === undefined || x === null) return "—";
  return x;
}

export function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function escAttr(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

export function num01(x) {
  if (x === undefined || x === null) return null;
  const n = parseFloat(x);
  if (Number.isNaN(n)) return null;
  return Math.max(0, Math.min(1, n));
}

export async function api(path, opt) {
  const res = await fetch(path, opt);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
