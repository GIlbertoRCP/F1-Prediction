import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { compare, teammatePairs } from "../site/h2h.js";

const toy = {
  rounds: [{}, {}, {}, {}, {}],
  drivers: {
    a: { team: ["x", "x", "x", "x", null], q: [1, 3, 2, 5, null], f: [1, 0, 2, 0, null], pts: [25, 0, 18, 0, 0] },
    b: { team: ["x", "x", "x", "x", "y"], q: [2, 1, 4, 5, 9], f: [3, 4, 0, 0, 6], pts: [15, 12, 0, 0, 8] },
  },
};

test("counts qualifying, race, points and retirements only where both took part", () => {
  const c = compare(toy, "a", "b");
  assert.equal(c.together, 4);
  assert.deepEqual(c.quali, { a: 2, b: 1, n: 4 });         // round 4 tie counts for neither
  assert.deepEqual(c.race, { a: 2, b: 1, n: 3 });          // round 4: both retired, no result
  assert.deepEqual(c.points, { a: 43, b: 27 });
  assert.deepEqual(c.dnf, { a: 2, b: 2 });
  assert.deepEqual(c.avgFinish, { a: 1, b: 3 });            // only round 1 had both classified
});

test("a retirement loses to a classified finish", () => {
  const c = compare(toy, "a", "b");
  // round 2: a retired, b 4th -> b ahead; round 3: a 2nd, b retired -> a ahead; round 1: a ahead
  assert.equal(c.race.a, 2);
  assert.equal(c.race.b, 1);
});

test("symmetry: swapping the drivers swaps the sides", () => {
  const ab = compare(toy, "a", "b"), ba = compare(toy, "b", "a");
  assert.deepEqual([ab.quali.a, ab.quali.b], [ba.quali.b, ba.quali.a]);
  assert.deepEqual([ab.race.a, ab.race.b], [ba.race.b, ba.race.a]);
  assert.equal(ab.points.a, ba.points.b);
});

test("teammate pairs need enough shared rounds", () => {
  assert.equal(teammatePairs(toy, 3).length, 1);
  assert.equal(teammatePairs(toy, 5).length, 0);
});

const real = JSON.parse(fs.readFileSync(new URL("../site/data/h2h.json", import.meta.url)));

test("real data: points add up to the season's raw points for every driver", () => {
  for (const season of Object.values(real)) {
    const ids = Object.keys(season.drivers);
    for (const id of ids.slice(0, 6)) {
      const other = ids.find((d) => d !== id);
      const c = compare(season, id, other);
      const mine = season.drivers[id].pts.reduce((t, v, i) => t + (season.drivers[other].team[i] != null ? v : 0), 0);
      assert.equal(c.points.a, mine);
      assert.ok(c.quali.a + c.quali.b <= c.quali.n && c.quali.n <= c.together);
      assert.ok(c.race.a + c.race.b === c.race.n);
    }
  }
});
