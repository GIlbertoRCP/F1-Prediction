// Championship tables from real results: race points plus sprint points, round by round.

const total = (d, i) => (d.pts[i] || 0) + (d.spts?.[i] || 0);

/** Drivers ranked by points, then by best finishes (the official countback). */
export function driverStandings(season, upTo = season.rounds.length) {
  const rows = Object.entries(season.drivers).map(([id, d]) => {
    const counts = new Array(25).fill(0);
    let points = 0, team = null;
    const cumulative = [0];
    for (let i = 0; i < upTo; i++) {
      points += total(d, i);
      cumulative.push(points);
      if (d.team[i]) team = d.team[i];
      if (d.f[i] > 0) counts[Math.min(d.f[i], 24)]++;
    }
    return { id, code: d.code, team, points, wins: counts[1], podiums: counts[1] + counts[2] + counts[3], counts, cumulative };
  }).filter((r) => r.team);
  return rows.sort((a, b) => b.points - a.points || cmpCounts(b.counts, a.counts) || a.id.localeCompare(b.id));
}

function cmpCounts(a, b) {
  for (let i = 1; i < a.length; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return 0;
}

/** Constructors: every car's points, credited to the team it drove for that round. */
export function teamStandings(season, upTo = season.rounds.length) {
  const teams = {};
  Object.values(season.drivers).forEach((d) => {
    for (let i = 0; i < upTo; i++) {
      const t = d.team[i];
      if (!t) continue;
      (teams[t] ||= { id: t, per: new Array(upTo).fill(0), wins: 0 });
      teams[t].per[i] += total(d, i);
      if (d.f[i] === 1) teams[t].wins++;
    }
  });
  return Object.values(teams).map((t) => {
    let c = 0;
    const cumulative = [0].concat(t.per.map((v) => (c += v)));
    return { id: t.id, team: t.id, code: t.id, points: c, wins: t.wins, cumulative };
  }).sort((a, b) => b.points - a.points || b.wins - a.wins || a.id.localeCompare(b.id));
}
