// Your pick for the race and how your picks have scored against the model's (stored in this browser only).

import { colour } from "./names.js";
import { loadPicks, savePick, tally } from "./picks.js";
import { $, esc, getJSON, pageCache, pct, whole } from "./ui.js";

/* ---------- your pick ---------- */
export function pickPanel(forecast, record) {
  const key = `${forecast.race.season}-${forecast.race.round}`;
  const box = document.createElement("div");
  box.className = "pickbox";
  const draw = () => {
    const mine = loadPicks()[key]?.driver_id;
    const oracle = forecast.predictions[0];
    box.innerHTML = `
      <h3>Who wins? Make your pick</h3>
      <p class="fine">${mine
        ? `You picked <b>${esc(forecast.predictions.find((p) => p.driver_id === mine)?.driver ?? mine)}</b>; Automata's favourite is ${esc(oracle.driver)}. Change it any time before the start.`
        : `Automata's favourite is ${esc(oracle.driver)}. Longshots pay more: a correct pick scores 1 ÷ Automata's chance.`}</p>
      <div class="chips" role="group" aria-label="Pick the winner">
        ${forecast.predictions.map((p) => `<button class="chip" type="button" data-id="${esc(p.driver_id)}" aria-pressed="${p.driver_id === mine}">
          <span class="tick" style="background:${colour(p.team)}"></span><b>${esc(p.driver)}</b><span class="num">${pct(p.p)}</span></button>`).join("")}
      </div>`;
    box.querySelectorAll(".chip").forEach((b) => (b.onclick = () => { savePick(key, b.dataset.id); draw(); renderPicks(record); }));
  };
  draw();
  return box;
}

export async function renderPicks(record) {
  const el = $("#picks");
  const picks = loadPicks();
  const settled = Object.fromEntries(record.races.map((r) => [`${r.season}-${r.round}`, r]));
  const keys = Object.keys(picks).filter((k) => settled[k]);
  if (!keys.length) { el.hidden = true; return; }
  const pages = {};
  await Promise.all(keys.map(async (k) => { pages[k] = pageCache[k] ||= await getJSON(`data/races/${k}.json`); }));
  const t = tally(picks, settled, pages);
  el.hidden = false;
  const verdict = t.you.points > t.oracle.points ? "You are ahead of Automata." : t.you.points < t.oracle.points ? "Automata is ahead." : "You are level with Automata.";
  $("#picks-body").innerHTML = `
    <p class="lede">After ${t.you.n} race${t.you.n > 1 ? "s" : ""} you have <b>${t.you.points} points</b> and Automata's top pick has <b>${t.oracle.points}</b>. ${verdict}</p>
    <p class="fine">Winners called: you ${t.you.wins}, Automata ${t.oracle.wins}. Picks are saved in this browser only.</p>
    <div class="tablewrap"><table>
      <thead><tr><th>Race</th><th>Your pick</th><th>Winner</th><th>You</th><th>Automata top pick</th></tr></thead>
      <tbody>${t.rows.map((r) => `<tr><td>${esc(r.race)}</td><td>${esc(r.pick)} (${whole(r.pick_p)})</td><td>${esc(r.winner)}</td>
        <td>${r.points}</td><td>${esc(r.oracle_pick)}: ${r.oracle_points}</td></tr>`).join("")}</tbody>
    </table></div>`;
}
