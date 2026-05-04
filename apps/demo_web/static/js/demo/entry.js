/**
 * index.html から import されるとき import.meta.url に ?t= が付く想定。
 * 単体で開かれた場合は自前で t を付与する。
 */
const t = new URL(import.meta.url).searchParams.get("t") || String(Date.now());
await import(`./app.js?t=${encodeURIComponent(t)}`);
