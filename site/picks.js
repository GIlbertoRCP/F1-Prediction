// Beat the Oracle: your pick for each race, stored only in this browser.
// Scoring is fair-odds: a correct pick earns 1 / (the Oracle's chance for that driver), so a
// favourite is worth little and a longshot a lot. Anyone who picks in line with the Oracle's odds
// averages exactly 1 point per race, and beating that takes real insight.
const KEY = "winner-oracle:picks:v1";
const MIN_P = 0.01;   // caps a single pick at 100 points

export function loadPicks(storage = globalThis.localStorage) {
  try { return JSON.parse(storage.getItem(KEY)) || {}; } catch { return {}; }
}

export function savePick(raceKey, driverId, storage = globalThis.localStorage, now = new Date()) {
  const picks = loadPicks(storage);
  picks[raceKey] = { driver_id: driverId, at: now.toISOString() };
  try { storage.setItem(KEY, JSON.stringify(picks)); } catch { /* private mode: keep going in memory */ }
  return picks;
}

export function points(pCorrectPick) {
  return Math.round(1 / Math.max(pCorrectPick, MIN_P));
}

/**
 * picks:   {raceKey: {driver_id}}
 * settled: {raceKey: row from track_record.races}   (only finished races)
 * pages:   {raceKey: race page with predictions}
 * Returns rows for finished races you picked, plus totals for you and for the Oracle's top pick
 * on the same races.
 */
export function tally(picks, settled, pages) {
  const rows = [];
  for (const [key, pick] of Object.entries(picks)) {
    const s = settled[key], page = pages[key];
    if (!s || !page) continue;
    const mine = page.predictions.find((p) => p.driver_id === pick.driver_id);
    if (!mine) continue;
    const hit = pick.driver_id === s.winner_id;
    rows.push({
      key, race: s.race, date: s.date, pick: mine.driver, pick_p: mine.p, winner: s.winner,
      hit, points: hit ? points(mine.p) : 0,
      oracle_pick: s.pick, oracle_hit: s.hit, oracle_points: s.hit ? points(s.pick_p) : 0,
    });
  }
  rows.sort((a, b) => b.date.localeCompare(a.date));
  const sum = (f) => rows.reduce((t, r) => t + f(r), 0);
  return {
    rows,
    you: { n: rows.length, wins: sum((r) => (r.hit ? 1 : 0)), points: sum((r) => r.points) },
    oracle: { wins: sum((r) => (r.oracle_hit ? 1 : 0)), points: sum((r) => r.oracle_points) },
  };
}
