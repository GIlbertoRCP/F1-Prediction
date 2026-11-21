// The top of the page: the frozen forecast with its lights, or the next race with its countdown and early odds,
// then the last race and how it went.

import { circuitFigure } from "./circuits.js";
import { colour, venue } from "./names.js";
import { forecastCard, shareCard } from "./share.js";
import { $, esc, fmtDate, fmtInstant, fmtStamp, getJSON, ordinal, pct, reduceMotion, store, toInstant, tower, whole } from "./ui.js";
import { pickPanel } from "./view-picks.js";

/* ---------- hero ---------- */
export const mapFor = (circuit, caption) => circuitFigure(store.circuits, circuit, caption);
export const SHARE_BTN = `<button type="button" class="share-btn"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 13V3m0 0L6 7m4-4 4 4M4 11v5h12v-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>Share image</button>`;

// Hooks the hero's share button to a picture of the odds on show.
export function bindShare(el, forecast) {
  const btn = $(".share-btn", el);
  const card = btn && forecastCard(forecast, store.circuits, location.host || "Automata F1");
  if (!card) return;
  btn.onclick = async () => {
    btn.disabled = true;
    try {
      const how = await shareCard(card, card.filename);
      if (how === "downloaded") { btn.lastChild.textContent = "Saved"; setTimeout(() => (btn.lastChild.textContent = "Share image"), 1800); }
    } finally { btn.disabled = false; }
  };
}

