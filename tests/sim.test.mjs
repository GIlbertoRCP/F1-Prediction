import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { utilities, winProbs, simulate, summarize } from "../site/sim.js";

const page = JSON.parse(fs.readFileSync(new URL("../site/data/races/2026-16.json", import.meta.url)));
const sim = page.simulator;
const published = Object.fromEntries(page.predictions.map((p) => [p.driver_id, p]));

test("browser model reproduces the published win odds exactly", () => {
  const w = winProbs(utilities(sim));
  for (const [id, p] of Object.entries(w)) assert.ok(Math.abs(p - published[id].p) < 2e-6, `${id}: ${p} vs ${published[id].p}`);
});

test("simulated win and podium odds match the published exact odds", () => {
  const u = utilities(sim);
  const n = 20000;
  const rows = Object.fromEntries(summarize(simulate(u, sim.model.scales, n, { seed: 7 }), n).map((r) => [r.driver_id, r]));
  for (const id of Object.keys(u)) {
    assert.ok(Math.abs(rows[id].win - published[id].p) < 0.012, `win ${id}`);
    assert.ok(Math.abs(rows[id].podium - published[id].podium) < 0.015, `podium ${id}`);
  }
});

test("each place is filled exactly once per simulated race", () => {
  const u = utilities(sim), n = 500;
  const counts = simulate(u, sim.model.scales, n, { seed: 3 });
  const ids = Object.keys(u);
  for (let pos = 0; pos < ids.length; pos++) assert.equal(ids.reduce((t, d) => t + counts[d][pos], 0), n);
});

test("moving a driver to pole raises his win chance, and a retired driver never finishes", () => {
  const base = winProbs(utilities(sim));
  const slowest = Object.entries(published).sort((a, b) => b[1].grid - a[1].grid)[0][0];
  const moved = winProbs(utilities(sim, { [slowest]: 1 }));
  assert.ok(moved[slowest] > base[slowest]);
  const out = new Set(["max_verstappen"]);
  const rows = summarize(simulate(utilities(sim), sim.model.scales, 400, { out, seed: 1 }), 400);
  const v = rows.find((r) => r.driver_id === "max_verstappen");
  assert.equal(v.win, 0);
  assert.equal(v.out, true);
  assert.ok(Math.abs(rows.reduce((t, r) => t + r.win, 0) - 1) < 1e-9);
});

test("same seed gives the same simulation", () => {
  const u = utilities(sim);
  assert.deepEqual(simulate(u, sim.model.scales, 200, { seed: 5 }), simulate(u, sim.model.scales, 200, { seed: 5 }));
});
