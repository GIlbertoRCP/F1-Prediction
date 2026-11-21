// Boot: loads the data, renders each section (one view-*.js module per section) and adds the page-wide
// touches: the freshness note, the nav that follows the section on screen, and the motion.

import { $, fmtDate, getJSON, getShared, reduceMotion, store } from "./ui.js";
import { driverCards } from "./view-driver.js";
import { renderChampionship } from "./view-championship.js";
import { renderH2H } from "./view-h2h.js";
import { renderHero } from "./view-hero.js";
import { renderPicks } from "./view-picks.js";
import { renderRaces } from "./view-races.js";
import { renderRecord } from "./view-record.js";
import { renderSim } from "./view-sim.js";
import { renderStandings } from "./view-standings.js";

/* ---------- freshness ---------- */
const ago = (ms) => { const h = Math.round(ms / 36e5); return h < 1 ? "under an hour ago" : h < 48 ? `${h} hour${h === 1 ? "" : "s"} ago` : `${Math.round(h / 24)} days ago`; };

// The data refreshes every three hours from Friday to Monday (UTC). If a weekend refresh is overdue, say so on the
// page instead of quietly showing old odds.
function freshness(meta) {
  const at = new Date(meta.generated_at), age = Date.now() - at;
  if (isNaN(at)) return "";
  const weekend = [5, 6, 0, 1].includes(new Date().getUTCDay());
  if (weekend && age > 7 * 36e5)
    $("#forecast").insertAdjacentHTML("afterbegin", `<p class="stale" role="status">Last refreshed ${ago(age)}. An update is overdue, so these numbers may be behind.</p>`);
  return `Updated ${ago(age)}. `;
}

// Marks the nav link for the section on screen.
function navTracker() {
  const links = new Map([...document.querySelectorAll(".top nav a")].map((a) => [a.getAttribute("href").slice(1), a]));
  if (!("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach((a) => a.removeAttribute("aria-current"));
      links.get(e.target.id)?.setAttribute("aria-current", "true");
    }
  }, { rootMargin: "-45% 0px -50% 0px" });            // the section crossing the middle of the screen
  links.forEach((_, id) => { const sec = document.getElementById(id); if (sec) io.observe(sec); });
}

/* ---------- motion ---------- */
// Runs `fn` once, the first time `el` is on screen.
function onceVisible(el, fn, threshold = 0.2) {
  if (!("IntersectionObserver" in window)) { fn(); return; }
  const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); fn(); } }, { threshold });
  io.observe(el);
}

// Counts a number like "55%", "1.23" or "175" up from zero, keeping its decimals and suffix.
function countUp(el, ms = 900) {
  const m = el.textContent.match(/^(\D*)(\d+(?:\.\d+)?)(.*)$/);
  if (!m) return;
  const [, pre, num, post] = m, end = Number(num), dp = (num.split(".")[1] || "").length;
  el.setAttribute("aria-label", el.textContent);
  const t0 = performance.now();
  const frame = (t) => {
    const k = Math.min(1, (t - t0) / ms), eased = 1 - (1 - k) ** 3;
    el.textContent = `${pre}${(end * eased).toFixed(dp)}${post}`;
    if (k < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

function motion() {
  if (reduceMotion()) return;
  document.querySelectorAll(".block").forEach((b) => { b.classList.add("reveal"); onceVisible(b, () => b.classList.add("in"), 0.05); });
  document.querySelectorAll(".tile .v").forEach((v) => onceVisible(v, () => countUp(v), 0.6));
}

/* ---------- boot ---------- */
(async function main() {
  try {
    const [meta, forecast, record, index] = await Promise.all([
      getJSON("data/meta.json"), getShared("data/forecast.json"), getJSON("data/track_record.json"), getJSON("data/races.json"),
    ]);
    store.circuits = await getJSON("data/circuits.json").catch(() => null);
    await renderHero(forecast, record);
    renderRecord(record);
    renderRaces(index, record);
    renderPicks(record);
    renderChampionship(index, record).catch((e) => console.error(e));
    renderSim(index, forecast);
    renderStandings().catch((e) => { console.error(e); $("#standings-body").textContent = "Standings data is not available."; });
    renderH2H().catch((e) => { console.error(e); $("#h2h-body").textContent = "Head-to-head data is not available."; });
    motion();
    navTracker();
    driverCards();
    const through = meta.data_through;
    $("#foot-meta").textContent = freshness(meta) +
      `Model ${meta.model} (version ${meta.model_version}). Results through ${through ? `${through.race}, ${fmtDate(through.date)}` : "n/a"}. ` +
      `Live log: ${meta.live_log.detail}.`;
  } catch (err) {
    console.error(err);
    $("#forecast").innerHTML = `<h1>Could not load the data</h1><p class="sub">The files in <code>data/</code> are missing. Run <code>python3 -m oracle.publish</code>, then serve this folder.</p>`;
  }
})();
