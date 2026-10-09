import test from "node:test";
import assert from "node:assert/strict";
import { loadPicks, savePick, points, tally } from "../site/picks.js";

const memory = () => { const m = {}; return { getItem: (k) => m[k] ?? null, setItem: (k, v) => { m[k] = v; } }; };

test("picks round-trip and a later pick replaces an earlier one", () => {
  const st = memory();
  savePick("2026-17", "norris", st, new Date("2026-10-17T10:00:00Z"));
  savePick("2026-17", "piastri", st);
  assert.equal(loadPicks(st)["2026-17"].driver_id, "piastri");
});

test("storage failures never throw", () => {
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.deepEqual(loadPicks(broken), {});
  assert.doesNotThrow(() => savePick("2026-17", "norris", broken));
});

test("points are fair odds, capped at 100", () => {
  assert.equal(points(0.5), 2);
  assert.equal(points(0.04), 25);
  assert.equal(points(0.0001), 100);
});

test("tally only counts finished races and compares with the Oracle's top pick", () => {
  const picks = { "2026-1": { driver_id: "b" }, "2026-2": { driver_id: "a" }, "2026-3": { driver_id: "a" } };
  const settled = {
    "2026-1": { race: "One", date: "2026-03-01", winner_id: "b", winner: "BBB", pick: "AAA", pick_p: 0.6, hit: false },
    "2026-2": { race: "Two", date: "2026-03-08", winner_id: "a", winner: "AAA", pick: "AAA", pick_p: 0.5, hit: true },
  };
  const page = { predictions: [{ driver_id: "a", driver: "AAA", p: 0.5 }, { driver_id: "b", driver: "BBB", p: 0.1 }] };
  const t = tally(picks, settled, { "2026-1": page, "2026-2": page, "2026-3": page });
  assert.equal(t.you.n, 2);                 // race 3 has no result yet
  assert.equal(t.you.wins, 2);
  assert.equal(t.you.points, 10 + 2);       // 1/0.1 for the upset, 1/0.5 for the favourite
  assert.equal(t.oracle.wins, 1);
  assert.equal(t.oracle.points, 2);
  assert.equal(t.rows[0].race, "Two");      // newest first
});
