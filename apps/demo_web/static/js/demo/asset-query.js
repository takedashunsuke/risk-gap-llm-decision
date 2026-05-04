/**
 * 同一ページ読み込み内で ?t= を揃える（entry → app → 各モジュールの import.meta.url へ伝播）
 */
export function siblingImportQuery(importMetaUrl) {
  try {
    const t = new URL(importMetaUrl).searchParams.get("t");
    if (t) return `?t=${encodeURIComponent(t)}`;
  } catch (_) {}
  return `?t=${Date.now()}`;
}
