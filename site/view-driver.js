// Driver cards: any driver code on the page opens one. Everything comes from files the page has already loaded:
// this season's results (h2h.json), the title outlook and the race odds on show.

import { compare } from "./h2h.js";
import { colour, teamName } from "./names.js";
import { clinched, driverStandings } from "./standings.js";
import { driverName, esc, formStrip, getShared, ordinal, pct, titlePct } from "./ui.js";

let dialog = null;

function make() {
  dialog = document.createElement("dialog");
  dialog.className = "drvcard";
  dialog.setAttribute("aria-labelledby", "drvcard-name");
  // a click on the backdrop (the dialog itself, outside its content) closes it
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  document.body.append(dialog);
}

async function card(id) {
  const [h2h, champ, forecast] = await Promise.all(["data/h2h.json", "data/championship.json", "data/forecast.json"]
    .map((p) => getShared(p).catch(() => null)));
  const year = Object.keys(h2h || {}).sort().pop();
  const season = h2h?.[year];
  const me = season?.drivers[id];
  if (!me) return null;
  const n = season.rounds.length;
  const last = (arr) => { for (let i = n - 1; i >= 0; i--) if (arr[i] != null) return i; return -1; };
  const team = me.team[last(me.team)];
  const table = driverStandings(season, n);
  const pos = table.findIndex((r) => r.id === id);
  const row = table[pos];

  // last five rounds they started, oldest first, in the timing tower's form strip (0 is a retirement)
  const recent = me.f.map((f, i) => (me.team[i] ? (f === 0 ? null : f) : undefined)).filter((f) => f !== undefined).slice(-5);

  // the teammate they shared the most rounds with this season
  const mates = Object.keys(season.drivers).filter((d) => d !== id)
    .map((d) => ({ d, n: season.drivers[d].team.filter((t, i) => t && t === me.team[i]).length })).filter((m) => m.n)
    .sort((a, b) => b.n - a.n);
  const mate = mates[0] && { id: mates[0].d, code: season.drivers[mates[0].d].code, c: compare(season, id, mates[0].d) };

  const outlook = champ?.current?.season === Number(year) ? champ.current.drivers.find((d) => d.id === id) : null;
  const winner = outlook && clinched(champ.current.drivers, champ.current.remaining, "d");   // settled on points
  const titleLine = !outlook ? "" : winner ? (winner.id === id ? "Champion" : `Won by ${esc(winner.code)}`) : titlePct(outlook.title);
  const odds = forecast?.status === "open" ? { race: forecast.race, rows: forecast.predictions, early: false }
    : forecast?.provisional ? { race: forecast.next_race, rows: forecast.provisional.predictions, early: true } : null;
  const chance = odds?.rows.find((p) => p.driver_id === id);

  const stat = (v, l) => `<div><b class="num">${v}</b><span>${l}</span></div>`;
  return `
    <div class="drvcard-head" style="--team:${colour(team)}">
      <span class="tick" style="background:${colour(team)}"></span>
      <div><h2 id="drvcard-name">${esc(me.code)}</h2><p>${esc(driverName(id))} · ${esc(teamName(team))}</p></div>
      <button type="button" class="drvcard-x" aria-label="Close">×</button>
    </div>
    <div class="drvcard-stats">
      ${stat(row ? ordinal(pos + 1) : "–", `in ${year}`)}${stat(row ? row.points : 0, "points")}${stat(row?.wins ?? 0, "wins")}${stat(row?.podiums ?? 0, "podiums")}
    </div>
    ${recent.length ? `<p class="drvcard-row"><span>Last ${recent.length} finishes</span>${formStrip(recent)}</p>` : ""}
    ${mate && mate.c.together ? `<p class="drvcard-row"><span>Against ${esc(mate.code)}, their teammate</span>
      <b>Qualifying ${mate.c.quali.a}–${mate.c.quali.b}</b><b>Races ${mate.c.race.a}–${mate.c.race.b}</b></p>` : ""}
    ${outlook ? `<p class="drvcard-row"><span>${year} title</span><b>${titleLine}</b></p>` : ""}
    ${chance ? `<p class="drvcard-row"><span>${esc(odds.race.race.replace(/ Grand Prix$/, " GP"))}${odds.early ? ", early odds" : ""}</span><b>${pct(chance.p)} to win</b></p>` : ""}
    <a class="drvcard-link" href="#h2h">Compare with anyone in Head to head</a>`;
}

/** Opens a driver's card when any [data-driver] button is clicked. */
export function driverCards() {
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-driver]");
    if (!btn) return;
    const html = await card(btn.dataset.driver);
    if (!html) return;
    if (!dialog) make();
    dialog.innerHTML = html;
    dialog.querySelector(".drvcard-x").onclick = () => dialog.close();
    dialog.querySelector(".drvcard-link").onclick = () => dialog.close();
    dialog.showModal();
  });
}
