// Head to head: teammate battles and any two drivers compared, counted from real results.

import { compare, teammatePairs } from "./h2h.js";
import { colour } from "./names.js";
import { $, esc, getShared, more } from "./ui.js";

/* ---------- head to head ---------- */
export function split(a, b, fmt = (v) => v) {
  const total = a + b;
  const wa = total ? (a / total) * 100 : 50;
  return `<span class="split" role="img" aria-label="${fmt(a)} to ${fmt(b)}"><b class="num">${fmt(a)}</b>
    <span class="bar"><i style="width:${wa}%"></i></span><b class="num">${fmt(b)}</b></span>`;
}
export const one = (v) => (Math.round(v * 10) / 10).toFixed(1);

export async function renderH2H() {
  const el = $("#h2h-body");
  const data = await getShared("data/h2h.json");
  const years = Object.keys(data).sort((a, b) => b - a);
  el.innerHTML = `
    ${more(`<p class="fine">Counted from qualifying positions and race finishes in rounds where both drivers took part. A retirement counts as finishing behind anyone who finished; if both retire, the race does not count for either.</p>`, "How it's counted")}
    <div class="simbar"><label class="select">Season <select id="h2h-year">${years.map((y) => `<option>${y}</option>`).join("")}</select></label></div>
    <h3>Teammates</h3><div id="h2h-team"></div>
    <h3>Compare any two drivers</h3><div id="h2h-any"></div>`;
  const draw = () => {
    const season = data[$("#h2h-year").value];
    const drv = season.drivers;
    const name = (id) => esc(drv[id].code);
    const teamOf = (id) => drv[id].team.find(Boolean);
    const pairs = teammatePairs(season);
    $("#h2h-team").innerHTML = `<div class="tablewrap"><table class="simtable h2htable">
      <thead><tr><th>Teammates</th><th>Races together</th><th>Qualifying</th><th>Race</th><th>Points</th></tr></thead>
      <tbody>${pairs.map((p) => `<tr>
        <td><span class="tick inline" style="background:${colour(p.team)}"></span><b>${name(p.a)}</b> vs <b>${name(p.b)}</b></td>
        <td class="num" data-label="Races together">${p.sameTeam}</td>
        <td data-label="Qualifying">${split(p.quali.a, p.quali.b)}</td><td data-label="Race">${split(p.race.a, p.race.b)}</td><td data-label="Points">${split(p.points.a, p.points.b, (v) => Math.round(v))}</td></tr>`).join("")}</tbody></table></div>
      <p class="fine">Rounds won by each driver. Race points only, no sprints.</p>`;
    const ids = Object.keys(drv).sort((a, b) => drv[a].code.localeCompare(drv[b].code));
    const opts = (sel) => ids.map((id) => `<option value="${esc(id)}"${id === sel ? " selected" : ""}>${esc(drv[id].code)} (${esc(teamOf(id))})</option>`).join("");
    const first = pairs[0] || { a: ids[0], b: ids[1] };
    $("#h2h-any").innerHTML = `<div class="simbar">
        <label class="select">Driver <select id="h2h-a">${opts(first.a)}</select></label>
        <label class="select">against <select id="h2h-b">${opts(first.b)}</select></label></div>
      <div id="h2h-result"></div>`;
    const show = () => {
      const a = $("#h2h-a").value, b = $("#h2h-b").value;
      if (a === b) { $("#h2h-result").innerHTML = `<p>Pick two different drivers.</p>`; return; }
      const c = compare(season, a, b);
      if (!c.together) { $("#h2h-result").innerHTML = `<p>${name(a)} and ${name(b)} did not race in the same rounds this season.</p>`; return; }
      const row = (label, html) => `<tr><th scope="row">${label}</th><td>${html}</td></tr>`;
      $("#h2h-result").innerHTML = `<div class="tablewrap"><table class="simtable"><tbody>
        ${row("Races together", `<b class="num">${c.together}</b>`)}
        ${row("Qualified ahead", split(c.quali.a, c.quali.b))}
        ${row("Finished ahead", split(c.race.a, c.race.b))}
        ${row("Race points", split(c.points.a, c.points.b, (v) => Math.round(v)))}
        ${c.avgQuali ? row("Average qualifying position", split(c.avgQuali.a, c.avgQuali.b, one)) : ""}
        ${c.avgFinish ? row("Average finish (both finished)", split(c.avgFinish.a, c.avgFinish.b, one)) : ""}
        ${row("Retirements", split(c.dnf.a, c.dnf.b))}
        </tbody></table></div>
        ${c.sameTeam === c.together ? "" : `<p class="fine">${c.sameTeam === 0
            ? "Not teammates, so this mostly compares their cars."
            : `Teammates in ${c.sameTeam} of ${c.together} rounds, so this partly compares cars.`}</p>`}`;
    };
    $("#h2h-a").onchange = show; $("#h2h-b").onchange = show;
    show();
  };
  $("#h2h-year").onchange = draw;
  draw();
}
