import { loadPicks, savePick, tally } from "./picks.js";
import { utilities, simulate, summarize } from "./sim.js";
import { compare, teammatePairs } from "./h2h.js";
import { driverStandings, teamStandings } from "./standings.js";
import { lineChart } from "./linechart.js";
import { circuitFigure } from "./circuits.js";

const TEAM_COLOURS = {
  red_bull: "#4a6bff", mercedes: "#27d1c0", ferrari: "#ef1a2d", mclaren: "#ff8000",
  aston_martin: "#2aa58f", alpine: "#ff87bc", williams: "#3ab4ee", rb: "#7da0ff",
  alphatauri: "#7aa6c6", toro_rosso: "#7aa6c6", haas: "#b58ae6", sauber: "#52e252",
  alfa: "#d8465c", audi: "#e0334f", cadillac: "#9aa5b8", renault: "#ffd800",
  racing_point: "#f596c8", force_india: "#f596c8",
};
const colour = (team) => TEAM_COLOURS[team] || "#8a8f98";
const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let CIRCUITS = null;

const pageCache = {};
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p < 0.005 ? "<1%" : p < 0.1 ? `${(p * 100).toFixed(1)}%` : `${Math.round(p * 100)}%`);
const whole = (p) => `${Math.round(p * 100)}%`;
const getJSON = (path) => fetch(path).then((r) => { if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); });
const fmtDate = (iso, opts = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });
const fmtStamp = (iso) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
const ordinal = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };

