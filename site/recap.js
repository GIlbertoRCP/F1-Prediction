// A finished season in a few facts: who won and when it was settled, and how the race forecasts did.
// Pure functions over h2h.json's season data and track_record.json's races, so they can be tested in Node.

import { driverStandings, teamStandings, clinched } from "./standings.js";

/** The champion, the runner-up's gap, and the round after which nobody could catch them. */
export function titleStory(season, kind = "d") {
  const table = kind === "d" ? driverStandings : teamStandings;
  const n = season.rounds.length;
  const [champ, second] = table(season, n);
  if (!champ) return null;
  let settledAfter = n;
  for (let k = 1; k <= n; k++) {
    const who = clinched(table(season, k), season.rounds.slice(k), kind);
    if (who && who.id === champ.id) { settledAfter = k; break; }
  }
  return { champ, margin: second ? champ.points - second.points : null, settledAfter, left: n - settledAfter };
}

/** How the race forecasts did over one season: hits, the biggest upset and the most confident correct call. */
export function forecastStory(races, season) {
  const rs = races.filter((r) => r.season === season);
  if (!rs.length) return null;
  const hits = rs.filter((r) => r.hit);
  const by = (f) => (a, b) => f(a) - f(b);
  return {
    n: rs.length, hits: hits.length, live: rs.filter((r) => r.kind === "live").length,
    winners: new Set(rs.map((r) => r.winner_id)).size,
    upset: rs.slice().sort(by((r) => r.p_winner))[0],
    bestCall: hits.slice().sort(by((r) => -r.p_winner))[0] || null,
  };
}
