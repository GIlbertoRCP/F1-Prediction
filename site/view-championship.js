// Championship outlook: title odds, races left, how the odds moved, and how far to trust them.

import { lineChart } from "./linechart.js";
import { colour, teamName } from "./names.js";
import { clinched } from "./standings.js";
import { titleStory, forecastStory } from "./recap.js";
import { $, esc, fmtStamp, getJSON, getShared, more, pct, shownTitle, titlePct, whole } from "./ui.js";
import { fmtPts } from "./view-standings.js";

/* ---------- championship ---------- */
export function rangeRow(r, i, axisMax, label, cls = "", pct = titlePct(r.title)) {
  const at = (v) => `${Math.min(100, (v / axisMax) * 100).toFixed(2)}%`;
  return `<li class="${cls}" style="--team:${colour(r.team)}">
    <span class="rk">${i + 1}</span><span class="tick" style="background:${colour(r.team)}"></span>
    <span class="code" title="${esc(label)}">${esc(label)}</span>
    <span class="pts num">${fmtPts(r.points)} pts</span>
    <span class="range" role="img" aria-label="${esc(label)}: ${fmtPts(r.points)} points now; most likely finish between ${Math.round(r.p10)} and ${Math.round(r.p90)}">
      <span class="axis"></span>
      <span class="span" style="left:${at(r.p10)};width:calc(${at(r.p90)} - ${at(r.p10)})"></span>
      <span class="now" style="left:${at(r.points)}"></span>
      <span class="mid" style="left:${at(r.p50)}"></span>
    </span>
    <span class="pct num">${pct}</span></li>`;
}

// A finished season, told in four tiles: both champions and when it was settled, and how the race forecasts did.
async function seasonInReview(cur, record) {
  const season = (await getShared("data/h2h.json"))[cur.season];
  if (!season) return "";
  const d = titleStory(season, "d"), c = titleStory(season, "c"), f = forecastStory(record.races, cur.season);
  const settled = (t) => (t.left ? `settled after round ${t.settledAfter}, with ${t.left} to go` : "settled at the last round");
  const champTile = (t, name, what) => `<div class="tile best"><span class="v">${esc(name)}</span>
    <span class="l">${what} champion on ${fmtPts(t.champ.points)} points, ${fmtPts(t.margin)} clear; ${settled(t)}</span></div>`;
  return `<h3>${cur.season} in review</h3>
    <div class="tiles">
      ${champTile(d, d.champ.code, "Drivers'")}
      ${champTile(c, teamName(c.champ.id), "Constructors'")}
      ${f ? `<div class="tile"><span class="v">${f.hits} of ${f.n}</span><span class="l">races won by our favourite, with ${f.winners} different winners</span></div>
      <div class="tile warn"><span class="v">${pct(f.upset.p_winner)}</span><span class="l">biggest upset: ${esc(f.upset.winner)} won the ${esc(f.upset.race.replace(/ Grand Prix$/, " GP"))}</span></div>` : ""}
    </div>
    ${f?.bestCall ? `<p class="fine">Best call: ${esc(f.bestCall.winner)} at ${whole(f.bestCall.p_winner)} for the ${esc(f.bestCall.race)}.${f.live ? ` ${f.live} of these races were live forecasts, frozen before the start; the rest are replays.` : ""}</p>` : ""}`;
}

