import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { driverStandings, teamStandings } from "../site/standings.js";

const real = JSON.parse(fs.readFileSync(new URL("../site/data/h2h.json", import.meta.url)));

test("toy season: points, sprint points, countback and mid-season team change", () => {
  const season = {
    rounds: [{}, {}, {}],
    drivers: {
      a: { code: "AAA", team: ["x", "x", "y"], f: [1, 2, 0], pts: [25, 18, 0], spts: [0, 8, 0] },
      b: { code: "BBB", team: ["y", "y", "y"], f: [2, 1, 1], pts: [18, 25, 25], spts: [0, 0, 0] },
      c: { code: "CCC", team: ["x", "x", "x"], f: [3, 3, 2], pts: [15, 15, 18], spts: [0, 0, 0] },
    },
  };
  const d = driverStandings(season);
  assert.deepEqual(d.map((r) => [r.id, r.points]), [["b", 68], ["a", 51], ["c", 48]]);
  assert.equal(d[0].wins, 2);
  assert.equal(d.find((r) => r.id === "a").team, "y");               // latest team
  assert.deepEqual(d[0].cumulative, [0, 18, 43, 68]);
  const t = teamStandings(season);
  assert.deepEqual(Object.fromEntries(t.map((r) => [r.id, r.points])), { x: 25 + 26 + 15 + 15 + 18, y: 18 + 25 + 25 + 0 });
  assert.equal(d.reduce((s, r) => s + r.points, 0), t.reduce((s, r) => s + r.points, 0));   // same total points
});

test("equal points are split by best finishes", () => {
  const season = { rounds: [{}, {}], drivers: {
    a: { code: "A", team: ["x", "x"], f: [1, 5], pts: [25, 10], spts: [0, 0] },
    b: { code: "B", team: ["y", "y"], f: [3, 2], pts: [15, 20], spts: [0, 0] } } };
  assert.equal(driverStandings(season)[0].id, "a");
});

// Final tables of real seasons, as published by the championship.
const FINAL = {
  "2024": { drivers: [["max_verstappen", 437], ["norris", 374], ["leclerc", 356]], teams: [["mclaren", 666], ["ferrari", 652], ["red_bull", 589]] },
  "2021": { drivers: [["max_verstappen", 395.5], ["hamilton", 387.5], ["bottas", 226]], teams: [["mercedes", 613.5], ["red_bull", 585.5]] },
  "2025": { drivers: [["norris", 423], ["max_verstappen", 421], ["piastri", 410]], teams: [["mclaren", 833], ["mercedes", 469]] },
};
test("real seasons reproduce the published final standings", () => {
  for (const [year, exp] of Object.entries(FINAL)) {
    const d = driverStandings(real[year]);
    exp.drivers.forEach(([id, pts], i) => { assert.equal(d[i].id, id, `${year} position ${i + 1}`); assert.equal(d[i].points, pts); });
    const t = teamStandings(real[year]);
    exp.teams.forEach(([id, pts], i) => { assert.equal(t[i].id, id, `${year} team ${i + 1}`); assert.equal(t[i].points, pts); });
  }
});
