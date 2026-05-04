import { siblingImportQuery } from "./asset-query.js";

const q = siblingImportQuery(import.meta.url);
const { $ } = await import(`./util.js${q}`);

const RP_BG = {
  yama: "/static/image/yama.jpg",
  mori: "/static/image/mori.jpg",
  kouya: "/static/image/kouya.jpg",
  home: "/static/image/home.jpg",
  mori_yoru: "/static/image/mori_yoru.jpg",
  umi: "/static/image/umi.jpg",
};

const RP_LABEL = {
  yama: "山・登山口付近",
  mori: "森の中",
  kouya: "高地・荒野（コウヤ）",
  home: "帰還（ホーム）",
  mori_yoru: "森の夜（引き返せない）",
  umi: "ゴール（海）",
};

export function inferRpZone(data) {
  const phase = data.phase;
  const oc = data.outcome;
  const ms = Math.max(data.max_steps || 1, 1);
  const step = data.step || 0;
  if (phase === "ended") {
    if (oc === "avoided") return "home";
    if (oc === "accident") return "mori_yoru";
    if (oc === "cleared") return "umi";
  }
  const pr = step / ms;
  if (pr < 0.28) return "yama";
  if (pr < 0.55) return "mori";
  return "kouya";
}

const TRI_PARTY = [
  { dx: 0, dy: -5.4 },
  { dx: 6.0, dy: 3.7 },
  { dx: -6.0, dy: 3.7 },
];
const CIRCLE_TURNS = 2.2;
const CIRCLE_R_PCT = 2.85;
/** キャラ全体をやや下へ（%） */
const PARTY_DROP_Y = 3.2;

export function pulseTrailScene() {
  const el = document.querySelector(".trail-scene");
  if (!el) return;
  el.classList.remove("trail-scene--pulse");
  void el.offsetWidth;
  el.classList.add("trail-scene--pulse");
}

export function updateTrail(data) {
  const m = data.metrics || {};
  const r = typeof m.R_obj === "number" ? m.R_obj : 0;
  const progress = data.max_steps > 0 ? data.step / data.max_steps : 0;
  const walking =
    data.phase === "running" &&
    data.step < data.max_steps &&
    data.step >= 0;

  const zone = data.rp_zone || inferRpZone(data);
  const bg = $("trail-bg");
  if (bg && RP_BG[zone]) {
    bg.style.backgroundImage = 'url("' + RP_BG[zone] + '")';
  }

  const ang = progress * Math.PI * 2 * CIRCLE_TURNS;
  const baseX = 50 + Math.cos(ang) * CIRCLE_R_PCT;
  const baseY = 50 + Math.sin(ang) * CIRCLE_R_PCT + PARTY_DROP_Y;

  for (let i = 0; i < TRI_PARTY.length; i++) {
    const t = TRI_PARTY[i];
    const charRoot = $("trail-char-" + i);
    if (charRoot) {
      charRoot.style.left = baseX + t.dx + "%";
      charRoot.style.top = baseY + t.dy + "%";
    }
    const anchor = charRoot && charRoot.querySelector(".trail-char-anchor");
    if (anchor) {
      anchor.classList.toggle("trail-char-anchor--walk", !!walking);
    }
  }

  const veil = $("trail-veil");
  if (veil) {
    const op = Math.min(0.78, r * 0.92 + (m.gap_danger ? 0.08 : 0));
    veil.style.opacity = String(op);
  }

  const scene = document.querySelector(".trail-scene");
  if (scene) {
    scene.classList.toggle("trail-scene--danger", !!(m.gap_danger || r >= 0.42));
  }

  const z = data.rp_zone || inferRpZone(data);
  const zj = RP_LABEL[z] || z;
  $("trail-caption").textContent =
    `ステップ ${data.step} / ${data.max_steps} · 場所：${zj} · R_obj ≈ ${
      m.R_obj != null ? m.R_obj.toFixed(2) : "—"
    }`;
}
