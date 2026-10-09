// Head-to-head from real results. Everything is counted from the race and qualifying results of one
// season; nothing is estimated.

/** Compare two drivers over the rounds where both took part. */
export function compare(season, a, b) {
  const A = season.drivers[a], B = season.drivers[b];
  const r = {
    together: 0, sameTeam: 0,
    quali: { a: 0, b: 0, n: 0 }, race: { a: 0, b: 0, n: 0 },
    points: { a: 0, b: 0 }, dnf: { a: 0, b: 0 },
    avgQuali: { a: 0, b: 0 }, avgFinish: { a: 0, b: 0 },
  };
  let qn = 0, fn = 0;
  season.rounds.forEach((_, i) => {
    if (A.team[i] == null || B.team[i] == null) return;
    r.together++;
    if (A.team[i] === B.team[i]) r.sameTeam++;
    r.points.a += A.pts[i]; r.points.b += B.pts[i];
    if (A.f[i] === 0) r.dnf.a++;
    if (B.f[i] === 0) r.dnf.b++;
    if (A.q[i] != null && B.q[i] != null) {
      qn++; r.avgQuali.a += A.q[i]; r.avgQuali.b += B.q[i];
      if (A.q[i] < B.q[i]) r.quali.a++; else if (B.q[i] < A.q[i]) r.quali.b++;
      r.quali.n++;
    }
    const fa = A.f[i], fb = B.f[i];
    if (fa === 0 && fb === 0) return;               // both retired: no result either way
    r.race.n++;
    if (fa > 0 && fb > 0) { fn++; r.avgFinish.a += fa; r.avgFinish.b += fb; }
    if (fa > 0 && (fb === 0 || fa < fb)) r.race.a++; else r.race.b++;
  });
  if (qn) { r.avgQuali.a /= qn; r.avgQuali.b /= qn; } else r.avgQuali = null;
  if (fn) { r.avgFinish.a /= fn; r.avgFinish.b /= fn; } else r.avgFinish = null;
  return r;
}

/** Every pair of drivers who shared a team in at least `min` rounds, grouped by team. */
export function teammatePairs(season, min = 3) {
  const ids = Object.keys(season.drivers), pairs = [];
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const c = compare(season, ids[i], ids[j]);
      if (c.sameTeam >= min) {
        const team = season.rounds.map((_, k) => season.drivers[ids[i]].team[k])
          .find((t, k) => t && t === season.drivers[ids[j]].team[k]);
        pairs.push({ team, a: ids[i], b: ids[j], ...c });
      }
    }
  }
  return pairs.sort((x, y) => x.team.localeCompare(y.team) || y.sameTeam - x.sameTeam);
}
