// Season standings for drivers and constructors, with the points chart.

import { lineChart } from "./linechart.js";
import { colour, teamName } from "./names.js";
import { driverStandings, teamStandings } from "./standings.js";
import { $, esc, getShared } from "./ui.js";

/* ---------- standings ---------- */
export const fmtPts = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

export async function renderStandings() {
  const el = $("#standings-body");
  const data = await getShared("data/h2h.json");
  const years = Object.keys(data).sort((a, b) => b - a);
  el.innerHTML = `
    <div class="simbar">
      <label class="select">Season <select id="st-year">${years.map((y) => `<option>${y}</option>`).join("")}</select></label>
      <span class="seg" role="group" aria-label="Championship">
        <button type="button" id="st-d" aria-pressed="true">Drivers</button>
        <button type="button" id="st-c" aria-pressed="false">Constructors</button>
      </span>
    </div>
    <p class="fine" id="st-note"></p>
    <div id="st-chart"></div>
    <div id="st-table"></div>`;
  let kind = "d";
  const draw = () => {
    const year = $("#st-year").value, season = data[year];
    const rounds = season.rounds.length;
    const rows = kind === "d" ? driverStandings(season) : teamStandings(season);
    const nPlayed = rounds;
    $("#st-note").textContent = `After ${nPlayed} round${nPlayed === 1 ? "" : "s"}${season.rounds[nPlayed - 1] ? `, ${season.rounds[nPlayed - 1].race}` : ""}. Race points plus sprint points.`;
    // chart: five leaders; a team's second driver gets a dashed line
    const seen = {};
    const series = rows.slice(0, 5).map((r) => {
      const dash = kind === "d" && seen[r.team] ? "7 5" : null;
      seen[r.team] = true;
      return { name: kind === "d" ? r.code : teamName(r.team), color: colour(r.team), dash, values: r.cumulative };
    });
    lineChart($("#st-chart"), series, [""].concat(season.rounds.map((r) => String(r.round))), { unit: "points" });
    $("#st-table").innerHTML = `<div class="tablewrap"><table class="simtable"><thead><tr>
      <th>Pos</th><th>${kind === "d" ? "Driver" : "Team"}</th>${kind === "d" ? '<th class="tl">Team</th>' : ""}<th>Points</th><th>Wins</th>${kind === "d" ? "<th>Podiums</th>" : ""}</tr></thead>
      <tbody>${rows.map((r, i) => `<tr><td class="num">${i + 1}</td>
        <td><span class="tick inline" style="background:${colour(r.team)}"></span><b>${esc(kind === "d" ? r.code : teamName(r.team))}</b></td>
        ${kind === "d" ? `<td class="tl">${esc(teamName(r.team))}</td>` : ""}
        <td class="num">${fmtPts(r.points)}</td><td class="num">${r.wins}</td>${kind === "d" ? `<td class="num">${r.podiums}</td>` : ""}</tr>`).join("")}</tbody></table></div>
      <p class="fine">${kind === "d" ? "Ties are split by best finishes." : "Every car's points count, whoever drove it."}</p>`;
  };
  $("#st-year").onchange = draw;
  const setKind = (k) => { kind = k; $("#st-d").setAttribute("aria-pressed", String(k === "d")); $("#st-c").setAttribute("aria-pressed", String(k === "c")); draw(); };
  $("#st-d").onclick = () => setKind("d");
  $("#st-c").onclick = () => setKind("c");
  draw();
}