// Five red lights, then lights out: the bars on the tower grow as the lights go out.
export function startLights(el, onGo) {
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
export function whyLine(rows) {
  const [a, b] = rows;
  const form = (r) => {
    const rec = (r.recent || []).filter((f) => f != null);
    if (!r.recent?.length) return "";
    const wins = rec.filter((f) => f === 1).length, pods = rec.filter((f) => f <= 3).length;
    const outs = r.recent.length - rec.length;
    const parts = [];
    if (wins) parts.push(`${wins} win${wins > 1 ? "s" : ""}`);
    if (pods > wins) parts.push(`${pods} podium${pods > 1 ? "s" : ""}`);
    if (outs) parts.push(`${outs} retirement${outs > 1 ? "s" : ""}`);
    return parts.length ? ` (${parts.join(", ")} in the last ${r.recent.length})` : "";
  };
  return `<b>${esc(a.driver)}</b> leads at <b>${pct(a.p)}</b>${form(a)}.
    ${b ? `<b>${esc(b.driver)}</b> next at ${pct(b.p)}${form(b)}.` : ""}`;
}

export function provisionalPanel(pv) {
  const at = pv.stages.findIndex((s) => s.key === pv.stage);
  const box = document.createElement("section");
  box.className = "provisional";
  box.innerHTML = `
    <div class="prov-head">
      <h2>Early odds <span class="tag soft">Provisional</span></h2>
      <ol class="steps" aria-label="How these odds sharpen over the weekend">
        ${pv.stages.map((s, i) => `<li class="${i < at ? "done" : i === at ? "now" : ""}">${esc(s.label)}</li>`).join("")}
      </ol>
    </div>
    <p class="why">${whyLine(pv.predictions)}</p>
    <p class="prov-note">${esc(pv.note)} Not scored; the real forecast replaces them after qualifying.</p>
    ${pv.stage === "form" ? `<p class="form-key" aria-hidden="true"><span>Last five finishes, oldest first</span><b><i class="w">1</i> win</b><b><i class="pd">3</i> podium</b><b><i class="out">R</i> retired</b></p>` : ""}`;
  box.append(tower(pv.predictions, { animate: true, form: pv.stage === "form" }));
  return box;
}

// Ticks down to the next session; switches to a plain message once it has started.
export function countdown(el, target, label) {
  if (!el || !target || isNaN(target)) return;
  const tick = () => {
    const ms = target - Date.now();
    if (ms <= 0) {
      el.innerHTML = `<span class="cd-label">${label === "qualifying"
        ? "Qualifying is under way. The forecast locks once the grid is official."
        : "The race is under way. It is scored once the results are in."}</span>`;
      return;
    }
    const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60, sec = Math.floor(ms / 1e3) % 60;
    const unit = (u) => `<span class="cd-u"><b class="num"></b><small>${u}</small></span>`;
    if (!el.querySelector(".cd-u")) el.innerHTML = `${unit("days")}${unit("hrs")}${unit("min")}${unit("sec")}<span class="cd-label">until ${esc(label)}</span>`;
    // only the digits that changed are rewritten, and each one drops in
    el.querySelectorAll(".cd-u b").forEach((b, i) => {
      const v = String([d, h, m, sec][i]).padStart(2, "0");
      if (b.textContent === v) return;
      const first = !b.textContent;
      b.textContent = v;
      if (!first && !reduceMotion()) { b.classList.remove("flip"); void b.offsetWidth; b.classList.add("flip"); }
    });
    setTimeout(tick, 1000 - (Date.now() % 1000));
  };
  tick();
}

export async function renderHero(forecast, record) {
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
          ${SHARE_BTN}
        </div>
        ${map}
      </div>`;
    const t = tower(forecast.predictions, { animate: true, hold: true, fromGrid: true });
    el.append(t);
    el.append(pickPanel(forecast, record));
    startLights(el, () => t.release());
    bindShare(el, forecast);
    return;
  }
  const next = forecast.next_race;
  const nextMap = next ? mapFor(next.circuit, "") : "";
  const quali = next && toInstant(next.quali_date, next.quali_time);
  const raceAt = next && toInstant(next.date, next.time);
  const session = (name, at, date) => `<li><span>${name}</span><b>${esc(at && !isNaN(at) ? fmtInstant(at) : fmtDate(date))}</b></li>`;
  el.innerHTML = next
    ? `<div class="hero-top ${nextMap ? "" : "nomap"}"><div>
         <p class="eyebrow">${esc(venue(next))}${next.sprint ? ' · <span class="s">Sprint weekend</span>' : ""}</p>
         <h1>${esc(next.race)}</h1>
         <div class="countdown" id="cd" role="timer" aria-live="off"></div>
         <ul class="weekend">
           ${next.quali_date ? session("Qualifying", quali, next.quali_date) : ""}
           ${session("Race", raceAt, next.date)}
         </ul>
         <p class="sub">The forecast locks after qualifying and is scored after the race. Times are in your time zone.</p>
         ${forecast.provisional ? SHARE_BTN : ""}
       </div>${nextMap}</div>`
    : `<h1 class="calm">No race to forecast right now</h1>
       <p class="sub">Forecasts open after qualifying. Here is the last race and how it went.${record.latest ? ` <a href="#championship">The ${record.latest.season} season in review</a>.` : ""}</p>`;
  if (next) countdown($("#cd", el), quali && quali > Date.now() ? quali : raceAt, quali && quali > Date.now() ? "qualifying" : "the race");
  if (forecast.provisional) {
    el.append(provisionalPanel(forecast.provisional));
    bindShare(el, forecast);
  }
  const last = record.latest;
  if (!last) return;
  const page = await getJSON(`data/races/${last.season}-${last.round}.json`);
  const hit = last.hit;
  const winnerRow = page.predictions.find((p) => p.driver_id === last.winner_id);
  el.insertAdjacentHTML("beforeend", `<h2 class="lastrace-title">${page.kind === "live" ? '<span class="tag">Scored</span>' : ""}${esc(last.race)}</h2>
    <p class="lastrace-sub">${page.kind === "live"
      ? `Last race. Frozen before the start, fingerprint <code>${esc((page.hash || "").slice(0, 12))}</code>.`
      : "Last race. A replay made only from earlier races."}</p>`);
  el.append(tower(page.predictions, { winnerId: last.winner_id, animate: true }));
  el.insertAdjacentHTML("beforeend", `
    <div class="callout ${hit ? "" : "miss"}">
      <h3>${hit ? "The favourite won" : "An upset"}</h3>
      <p>${hit
        ? `We gave ${esc(last.winner)} ${whole(last.p_winner)} and ${esc(last.winner)} won.`
        : `We rated ${esc(last.pick)} at ${whole(last.pick_p)}. ${esc(last.winner)} won from ${ordinal(winnerRow.grid)} on the grid, a ${pct(last.p_winner)} chance in our forecast.`}
        </p>
      ${podiumLine(page)}
    </div>`);
}

export function podiumLine(page) {
  const podium = (page.result?.finishers || []).slice(0, 3);
  if (podium.length < 3) return "";
  const top3 = new Set(page.predictions.slice(0, 3).map((p) => p.driver));
  const hits = podium.filter((f) => top3.has(f.driver)).length;
  return `<p class="podium">${podium.map((f) => `<span style="--team:${colour(f.team)}"><b>P${f.pos}</b> ${esc(f.driver)} <small>from P${f.grid}</small></span>`).join("")}</p>
    <p>${hits === 3 ? "All three podium finishers were in our top three." : `${hits} of the 3 podium finishers ${hits === 1 ? "was" : "were"} in our top three.`}</p>`;
}
