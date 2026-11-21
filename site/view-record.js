// Track record: live and replayed scores, by season, and the calibration chart.

import { $, more, pct, whole } from "./ui.js";

/* ---------- track record ---------- */
export function calibrationSVG(rows) {
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

export function renderRecord(tr) {
  const el = $("#record-body");
  const b = tr.backtest, l = tr.live;
  if (!b.n) { el.innerHTML = `<p>No scored forecasts yet.</p>`; return; }
  const random = 1 / Math.exp(b.uniform_logloss);
  const live = l.n
    ? `<div class="livebox"><p><b>Live record: ${l.n} race${l.n > 1 ? "s" : ""}.</b> The favourite won ${Math.round(l.top1.mean * l.n)} of ${l.n}; we gave the winner ${whole(l.avg_winner_prob)} on average.</p>
       </div>`
    : `<div class="livebox"><p><b>Live record: no races scored yet.</b></p>
       <p>Everything below is from replays; live races will show here.</p></div>`;
  const seasons = Object.entries(tr.by_season).map(([s, v]) => `
    <tr><td>${s}</td><td>${v.n}</td><td>${whole(v.top1.mean)}</td><td>${whole(v.top3.mean)}</td>
    <td>${whole(v.avg_winner_prob)}</td><td>${v.logloss.mean.toFixed(2)}</td></tr>`).join("");
  el.innerHTML = `
    ${live}
    <div class="tiles">
      <div class="tile"><span class="v">${whole(b.top1.mean)}</span><span class="l">top pick won, over ${b.n} replayed races (the pole sitter won ${whole(b.pole_top1)})</span></div>
      <div class="tile"><span class="v">${whole(b.top3.mean)}</span><span class="l">of the time the winner was in our top three</span></div>
      <div class="tile ${tr.reference && b.logloss.mean < tr.reference.slot_prior_logloss ? "good" : ""}"><span class="v">${b.logloss.mean.toFixed(2)}</span><span class="l">log loss, lower is better${tr.reference ? ` (grid slot alone: ${tr.reference.slot_prior_logloss.toFixed(2)})` : ""}</span></div>
      <div class="tile ${l.n ? "good" : "warn"}"><span class="v">${l.n}</span><span class="l">live races scored</span></div>
    </div>
    ${more(`<p class="fine">Picking the pole sitter wins ${whole(b.pole_top1)}, so for a single best guess the model is no better than pole. What it adds is the odds for everyone else: on average we gave the eventual winner ${whole(b.avg_winner_prob)}, where a random guess gives about ${whole(random)}.</p>
    <p class="fine">Log loss is lower when the winner was given a higher chance. A random guess scores ${b.uniform_logloss.toFixed(2)}${tr.reference ? `; always going by the starting slot scores ${tr.reference.slot_prior_logloss.toFixed(2)}; this model scores ${b.logloss.mean.toFixed(2)}` : ""}. Single seasons have few races, so treat their numbers as rough.</p>`)}
    <div class="two">
      <div>
        <h3>By season</h3>
        <div class="tablewrap"><table>
          <thead><tr><th>Season</th><th>Races</th><th>Top pick won</th><th>Winner in top 3</th><th>Chance given to winner</th><th>Log loss</th></tr></thead>
          <tbody>${seasons}</tbody>
        </table></div>
      </div>
      <figure>
        ${calibrationSVG(tr.calibration)}
        <figcaption>When we say 30%, it should happen 30% of the time. On the dashed line means honest odds.</figcaption>
      </figure>
    </div>`;
}
