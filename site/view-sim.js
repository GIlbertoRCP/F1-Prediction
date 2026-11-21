// The race simulator: change the grid or take drivers out, and the race is re-run in the browser.

import { colour } from "./names.js";
import { simulate, summarize, utilities } from "./sim.js";
import { $, esc, getJSON, more, pageCache, pct } from "./ui.js";

/* ---------- race simulator ---------- */
export async function renderSim(index, forecast) {
  const el = $("#sim-body");
  const open = forecast.status === "open" ? `${forecast.race.season}-${forecast.race.round}` : null;
  const keys = (open && !index.some((r) => r.key === open) ? [{ key: open, race: forecast.race.race, season: forecast.race.season }] : []).concat(index);
  el.innerHTML = `
    <p class="fine">Change the grid or knock a driver out; the race re-runs thousands of times in your browser.</p>
    <div class="simbar">
      <label class="select">Race <select id="sim-race">${keys.map((r) => `<option value="${r.key}">${esc(r.season)} ${esc(r.race)}${r.key === open ? " (open forecast)" : ""}</option>`).join("")}</select></label>
      <label class="select">Simulated races <select id="sim-n"><option value="2000">2,000</option><option value="10000" selected>10,000</option><option value="50000">50,000</option></select></label>
      <button class="more" id="sim-reset" type="button">Reset changes</button>
    </div>
    <div id="sim-out"></div>`;
  const out = $("#sim-out");
  let page, grid, outSet;
  const load = async () => {
    const key = $("#sim-race").value;
    page = key === open ? { predictions: forecast.predictions, simulator: forecast.simulator }
      : (pageCache[key] ||= await getJSON(`data/races/${key}.json`));
    grid = Object.fromEntries(page.predictions.map((p) => [p.driver_id, p.grid]));
    outSet = new Set();
    draw();
  };
  const edited = () => outSet.size > 0 || page.predictions.some((p) => grid[p.driver_id] !== p.grid);
  const draw = () => {
    const sim = page.simulator;
    if (!sim) { out.innerHTML = `<p>This race has no simulator data yet.</p>`; return; }
    const n = Number($("#sim-n").value);
    const counts = simulate(utilities(sim, grid), sim.model.scales, n, { out: outSet, seed: 1 });
    const rows = summarize(counts, n);
    const info = Object.fromEntries(page.predictions.map((p) => [p.driver_id, p]));
    const isEdited = edited();
    const maxSlot = Math.max(...Object.values(info).map((p) => p.grid));
    const order = rows.slice().sort((a, b) => b.win - a.win || a.driver_id.localeCompare(b.driver_id));
    out.innerHTML = `<div class="tablewrap"><table class="simtable">
      <thead><tr><th>Driver</th><th>Starts</th><th>Win</th>${isEdited ? "<th>Change</th>" : ""}<th>Podium</th><th>Average finish</th><th>Where they finish</th></tr></thead>
      <tbody>${order.map((r) => {
        const p = info[r.driver_id];
        const d = (r.win - p.p) * 100;
        return `<tr class="${r.out ? "isout" : ""}">
          <td><span class="tick inline" style="background:${colour(p.team)}"></span><b>${esc(p.driver)}</b></td>
          <td><select class="slot" data-id="${esc(r.driver_id)}" aria-label="Starting slot for ${esc(p.driver)}">${Array.from({ length: maxSlot }, (_, i) => `<option${grid[r.driver_id] === i + 1 ? " selected" : ""}>${i + 1}</option>`).join("")}</select>
            <label class="outbox"><input type="checkbox" class="out" data-id="${esc(r.driver_id)}"${r.out ? " checked" : ""}> Out</label></td>
          <td class="num">${r.out ? "–" : pct(r.win)}</td>
          ${isEdited ? `<td class="num ${d > 0.05 ? "up" : d < -0.05 ? "down" : ""}">${r.out || Math.abs(d) < 0.05 ? "" : (d > 0 ? "+" : "") + d.toFixed(1) + " pts"}</td>` : ""}
          <td class="num">${r.out ? "–" : pct(r.podium)}</td>
          <td class="num">${r.avg ? r.avg.toFixed(1) : "–"}</td>
          <td><span class="strip" aria-hidden="true">${r.dist.map((q, i) => `<i style="opacity:${Math.sqrt(q).toFixed(2)}" title="P${i + 1}: ${(q * 100).toFixed(1)}%"></i>`).join("")}</span></td>
        </tr>`;
      }).join("")}</tbody></table></div>
      <p class="fine">First to last, left to right; darker is likelier.</p>
      ${more(`<p class="fine">Win and podium odds are checked against history. Positions below third are rougher, so read the strip as a rough shape. See <code>reports/ordered.md</code>.</p>`)}`;
    out.querySelectorAll(".slot").forEach((sel) => (sel.onchange = () => {
      const id = sel.dataset.id, target = Number(sel.value), old = grid[id];
      const other = Object.keys(grid).find((d) => d !== id && grid[d] === target);
      grid[id] = target;
      if (other) grid[other] = old;
      draw();
    }));
    out.querySelectorAll(".out").forEach((cb) => (cb.onchange = () => { cb.checked ? outSet.add(cb.dataset.id) : outSet.delete(cb.dataset.id); draw(); }));
  };
  $("#sim-race").onchange = load;
  $("#sim-n").onchange = draw;
  $("#sim-reset").onclick = load;
  await load();
}
