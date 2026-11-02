// A 1200×630 picture of the current forecast (the size social cards use), drawn on a canvas in the
// page's own colours and fonts. The phone's share sheet gets it where that exists; elsewhere it downloads.

const W = 1200, H = 630;
const C = { paper: "#0a0b0e", panel: "#14161b", ink: "#f4f5f7", slate: "#9aa1b0", rule: "#2a2e38", red: "#e10600", redText: "#ff4a40", yellow: "#ffd23f" };
const DISPLAY = '"Barlow Condensed", "Arial Narrow", Arial, sans-serif';
const TEXT = 'Barlow, "Helvetica Neue", Arial, sans-serif';

const spaced = (ctx, px) => { if ("letterSpacing" in ctx) ctx.letterSpacing = `${px}px`; };

// One line if it fits at `size`, else two balanced lines ("UNITED STATES / GRAND PRIX", not "... GRAND / PRIX"),
// shrinking the font until they fit `width`.
function fitLines(ctx, text, width, size, font) {
  const words = text.split(" ");
  for (let s = size; s > 24; s -= 4) {
    ctx.font = font(s);
    const w = (t) => ctx.measureText(t).width;
    if (w(text) <= width) return { lines: [text], size: s };
    let best = null;
    for (let i = 1; i < words.length; i++) {
      const pair = [words.slice(0, i).join(" "), words.slice(i).join(" ")];
      const widest = Math.max(...pair.map(w));
      if (widest <= width && (!best || widest < best.widest)) best = { lines: pair, widest };
    }
    if (best) return { lines: best.lines, size: s };
  }
  return { lines: [text], size: 24 };
}

/**
 * card: { eyebrow, title, tag, tagColour, rows: [{ code, colour, p, label }], footer, circuit: {d, w, h, start} | null }
 * Returns a PNG Blob.
 */
export async function drawCard(card) {
  await Promise.all([`italic 800 80px ${DISPLAY}`, `italic 700 40px ${DISPLAY}`, `500 22px ${TEXT}`, `600 22px ${TEXT}`]
    .map((f) => document.fonts?.load(f).catch(() => null)));
  const cv = Object.assign(document.createElement("canvas"), { width: W, height: H });
  const ctx = cv.getContext("2d");
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = C.red; ctx.fillRect(0, 0, W, 6);

  // brand: three rising bars, then the wordmark
  const bars = [[0, 18], [12, 26], [24, 22]];
  bars.forEach(([x, h]) => { ctx.save(); ctx.translate(64 + x, 76); ctx.transform(1, 0, -0.25, 1, 0, 0); ctx.fillStyle = C.red; ctx.fillRect(0, -h, 8, h); ctx.restore(); });
  ctx.font = `italic 800 34px ${DISPLAY}`; ctx.fillStyle = C.ink; ctx.textBaseline = "alphabetic";
  ctx.fillText("Automata", 108, 76);
  const bw = ctx.measureText("Automata").width;
  ctx.font = `italic 700 34px ${DISPLAY}`; ctx.fillStyle = C.redText; ctx.fillText("F1", 108 + bw + 6, 76);

  const left = 64, colW = card.circuit ? 640 : W - 128;
  ctx.font = `600 18px ${TEXT}`; spaced(ctx, 2.5); ctx.fillStyle = C.slate;
  ctx.fillText(card.eyebrow.toUpperCase(), left, 136);
  spaced(ctx, 0);

  const { lines, size } = fitLines(ctx, card.title.toUpperCase(), colW, 78, (s) => `italic 800 ${s}px ${DISPLAY}`);
  ctx.fillStyle = C.ink;
  lines.forEach((l, i) => ctx.fillText(l, left - 3, 136 + size * 0.95 * (i + 1)));
  let y = 136 + size * 0.95 * lines.length + 34;

  // stage tag, cut on the right like the site's tags
  ctx.font = `italic 700 20px ${DISPLAY}`; spaced(ctx, 1);
  const tw = ctx.measureText(card.tag).width + 30;
  ctx.fillStyle = card.tagColour;
  ctx.beginPath(); ctx.moveTo(left, y - 22); ctx.lineTo(left + tw, y - 22); ctx.lineTo(left + tw - 8, y + 8); ctx.lineTo(left, y + 8); ctx.fill();
  ctx.fillStyle = card.tagColour === C.yellow ? C.paper : "#fff"; ctx.fillText(card.tag, left + 12, y);
  spaced(ctx, 0);
  y += 30;

  // the top of the order
  const max = Math.max(...card.rows.map((r) => r.p));
  const rowH = Math.min(52, (H - 70 - y) / card.rows.length);
  card.rows.forEach((r, i) => {
    const ry = y + i * rowH;
    ctx.fillStyle = i === 0 ? C.panel : "transparent"; if (i === 0) ctx.fillRect(left, ry, colW, rowH - 6);
    ctx.fillStyle = r.colour; ctx.fillRect(left, ry, 6, rowH - 6);
    ctx.font = `italic 700 ${i === 0 ? 32 : 28}px ${DISPLAY}`; ctx.fillStyle = C.ink;
    ctx.fillText(r.code, left + 20, ry + rowH / 2 + 7);
    const bx = left + 110, bwMax = colW - 110 - 110;
    ctx.fillStyle = C.rule; ctx.fillRect(bx, ry + rowH / 2 - 6, bwMax, 6);
    ctx.fillStyle = i === 0 ? C.ink : r.colour; ctx.fillRect(bx, ry + rowH / 2 - 6, Math.max(4, (r.p / max) * bwMax), 6);
    ctx.textAlign = "right"; ctx.fillStyle = C.ink;
    ctx.font = `italic 800 ${i === 0 ? 36 : 30}px ${DISPLAY}`;
    ctx.fillText(r.label, left + colW - 12, ry + rowH / 2 + 9);
    ctx.textAlign = "left";
  });

  // the circuit, filling the right-hand side
  if (card.circuit) {
    const c = card.circuit, box = { x: 760, y: 120, w: 380, h: 400 };
    const k = Math.min(box.w / c.w, box.h / c.h);
    ctx.save();
    ctx.translate(box.x + (box.w - c.w * k) / 2, box.y + (box.h - c.h * k) / 2); ctx.scale(k, k);
    const path = new Path2D(c.d);
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.strokeStyle = C.rule; ctx.lineWidth = 14 / k; ctx.stroke(path);      // widths in screen pixels
    ctx.strokeStyle = C.ink; ctx.lineWidth = 5 / k; ctx.stroke(path);
    const [sx, sy] = c.start; ctx.fillStyle = C.red; ctx.fillRect(sx - 9, sy - 26, 18, 52);
    ctx.restore();
  }

  ctx.font = `500 18px ${TEXT}`; ctx.fillStyle = C.slate;
  ctx.fillText(card.footer, left, H - 34);
  return new Promise((res) => cv.toBlob(res, "image/png"));
}

/** Opens the share sheet with the picture where the browser can, else downloads it. */
export async function shareCard(card, filename) {
  const blob = await drawCard(card);
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file], title: card.title }); return "shared"; }
    catch (e) { if (e.name === "AbortError") return "cancelled"; }
  }
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  return "downloaded";
}