/* ---------- the timing tower ---------- */
function tower(predictions, { winnerId = null, limit = 10, animate = false, hold = false } = {}) {
  const ol = document.createElement("ol");
  ol.className = "tower" + (animate ? " animate" : "");
  const max = Math.max(...predictions.map((p) => p.p));
  const draw = (rows) => {
    ol.innerHTML = rows.map((p, i) => `
      <li class="${i === 0 ? "lead" : ""} ${p.driver_id === winnerId ? "winner" : ""}" style="--team:${colour(p.team)}">
        <span class="rk">${i + 1}</span>
        <span class="tick" style="background:${colour(p.team)}"></span>
        <span class="code" title="${esc(p.driver_id.replace(/_/g, " "))}">${esc(p.driver)}</span>
        <span class="grid">${p.grid ? "P" + p.grid : ""}</span>
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

/* ---------- hero ---------- */
const mapFor = (circuit, caption) => circuitFigure(CIRCUITS, circuit, caption);

// Five red lights, then lights out: the bars on the tower grow as the lights go out.
function startLights(el, onGo) {
  const lights = el.querySelector(".lights");
  const done = () => { lights.classList.add("done"); lights.querySelectorAll(".light").forEach((l) => l.classList.remove("on")); onGo(); };
  if (!lights || reduceMotion()) { lights?.classList.add("done"); onGo(); return; }
  const bulbs = [...lights.querySelectorAll(".light")];
  let i = 0, timer = null, finished = false;
  const finish = () => { if (finished) return; finished = true; clearTimeout(timer); window.removeEventListener("pointerdown", finish); window.removeEventListener("keydown", finish); done(); };
  const step = () => {
    if (i < bulbs.length) { bulbs[i++].classList.add("on"); timer = setTimeout(step, 260); }
    else timer = setTimeout(finish, 650);
  };
  window.addEventListener("pointerdown", finish, { once: true });
  window.addEventListener("keydown", finish, { once: true });
  timer = setTimeout(step, 250);
}

// Early odds for the weekend, before qualifying exists. Not frozen, not scored, and labelled as such.
function provisionalPanel(pv) {
  const at = pv.stages.findIndex((s) => s.key === pv.stage);
  const box = document.createElement("section");
  box.className = "provisional";
  box.innerHTML = `
    <div class="prov-head">
      <h2>Early odds <span class="tag soft">Provisional</span></h2>
      <ol class="steps" aria-label="How these odds sharpen">
        ${pv.stages.map((s, i) => `<li class="${i < at ? "done" : i === at ? "now" : ""}">${esc(s.label)}</li>`).join("")}
      </ol>
    </div>
    <p class="prov-note">${esc(pv.note)} They are not frozen or scored, and the real forecast replaces them after qualifying.</p>`;
  box.append(tower(pv.predictions, { animate: true }));
  return box;
}

async function renderHero(forecast, record) {
  const el = $("#forecast");
  if (forecast.status === "open") {
    const r = forecast.race;
    const map = mapFor(r.circuit, "Start/finish in red");
    el.innerHTML = `
      <div class="hero-top ${map ? "" : "nomap"}">
        <div>
          <div class="lights" aria-hidden="true">${'<span class="light"></span>'.repeat(5)}</div>
          <h1>${esc(r.race)}</h1>
          <p class="sub"><span class="tag">Live</span><strong>${esc(forecast.predictions[0].driver)}</strong> is the favourite at ${whole(forecast.predictions[0].p)}.
          Race day is ${fmtDate(r.date)}.</p>
          <span class="stamp">Frozen ${fmtStamp(forecast.made_at)} from the qualifying grid. Fingerprint <code>${forecast.hash.slice(0, 12)}</code></span>
        </div>
        ${map}
      </div>`;
    const t = tower(forecast.predictions, { animate: true, hold: true });
    el.append(t);
    el.append(pickPanel(forecast, record));
    startLights(el, () => t.release());
    return;
  }
  const next = forecast.next_race;
  const nextMap = next ? mapFor(next.circuit, "") : "";
  el.innerHTML = next
    ? `<div class="hero-top ${nextMap ? "" : "nomap"}"><div>
         <h1>Next forecast opens after qualifying</h1>
         <p class="sub">The <strong>${esc(next.race)}</strong> is on ${fmtDate(next.date)}${next.quali_date ? `; qualifying is ${fmtDate(next.quali_date)}` : ""}. The forecast needs the starting grid, so it appears as soon as qualifying finishes.</p>
       </div>${nextMap}</div>`
    : `<h1 class="calm">No race to forecast right now</h1>
       <p class="sub">Forecasts open after qualifying for each Grand Prix. Below is the most recent race, so you can see what a forecast looks like and how it did.</p>`;
  if (forecast.provisional) el.append(provisionalPanel(forecast.provisional));
  const last = record.latest;
  if (!last) return;
  const page = await getJSON(`data/races/${last.season}-${last.round}.json`);
  const hit = last.hit;
  const winnerRow = page.predictions.find((p) => p.driver_id === last.winner_id);
  el.insertAdjacentHTML("beforeend", `<h2 class="lastrace-title">${esc(last.race)}</h2>`);
  el.append(tower(page.predictions, { winnerId: last.winner_id, animate: true }));
  el.insertAdjacentHTML("beforeend", `
    <div class="callout ${hit ? "" : "miss"}">
      <h3>${hit ? "The favourite won" : "An upset"}</h3>
      <p>${hit
        ? `We gave ${esc(last.winner)} ${whole(last.p_winner)} and ${esc(last.winner)} won.`
        : `We rated ${esc(last.pick)} at ${whole(last.pick_p)}. ${esc(last.winner)} won from ${ordinal(winnerRow.grid)} on the grid, a ${pct(last.p_winner)} chance in our forecast.`}
        ${page.kind === "backtest" ? " This is a replay made from earlier races only." : ""}</p>
    </div>`);
}

/* ---------- your pick ---------- */
function pickPanel(forecast, record) {
  const key = `${forecast.race.season}-${forecast.race.round}`;
  const box = document.createElement("div");
  box.className = "pickbox";
  const draw = () => {
    const mine = loadPicks()[key]?.driver_id;
    const oracle = forecast.predictions[0];
    box.innerHTML = `
      <h3>Who wins? Make your pick</h3>
      <p class="fine">${mine
        ? `You picked <b>${esc(forecast.predictions.find((p) => p.driver_id === mine)?.driver ?? mine)}</b>. The Oracle's favourite is ${esc(oracle.driver)}. You can change your pick until the race starts. It is saved in this browser only.`
        : `The Oracle's favourite is ${esc(oracle.driver)}. Pick anyone; a correct pick scores 1 divided by the Oracle's chance for that driver, so longshots pay more.`}</p>
      <div class="chips" role="group" aria-label="Pick the winner">
        ${forecast.predictions.map((p) => `<button class="chip" type="button" data-id="${esc(p.driver_id)}" aria-pressed="${p.driver_id === mine}">
          <span class="tick" style="background:${colour(p.team)}"></span><b>${esc(p.driver)}</b><span class="num">${pct(p.p)}</span></button>`).join("")}
      </div>`;
    box.querySelectorAll(".chip").forEach((b) => (b.onclick = () => { savePick(key, b.dataset.id); draw(); renderPicks(record); }));
  };
  draw();
  return box;
}

async function renderPicks(record) {
  const el = $("#picks");
  const picks = loadPicks();
  const settled = Object.fromEntries(record.races.map((r) => [`${r.season}-${r.round}`, r]));
  const keys = Object.keys(picks).filter((k) => settled[k]);
  if (!keys.length) { el.hidden = true; return; }
  const pages = {};
  await Promise.all(keys.map(async (k) => { pages[k] = pageCache[k] ||= await getJSON(`data/races/${k}.json`); }));
  const t = tally(picks, settled, pages);
  el.hidden = false;
  const verdict = t.you.points > t.oracle.points ? "You are ahead of the Oracle." : t.you.points < t.oracle.points ? "The Oracle is ahead." : "You are level with the Oracle.";
  $("#picks-body").innerHTML = `
    <p class="lede">After ${t.you.n} race${t.you.n > 1 ? "s" : ""} you have <b>${t.you.points} points</b> and the Oracle's top pick has <b>${t.oracle.points}</b>. ${verdict}</p>
    <p class="fine">You called ${t.you.wins} winner${t.you.wins === 1 ? "" : "s"}; the Oracle's top pick called ${t.oracle.wins}. Over many races, someone who picks in line with the Oracle's odds averages 1 point per race.</p>
    <div class="tablewrap"><table>
      <thead><tr><th>Race</th><th>Your pick</th><th>Winner</th><th>You</th><th>Oracle top pick</th></tr></thead>
      <tbody>${t.rows.map((r) => `<tr><td>${esc(r.race)}</td><td>${esc(r.pick)} (${whole(r.pick_p)})</td><td>${esc(r.winner)}</td>
        <td>${r.points}</td><td>${esc(r.oracle_pick)}: ${r.oracle_points}</td></tr>`).join("")}</tbody>
    </table></div>`;
}

/* ---------- track record ---------- */
function calibrationSVG(rows) {
  const W = 380, M = 56, S = W - M - 18;
  const x = (v) => M + v * S, y = (v) => W - M - v * S;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const grid = ticks.map((t) => `
    <line x1="${x(t)}" y1="${y(0)}" x2="${x(t)}" y2="${y(1)}" stroke="var(--rule)"/>
    <line x1="${x(0)}" y1="${y(t)}" x2="${x(1)}" y2="${y(t)}" stroke="var(--rule)"/>
    <text x="${x(t)}" y="${y(0) + 16}" text-anchor="middle">${t * 100}%</text>
    <text x="${x(0) - 8}" y="${y(t) + 4}" text-anchor="end">${t * 100}%</text>`).join("");
  const pts = rows.map((r) => `<circle cx="${x(r.predicted)}" cy="${y(r.observed)}" r="${3 + Math.log10(r.n) * 3}" fill="var(--ink)" fill-opacity=".8"><title>We said ${pct(r.predicted)}; it happened ${pct(r.observed)} of the time (${r.n} driver-races)</title></circle>`).join("");
  return `<svg class="cal" viewBox="0 0 ${W} ${W}" role="img" aria-label="Calibration chart: predicted chance against how often it happened">
    ${grid}
    <line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--red)" stroke-width="1.5" stroke-dasharray="5 4"/>
    ${pts}
    <text x="${x(0.5)}" y="${W - 6}" text-anchor="middle">What we said</text>
    <text transform="translate(13 ${y(0.5)}) rotate(-90)" text-anchor="middle">How often it happened</text>
  </svg>`;
}

function renderRecord(tr) {
  const el = $("#record-body");
  const b = tr.backtest, l = tr.live;
  if (!b.n) { el.innerHTML = `<p>No scored forecasts yet.</p>`; return; }
  const random = 1 / Math.exp(b.uniform_logloss);
  const live = l.n
    ? `<div class="livebox"><p><b>Live record: ${l.n} race${l.n > 1 ? "s" : ""}.</b> The favourite won ${Math.round(l.top1.mean * l.n)} of ${l.n}; we gave the winner ${whole(l.avg_winner_prob)} on average.</p>
       <p>Only forecasts frozen before the race count here.</p></div>`
    : `<div class="livebox"><p><b>Live record: no races scored yet.</b></p>
       <p>Every number below comes from replays. Live forecasts are frozen after qualifying and scored once the race finishes; they will appear here, separately.</p></div>`;
  const seasons = Object.entries(tr.by_season).map(([s, v]) => `
    <tr><td>${s}</td><td>${v.n}</td><td>${whole(v.top1.mean)}</td><td>${whole(v.top3.mean)}</td>
    <td>${whole(v.avg_winner_prob)}</td><td>${v.logloss.mean.toFixed(2)}</td></tr>`).join("");
  el.innerHTML = `
    ${live}
    <div class="tiles">
      <div class="tile"><span class="v">${whole(b.top1.mean)}</span><span class="l">top pick won, over ${b.n} replayed races (the pole sitter won ${whole(b.pole_top1)})</span></div>
      <div class="tile"><span class="v">${whole(b.top3.mean)}</span><span class="l">of the time the winner was in our top three</span></div>
      <div class="tile ${tr.reference && b.logloss.mean < tr.reference.slot_prior_logloss ? "good" : ""}"><span class="v">${b.logloss.mean.toFixed(2)}</span><span class="l">log loss (lower is better)${tr.reference ? `; the starting slot alone scores ${tr.reference.slot_prior_logloss.toFixed(2)}, a random guess ${b.uniform_logloss.toFixed(2)}` : ""}</span></div>
      <div class="tile ${l.n ? "good" : "warn"}"><span class="v">${l.n}</span><span class="l">live races scored so far${l.n ? "" : "; the first live forecast is scored after its race"}</span></div>
    </div>
    <p class="fine">Picking the pole sitter wins ${whole(b.pole_top1)}, so for a single best guess the model is no better than pole. What it adds is the odds for everyone else: on average we gave the eventual winner ${whole(b.avg_winner_prob)}, where a random guess gives about ${whole(random)}.</p>
    <div class="two">
      <div>
        <h3>By season</h3>
        <div class="tablewrap"><table>
          <thead><tr><th>Season</th><th>Races</th><th>Top pick won</th><th>Winner in top 3</th><th>Chance given to winner</th><th>Log loss</th></tr></thead>
          <tbody>${seasons}</tbody>
        </table></div>
        <p class="fine">Log loss is lower when the winner was given a higher chance. A random guess scores ${b.uniform_logloss.toFixed(2)}${tr.reference ? `; always going by the starting slot scores ${tr.reference.slot_prior_logloss.toFixed(2)}; this model scores ${b.logloss.mean.toFixed(2)}` : ""}. Single seasons have few races, so treat their numbers as rough.</p>
      </div>
      <figure>
        ${calibrationSVG(tr.calibration)}
        <figcaption>When we say 30%, it should happen about 30% of the time. Each circle groups driver-races where we gave a similar chance; sitting on the dashed line means the odds were honest.</figcaption>
      </figure>
    </div>`;
}

/* ---------- race browser ---------- */
function renderRaces(index, tr) {
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
}

function detail(page) {
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

/* ---------- race simulator ---------- */
async function renderSim(index, forecast) {
  const el = $("#sim-body");
  const open = forecast.status === "open" ? `${forecast.race.season}-${forecast.race.round}` : null;
  const keys = (open && !index.some((r) => r.key === open) ? [{ key: open, race: forecast.race.race, season: forecast.race.season }] : []).concat(index);
  el.innerHTML = `
    <p class="fine">Change the starting grid or knock a driver out, and the model re-runs the race thousands of times. Everything runs in your browser using the same model as the forecast.</p>
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
      <p class="fine">The strip runs from first place on the left to last on the right; darker means likelier. Win and podium odds are checked against history. Positions below third are rougher, so read the strip as a rough shape. See <code>reports/ordered.md</code>.</p>`;
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

/* ---------- head to head ---------- */
function split(a, b, fmt = (v) => v) {
  const total = a + b;
  const wa = total ? (a / total) * 100 : 50;
  return `<span class="split" role="img" aria-label="${fmt(a)} to ${fmt(b)}"><b class="num">${fmt(a)}</b>
    <span class="bar"><i style="width:${wa}%"></i></span><b class="num">${fmt(b)}</b></span>`;
}
const one = (v) => (Math.round(v * 10) / 10).toFixed(1);

async function renderH2H() {
  const el = $("#h2h-body");
  const data = await getJSON("data/h2h.json");
  const years = Object.keys(data).sort((a, b) => b - a);
  el.innerHTML = `
    <p class="fine">Counted from real results: qualifying positions and race finishes in the rounds where both drivers took part. A retirement counts as finishing behind anyone who finished; if both retire, the race does not count for either.</p>
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
        <td class="num">${p.sameTeam}</td>
        <td>${split(p.quali.a, p.quali.b)}</td><td>${split(p.race.a, p.race.b)}</td><td>${split(p.points.a, p.points.b, (v) => Math.round(v))}</td></tr>`).join("")}</tbody></table></div>
      <p class="fine">Qualifying and race columns count rounds won by each driver. Points are race points only, not sprints.</p>`;
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
        <p class="fine">${name(a)} is on the left, ${name(b)} on the right. ${c.sameTeam === c.together
          ? "They were teammates in every one of these rounds."
          : c.sameTeam === 0
            ? "They were never teammates this season, so this mostly compares their cars."
            : `They drove for the same team in ${c.sameTeam} of ${c.together} rounds, so part of this compares cars, not drivers.`}</p>`;
    };
    $("#h2h-a").onchange = show; $("#h2h-b").onchange = show;
    show();
  };
  $("#h2h-year").onchange = draw;
  draw();
}

/* ---------- standings ---------- */
const TEAM_NAMES = { mclaren: "McLaren", rb: "Racing Bulls", alphatauri: "AlphaTauri", toro_rosso: "Toro Rosso", alfa: "Alfa Romeo",
  haas: "Haas", sauber: "Sauber", audi: "Audi", cadillac: "Cadillac", racing_point: "Racing Point", force_india: "Force India" };
const teamName = (t) => TEAM_NAMES[t] || t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const fmtPts = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

async function renderStandings() {
  const el = $("#standings-body");
  const data = await getJSON("data/h2h.json");
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
      <p class="fine">${kind === "d" ? "Equal points are split by best finishes, as in the championship rules." : "Constructors' points count every car, so a team that changed drivers keeps all the points its cars scored."}</p>`;
  };
  $("#st-year").onchange = draw;
  const setKind = (k) => { kind = k; $("#st-d").setAttribute("aria-pressed", String(k === "d")); $("#st-c").setAttribute("aria-pressed", String(k === "c")); draw(); };
  $("#st-d").onclick = () => setKind("d");
  $("#st-c").onclick = () => setKind("c");
  draw();
}

