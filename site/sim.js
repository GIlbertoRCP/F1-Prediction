// In-browser race simulator. It re-runs the same model the forecast uses (weights exported by
// oracle.publish) with whatever you change: starting slots, or drivers who retire.

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Model utilities for each driver. `grid` optionally overrides {driver_id: slot}. */
export function utilities(sim, grid = {}) {
  const { features, mu, sd, w } = sim.model;
  const gi = features.indexOf("log_grid");
  const u = {};
  for (const [id, raw] of Object.entries(sim.features)) {
    const x = raw.slice();
    if (grid[id] != null) x[gi] = Math.log(grid[id]);
    u[id] = x.reduce((t, v, j) => t + w[j] * ((v - mu[j]) / sd[j]), 0);
  }
  return u;
}

/** Exact win probabilities: softmax of the utilities. */
export function winProbs(u) {
  const ids = Object.keys(u), m = Math.max(...ids.map((d) => u[d]));
  const e = ids.map((d) => Math.exp(u[d] - m)), tot = e.reduce((a, b) => a + b, 0);
  return Object.fromEntries(ids.map((d, i) => [d, e[i] / tot]));
}

/**
 * Monte Carlo of the finishing order, one place at a time from the drivers left. scales[j] sharpens
 * or flattens place j+1 (the last scale is reused further down). Drivers in `out` retire and are
 * left out. Returns {driver: counts per place}.
 */
export function simulate(u, scales, nSims, { out = new Set(), seed = 1 } = {}) {
  const rng = mulberry32(seed);
  const all = Object.keys(u), ids = all.filter((d) => !out.has(d));
  const counts = Object.fromEntries(all.map((d) => [d, new Array(all.length).fill(0)]));
  const ex = ids.map((d) => ({ d, u: u[d] }));
  const pre = scales.map((lam) => ex.map((e) => Math.exp(lam * e.u)));   // exp(lam * u) per step
  for (let s = 0; s < nSims; s++) {
    const left = ids.map((_, i) => i);
    for (let pos = 0; pos < ids.length; pos++) {
      const w = pre[Math.min(pos, scales.length - 1)];
      let tot = 0;
      for (const i of left) tot += w[i];
      let r = rng() * tot, k = 0;
      for (; k < left.length - 1; k++) { r -= w[left[k]]; if (r <= 0) break; }
      counts[ids[left[k]]][pos]++;
      left.splice(k, 1);
    }
  }
  return counts;
}

export function summarize(counts, nSims) {
  return Object.entries(counts).map(([driver_id, c]) => {
    const dist = c.map((v) => v / nSims);
    const finished = dist.reduce((a, b) => a + b, 0);
    return {
      driver_id, dist, out: finished < 0.5,
      win: dist[0], podium: dist[0] + dist[1] + dist[2],
      avg: finished > 0 ? dist.reduce((t, p, i) => t + p * (i + 1), 0) / finished : null,
    };
  });
}
