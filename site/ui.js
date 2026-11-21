// Helpers every section uses, and the timing tower.

import { colour } from "./names.js";

// Shared state: the circuit outlines, loaded once at boot.
export const store = { circuits: null };

export const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const pageCache = {};
export const $ = (sel, root = document) => root.querySelector(sel);
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const pct = (p) => (p < 0.005 ? "<1%" : p < 0.1 ? `${(p * 100).toFixed(1)}%` : `${Math.round(p * 100)}%`);
// Title odds sit near 0 or 1 late in a season, so they get a finer scale; a simulation never proves certainty.
export const titlePct = (p) => (p >= 0.995 ? `${Math.min(99.9, p * 100).toFixed(1)}%` : p >= 0.1 ? `${Math.round(p * 100)}%` : p >= 0.001 ? `${(p * 100).toFixed(1)}%` : "<0.1%");
export const shownTitle = (r) => (r.title >= 0.001 ? r.title : 0);   // odds that display as "<0.1%" rank by expected points
export const whole = (p) => `${Math.round(p * 100)}%`;
export const getJSON = (path) => fetch(path).then((r) => { if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); });
export const shared = {};
export const getShared = (path) => (shared[path] ||= getJSON(path));   // one download for files several sections read
export const fmtDate = (iso, opts = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });
export const toInstant = (date, time) => (date && time ? new Date(`${date}T${time.endsWith("Z") ? time : time + "Z"}`) : null);
export const fmtInstant = (d) => d.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
export const finishLabel = (f) => (f == null ? "DNF" : `${ordinal(f)}`);
export const fmtStamp = (iso) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
// Fine print that backs a number up but would crowd the page: one click away instead of always on screen.
export const more = (html, label = "How we know") => `<details class="fold"><summary>${label}</summary>${html}</details>`;
export const ordinal = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };

/* ---------- the timing tower ---------- */
export function formStrip(recent) {
  if (!recent) return "";
  const cells = recent.map((f) => `<i class="${f === 1 ? "w" : f != null && f <= 3 ? "pd" : f == null ? "out" : ""}" title="${finishLabel(f)}">${f == null ? "R" : f}</i>`).join("");
  return `<span class="form" aria-label="Last ${recent.length} finishes: ${recent.map(finishLabel).join(", ")}">${cells}</span>`;
}

export function tower(predictions, { winnerId = null, limit = 10, animate = false, hold = false, form = false } = {}) {
  const ol = document.createElement("ol");
  ol.className = "tower" + (animate ? " animate" : "") + (form ? " withform" : "");
  const max = Math.max(...predictions.map((p) => p.p));
  const draw = (rows) => {
    ol.innerHTML = rows.map((p, i) => `
      <li class="${i === 0 ? "lead" : ""} ${p.driver_id === winnerId ? "winner" : ""}" style="--team:${colour(p.team)}">
        <span class="rk">${i + 1}</span>
        <span class="tick" style="background:${colour(p.team)}"></span>
        <span class="code" title="${esc(p.driver_id.replace(/_/g, " "))}">${esc(p.driver)}</span>
        ${form ? formStrip(p.recent) : `<span class="grid">${p.grid ? "P" + p.grid : ""}</span>`}
        <span class="track"><span class="fill" data-w="${(p.p / max) * 100}"></span></span>
        <span class="pct num">${pct(p.p)}</span>
      </li>`).join("");
    const fills = ol.querySelectorAll(".fill");
    const set = () => fills.forEach((f) => (f.style.width = f.dataset.w + "%"));
    ol._set = set;
    if (hold) return;
    animate ? requestAnimationFrame(() => requestAnimationFrame(set)) : set();
  };
  let rows = predictions.slice(0, limit);
  if (winnerId && !rows.some((r) => r.driver_id === winnerId)) rows = rows.concat(predictions.filter((r) => r.driver_id === winnerId));
  draw(rows);
  const wrap = document.createElement("div");
  wrap.release = () => ol._set();
  wrap.append(ol);
  if (predictions.length > rows.length) {
    const btn = document.createElement("button");
    btn.className = "more";
    btn.textContent = `Show all ${predictions.length} drivers`;
    btn.onclick = () => { hold = false; draw(predictions); btn.remove(); };
    wrap.append(btn);
  }
  return wrap;
}
