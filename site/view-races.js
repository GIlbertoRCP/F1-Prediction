// Every race, by season; a row opens the forecast against the result. #race-YYYY-RR opens one directly.

import { colour } from "./names.js";
import { $, esc, fmtDate, fmtStamp, getJSON, pageCache, tower, whole } from "./ui.js";

/* ---------- race browser ---------- */
export function renderRaces(index, tr) {
  const settled = Object.fromEntries(tr.races.map((r) => [`${r.season}-${r.round}`, r]));
  const sel = $("#season-filter");
  const seasons = [...new Set(index.map((r) => r.season))].sort((a, b) => b - a);
  sel.innerHTML = seasons.map((s) => `<option>${s}</option>`).join("");
  const list = $("#race-list");
  const draw = () => {
    const season = Number(sel.value);
    list.innerHTML = "";
    index.filter((r) => r.season === season).sort((a, b) => b.round - a.round).forEach((r) => {
      const s = settled[r.key];
      const li = document.createElement("li");
      li.id = `race-${r.key}`;
      const call = s ? `${s.pick} ${whole(s.pick_p)}` : "Forecast open";
      const res = !s ? `<span class="res">Open</span>`
        : s.hit ? `<span class="res hit">Called it</span>` : `<span class="res miss">${esc(s.winner)} won</span>`;
      li.innerHTML = `<button class="race-row" aria-expanded="false">
        <span class="date">${fmtDate(r.date, { day: "numeric", month: "short" })}</span>
        <span class="name">${esc(r.race)}</span>
        <span class="call">${esc(call)}</span>${res}<span class="chev" aria-hidden="true">▸</span></button>`;
      const btn = $("button", li);
      btn.onclick = async () => {
        const open = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!open));
        const existing = $(".detail", li);
        if (open) { existing.remove(); return; }
        const page = pageCache[r.key] ||= await getJSON(`data/races/${r.key}.json`);
        li.append(detail(page));
      };
      list.append(li);
    });
  };
  sel.onchange = draw;
  draw();
  // #race-2025-22 opens that race in the list, so other sections (and shared links) can point at a race
  const openFromHash = () => {
    const key = location.hash.match(/^#race-(\d{4}-\d+)$/)?.[1];
    const race = key && index.find((x) => x.key === key);
    if (!race) return;
    if (sel.value !== String(race.season)) { sel.value = String(race.season); draw(); }
    const li = document.getElementById(`race-${key}`), btn = li && $("button", li);
    if (btn?.getAttribute("aria-expanded") === "false") btn.click();
    li?.scrollIntoView({ block: "start" });
  };
  window.addEventListener("hashchange", openFromHash);
  openFromHash();
}

export function detail(page) {
  const d = document.createElement("div");
  d.className = "detail";
  const winnerId = page.result?.winner_id || null;
  const kind = page.kind === "live"
    ? `Live forecast, frozen ${fmtStamp(page.made_at)}.`
    : "Replay: made from earlier races only, using the final starting grid.";
  d.innerHTML = `<div class="cols"><div><h4>Chance of winning</h4></div><div>${page.result ? "<h4>How it finished</h4>" : ""}</div></div>`;
  const [left, right] = d.querySelectorAll(".cols > div");
  left.append(tower(page.predictions, { winnerId, limit: 8 }));
  left.insertAdjacentHTML("beforeend", `<p class="note">${kind}</p>`);
  if (page.result) {
    right.insertAdjacentHTML("beforeend", `<ol class="finish">${page.result.finishers.slice(0, 8).map((f) => `
      <li><span class="rk num">${f.pos}</span><span class="tick" style="background:${colour(f.team)}"></span>
      <span><b>${esc(f.driver)}</b> <span class="grid">from P${f.grid}</span></span></li>`).join("")}</ol>`);
  }
  return d;
}