export async function renderChampionship(index, record) {
  const sec = $("#championship");
  let data;
  try { data = await getJSON("data/championship.json"); } catch { return; }
  const cur = data.current;
  if (!cur) return;
  sec.hidden = false;
  const el = $("#champ-body");
  const played = cur.after_round;
  const total = played + cur.remaining.length;
  let kind = "d";
  el.innerHTML = `
    <p class="lede-line" id="ch-lede"></p>
    <div id="ch-review"></div>
    <div class="simbar">
      <span class="seg" role="group" aria-label="Championship">
        <button type="button" id="ch-d" aria-pressed="true">Drivers</button>
        <button type="button" id="ch-c" aria-pressed="false">Constructors</button>
      </span>
    </div>
    <div id="ch-tower"></div>
    <p class="legend-note" ${cur.remaining.length ? "" : "hidden"}><span><i style="background:var(--ink);width:3px;height:12px"></i>points now</span>
      <span><i style="background:var(--bar-soft);opacity:.7"></i>80% range for the final total</span>
      <span><i style="background:var(--slate);width:3px;height:12px"></i>middle outcome</span></p>
    ${cur.remaining.length ? '<h3>Races left</h3><ul class="remain" id="ch-left"></ul>' : ""}
    <h3>How the odds moved</h3>
    <div class="simbar"><label class="select">Season <select id="ch-season"></select></label></div>
    <p class="fine" id="ch-note"></p>
    <div id="ch-chart"></div>
    <div id="ch-trust"></div>`;
  // each race left links to its forecast if it is next, else to the last time the series raced there
  const lastHere = (race) => index.filter((x) => x.race === race && x.season < cur.season).sort((a, b) => b.season - a.season)[0];
  if (cur.remaining.length) $("#ch-left").innerHTML = cur.remaining.map((r, i) => {
    const prev = i ? lastHere(r.race) : null;
    const href = i === 0 ? "#forecast" : prev ? `#race-${prev.key}` : null;
    const body = `<b>R${r.round}</b> ${esc(r.race.replace(/ Grand Prix$/, " GP"))}${r.sprint ? '<span class="s" title="Sprint weekend">Sprint</span>' : ""}${href ? `<small>${i === 0 ? "Next" : prev.season}</small>` : ""}`;
    return `<li>${href ? `<a href="${href}" title="${i === 0 ? "The forecast for this race" : `How the ${prev.season} race here went`}">${body}</a>` : body}</li>`;
  }).join("");

  const drawTower = () => {
    const rows = (kind === "d" ? cur.drivers.filter((d) => d.racing) : cur.teams).slice()
      .sort((a, b) => shownTitle(b) - shownTitle(a) || b.mean - a.mean);
    const shown = rows.slice(0, 10);
    const axisMax = Math.max(...shown.map((r) => r.p90)) * 1.03;
    const label = (r) => (kind === "d" ? r.code : teamName(r.team));
    const lead = rows[0];
    const second = rows[1];
    const title = `${cur.season} ${kind === "d" ? "drivers'" : "constructors'"} title`;
    const left = `${cur.remaining.length} race${cur.remaining.length === 1 ? "" : "s"} to go`;
    // a title decided on points is a fact, not a 99.9% forecast: say so and drop the odds column
    const champ = clinched(kind === "d" ? cur.drivers : cur.teams, cur.remaining, kind);
    $("#ch-lede").innerHTML = champ
      ? `<b>${esc(label(champ))}</b> has won the ${title}${cur.remaining.length ? `, with ${left.replace(" to go", " left")}` : ""}.`
      : `After round ${played} of ${total}, <b>${esc(label(lead))}</b> has a <b>${titlePct(lead.title)}</b> chance of the ${title}${second && second.title >= 0.001 ? `; ${esc(label(second))} is next at ${titlePct(second.title)}` : ""}. ${left}.`;
    const pct = (r) => (!champ ? titlePct(r.title) : r === champ ? '<span class="champ">Champion</span>' : "");
    $("#ch-tower").innerHTML = `<ol class="tower title ${kind === "c" ? "teams" : ""}">${shown.map((r, i) => rangeRow(r, i, axisMax, label(r), (champ ? r !== champ : r.title < 0.001 && i > 0) ? "dim" : "", pct(r))).join("")}</ol>`;
  };
  const setKind = (k) => { kind = k; $("#ch-d").setAttribute("aria-pressed", String(k === "d")); $("#ch-c").setAttribute("aria-pressed", String(k === "c")); drawTower(); };
  $("#ch-d").onclick = () => setKind("d");
  $("#ch-c").onclick = () => setKind("c");
  drawTower();
  if (!cur.remaining.length) seasonInReview(cur, record).then((html) => { $("#ch-review").innerHTML = html; }).catch((e) => console.error(e));

  // how the odds moved: this season so far, and past seasons replayed round by round
  const seasons = { [`${cur.season}`]: { label: `${cur.season}${cur.remaining.length ? " so far" : ""}`, cutoffs: data.replay?.cutoffs || [], live: true } };
  for (const [y, v] of Object.entries({ ...data.backtest?.seasons, ...data.past_replays })) if (!seasons[y]) seasons[y] = { label: `${y}`, cutoffs: v.cutoffs, total: v.total_rounds };
  const keys = Object.keys(seasons).sort((a, b) => b - a);
  $("#ch-season").innerHTML = keys.map((k) => `<option value="${k}">${seasons[k].label}</option>`).join("");
  const drawChart = () => {
    const sx = seasons[$("#ch-season").value];
    const cuts = sx.cutoffs;
    if (cuts.length < 2) { $("#ch-chart").textContent = "Not enough rounds yet to draw this."; $("#ch-note").textContent = ""; return; }
    const last = cuts[cuts.length - 1];
    const peak = {};
    cuts.forEach((c) => c.drivers.forEach((d) => { peak[d.code] = Math.max(peak[d.code] || 0, d.title); }));
    const team = {};
    cuts.forEach((c) => c.drivers.forEach((d) => { team[d.code] = d.team; }));
    const finalT = Object.fromEntries(last.drivers.map((d) => [d.code, d.title]));
    const codes = Object.keys(peak).filter((c) => peak[c] >= 0.08).sort((a, b) => (finalT[b] || 0) - (finalT[a] || 0) || peak[b] - peak[a]).slice(0, 5);
    const picked = codes.length ? codes : last.drivers.slice(0, 3).map((d) => d.code);
    const seen = {};
    const series = picked.map((code) => {
      const dash = seen[team[code]] ? "7 5" : null;
      seen[team[code]] = true;
      return { name: code, color: colour(team[code]), dash, values: cuts.map((c) => Math.round((c.drivers.find((d) => d.code === code)?.title || 0) * 1000) / 10) };
    });
    lineChart($("#ch-chart"), series, cuts.map((c) => String(c.after)), { unit: "title chance", firstIsData: true, yMax: 100, fmt: (v) => `${Number.isInteger(v) ? v : v.toFixed(1)}%` });
    $("#ch-note").textContent = sx.live
      ? "Title chance at each round, using only results up to then."
      : `A replay using only results up to each round.${last.champion_actual ? ` ${last.champion_actual} won the title.` : ""}`;
  };
  $("#ch-season").onchange = drawChart;
  drawChart();

  const b = data.backtest?.summary;
  const live = data.live;
  const first = data.backtest?.seasons_tested?.[0], lastY = data.backtest?.seasons_tested?.slice(-1)[0];
  el.querySelector("#ch-trust").innerHTML = more(`
    ${b ? `<p>We replayed ${first}–${lastY} at every round, ${b.cutoffs} times in all. Expected final points were off by ${b.mae.toFixed(1)} on average, against ${b.straight_line_mae.toFixed(1)} for simply extending each driver's current points rate.</p>
    <p>For the title itself, the chance given to the eventual champion scored ${b.title_logloss.toFixed(2)} (log loss, lower is better), against ${b.rival_title_logloss.toFixed(2)} for a plain projection whose noise level was picked in hindsight. That is a small edge, and five seasons means only five champions, so the title odds are the least certain number on this page.</p>
    <p class="fine">One number, how far a team's pace may drift during a season, was chosen so the 80% ranges above held the real final total ${whole(b.coverage80)} of the time on those same seasons. That check is a fit, not an independent test, and the comparisons above were made on the same seasons too, so treat them as slightly flattering.</p>` : ""}
    <p class="fine">The simulation knows each team's recent form and the races and sprints left. It does not know about upgrades, penalties or injuries; it allows for pace drifting during the season, sized from past seasons. Details are in <code>reports/championship.md</code>.</p>
    <div class="livebox"><p><b>Live log: ${live.records} championship forecast${live.records === 1 ? "" : "s"} frozen.</b> ${live.chain_ok ? "The chain is intact." : "The chain is broken."}</p>
      ${live.log.length ? `<p>${live.log.slice(-3).map((r) => `After round ${r.after_round}: ${esc(r.leader)} ${titlePct(r.leader_title)}, frozen ${fmtStamp(r.made_at)}`).join(". ")}.</p>` : "<p>Each forecast is logged after a race, before the next one starts.</p>"}</div>`, "How far to trust it");
}