/* ---------- championship ---------- */
function rangeRow(r, i, axisMax, label, cls = "") {
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
    <span class="pct num">${pct(r.title)}</span></li>`;
}

async function renderChampionship() {
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
    <div class="simbar">
      <span class="seg" role="group" aria-label="Championship">
        <button type="button" id="ch-d" aria-pressed="true">Drivers</button>
        <button type="button" id="ch-c" aria-pressed="false">Constructors</button>
      </span>
    </div>
    <div id="ch-tower"></div>
    <p class="legend-note"><span><i style="background:var(--ink);width:3px;height:12px"></i>points now</span>
      <span><i style="background:var(--bar-soft);opacity:.7"></i>80% range for the final total</span>
      <span><i style="background:var(--slate);width:3px;height:12px"></i>middle outcome</span></p>
    <h3>Races left</h3>
    <ul class="remain" id="ch-left"></ul>
    <h3>How the odds moved</h3>
    <div class="simbar"><label class="select">Season <select id="ch-season"></select></label></div>
    <p class="fine" id="ch-note"></p>
    <div id="ch-chart"></div>
    <h3>How far to trust it</h3>
    <div id="ch-trust"></div>`;
  $("#ch-left").innerHTML = cur.remaining.map((r) =>
    `<li><b>R${r.round}</b> ${esc(r.race.replace(/ Grand Prix$/, " GP"))}${r.sprint ? '<span class="s" title="Sprint weekend">Sprint</span>' : ""}</li>`).join("");

  const drawTower = () => {
    const rows = kind === "d" ? cur.drivers.filter((d) => d.racing) : cur.teams;
    const shown = rows.slice(0, 10);
    const axisMax = Math.max(...shown.map((r) => r.p90)) * 1.03;
    const label = (r) => (kind === "d" ? r.code : teamName(r.team));
    const lead = rows[0];
    const second = rows[1];
    $("#ch-lede").innerHTML = `After round ${played} of ${total}, <b>${esc(label(lead))}</b> has a <b>${pct(lead.title)}</b> chance of the ${cur.season} ${kind === "d" ? "drivers'" : "constructors'"} title${second && second.title >= 0.005 ? `; ${esc(label(second))} is next at ${pct(second.title)}` : ""}. ${cur.remaining.length} race${cur.remaining.length === 1 ? "" : "s"} to go.`;
    $("#ch-tower").innerHTML = `<ol class="tower title ${kind === "c" ? "teams" : ""}">${shown.map((r, i) => rangeRow(r, i, axisMax, label(r), r.title < 0.005 && i > 0 ? "dim" : "")).join("")}</ol>`;
  };
  const setKind = (k) => { kind = k; $("#ch-d").setAttribute("aria-pressed", String(k === "d")); $("#ch-c").setAttribute("aria-pressed", String(k === "c")); drawTower(); };
  $("#ch-d").onclick = () => setKind("d");
  $("#ch-c").onclick = () => setKind("c");
  drawTower();

  // how the odds moved: this season so far, and past seasons replayed round by round
  const seasons = { [`${cur.season}`]: { label: `${cur.season} so far`, cutoffs: data.replay?.cutoffs || [], live: true } };
  for (const [y, v] of Object.entries(data.backtest?.seasons || {})) if (!seasons[y]) seasons[y] = { label: `${y}`, cutoffs: v.cutoffs, total: v.total_rounds };
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
      ? "Each point is the title chance using only the results up to that round. This replay is recomputed with every update; the live log below records forecasts as they were made."
      : `A replay: each point uses only the results up to that round, never the rest of ${$("#ch-season").value}. ${last.champion_actual ? `${last.champion_actual} went on to win the title.` : ""}`;
  };
  $("#ch-season").onchange = drawChart;
  drawChart();

  const b = data.backtest?.summary;
  const live = data.live;
  const first = data.backtest?.seasons_tested?.[0], lastY = data.backtest?.seasons_tested?.slice(-1)[0];
  el.querySelector("#ch-trust").innerHTML = `
    ${b ? `<p>We replayed ${first}–${lastY} at every round, ${b.cutoffs} times in all. Expected final points were off by ${b.mae.toFixed(1)} on average, against ${b.straight_line_mae.toFixed(1)} for simply extending each driver's current points rate.</p>
    <p>For the title itself, the chance given to the eventual champion scored ${b.title_logloss.toFixed(2)} (log loss, lower is better), against ${b.rival_title_logloss.toFixed(2)} for a plain projection whose noise level was picked in hindsight. That is a small edge, and five seasons means only five champions, so the title odds are the least certain number on this page.</p>
    <p class="fine">One number, how far a team's pace may drift during a season, was chosen so the 80% ranges above held the real final total ${whole(b.coverage80)} of the time on those same seasons. That check is a fit, not an independent test, and the comparisons above were made on the same seasons too, so treat them as slightly flattering.</p>` : ""}
    <p class="fine">The simulation knows each team's recent form and the races and sprints left. It does not know about upgrades, penalties or injuries; it allows for pace drifting during the season, sized from past seasons. Details are in <code>reports/championship.md</code>.</p>
    <div class="livebox"><p><b>Live log: ${live.records} championship forecast${live.records === 1 ? "" : "s"} frozen.</b> ${live.chain_ok ? "The chain is intact." : "The chain is broken."}</p>
      ${live.log.length ? `<p>${live.log.slice(-3).map((r) => `After round ${r.after_round}: ${esc(r.leader)} ${pct(r.leader_title)}, frozen ${fmtStamp(r.made_at)}`).join(". ")}.</p>` : "<p>Each forecast is logged after a race, before the next one starts.</p>"}</div>`;
}

/* ---------- boot ---------- */
(async function main() {
  try {
    const [meta, forecast, record, index] = await Promise.all([
      getJSON("data/meta.json"), getJSON("data/forecast.json"), getJSON("data/track_record.json"), getJSON("data/races.json"),
    ]);
    CIRCUITS = await getJSON("data/circuits.json").catch(() => null);
    await renderHero(forecast, record);
    renderRecord(record);
    renderRaces(index, record);
    renderPicks(record);
    renderChampionship().catch((e) => console.error(e));
    renderSim(index, forecast);
    renderStandings().catch((e) => { console.error(e); $("#standings-body").textContent = "Standings data is not available."; });
    renderH2H().catch((e) => { console.error(e); $("#h2h-body").textContent = "Head-to-head data is not available."; });
    const through = meta.data_through;
    $("#foot-meta").textContent =
      `Model ${meta.model} (version ${meta.model_version}). Results through ${through ? `${through.race}, ${fmtDate(through.date)}` : "n/a"}. ` +
      `Live log: ${meta.live_log.detail}.`;
  } catch (err) {
    console.error(err);
    $("#forecast").innerHTML = `<h1>Could not load the data</h1><p class="sub">The files in <code>data/</code> are missing. Run <code>python3 -m oracle.publish</code>, then serve this folder.</p>`;
  }
})();
