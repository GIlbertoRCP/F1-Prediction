import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { titleStory, forecastStory } from "../site/recap.js";

const h2h = JSON.parse(fs.readFileSync(new URL("../site/data/h2h.json", import.meta.url)));
const record = JSON.parse(fs.readFileSync(new URL("../site/data/track_record.json", import.meta.url)));
// the sprint flags on each round, as the publisher now writes them (the committed data may predate them)
const season2025 = { ...h2h["2025"], rounds: h2h["2025"].rounds.map((r) => ({ ...r, sprint: [2, 6, 13, 19, 21, 23].includes(r.round) })) };

test("2025: Norris settled it only at the last round", () => {
  const t = titleStory(season2025, "d");
  assert.equal(t.champ.id, "norris");
  assert.equal(t.champ.points, 423);
  assert.equal(t.settledAfter, 24);
  assert.equal(t.left, 0);
  assert.equal(t.margin, 2);
});

test("2025: McLaren clinched the constructors' with six rounds to go, sprints counted", () => {
  const t = titleStory(season2025, "c");
  assert.equal(t.champ.id, "mclaren");
  assert.equal(t.settledAfter, 18);
  assert.equal(t.left, 6);
});

test("forecast story counts hits and finds the upset and the best call", () => {
  const races = [
    { season: 1, kind: "live", hit: true, p_winner: 0.6, winner_id: "a" },
    { season: 1, kind: "backtest", hit: false, p_winner: 0.02, winner_id: "b" },
    { season: 1, kind: "backtest", hit: true, p_winner: 0.4, winner_id: "a" },
    { season: 2, kind: "live", hit: true, p_winner: 0.9, winner_id: "c" },
  ];
  const f = forecastStory(races, 1);
  assert.deepEqual([f.n, f.hits, f.live, f.winners], [3, 2, 1, 2]);
  assert.equal(f.upset.p_winner, 0.02);
  assert.equal(f.bestCall.p_winner, 0.6);
  assert.equal(forecastStory(races, 3), null);
  assert.ok(forecastStory(record.races, 2025).n > 20);
});
