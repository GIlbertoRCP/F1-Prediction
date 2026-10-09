// Points-over-the-season line chart: 2px lines, a legend, direct labels on the leaders, a crosshair
// tooltip listing every series, keyboard support and a table view. Series names are set with
// textContent, never as markup.

const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, parent) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.append(e);
  return e;
};
const html = (tag, cls, text, parent) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  if (parent) parent.append(e);
  return e;
};

/**
 * series: [{name, color, dash, values: [y at x=0..n]}]; xLabels: label for each x (index 0 = start).
 */
export function lineChart(container, series, xLabels, { unit = "points" } = {}) {
  container.textContent = "";
  const W = 1000, H = 360, m = { l: 48, r: 64, t: 12, b: 30 };
  const n = xLabels.length - 1;
  const ymax = Math.max(1, ...series.flatMap((s) => s.values));
  const step = [10, 20, 25, 50, 100, 200, 250, 500].find((s) => ymax / s <= 6) || 500;
  const top = Math.ceil(ymax / step) * step;
  const x = (i) => m.l + (i / n) * (W - m.l - m.r);
  const y = (v) => H - m.b - (v / top) * (H - m.t - m.b);

  const legend = html("div", "lc-legend", null, container);
  series.forEach((s) => {
    const item = html("span", "lc-key", null, legend);
    const sw = el("svg", { width: 22, height: 10, "aria-hidden": "true" });
    el("line", { x1: 1, x2: 21, y1: 5, y2: 5, stroke: s.color, "stroke-width": 2.5, "stroke-linecap": "round", ...(s.dash ? { "stroke-dasharray": s.dash } : {}) }, sw);
    item.append(sw);
    html("span", null, s.name, item);
  });

  const wrap = html("div", "lc-wrap", null, container);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "lc", role: "img", tabindex: 0,
    "aria-label": `Cumulative ${unit} after each round. Use the arrow keys to move between rounds.` });
  wrap.append(svg);

  for (let v = 0; v <= top; v += step) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: "var(--rule)", "stroke-width": 1 }, svg);
    const t = el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "lc-tick" }, svg);
    t.textContent = v;
  }
  const every = Math.ceil(n / 12);
  xLabels.forEach((lab, i) => {
    if (i === 0 || (i % every && i !== n)) return;
    const t = el("text", { x: x(i), y: H - 8, "text-anchor": "middle", class: "lc-tick" }, svg);
    t.textContent = lab;
  });

  series.forEach((s) => {
    const d = s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
    el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
      ...(s.dash ? { "stroke-dasharray": s.dash } : {}) }, svg);
  });

  // direct labels on the four leaders, nudged apart
  const ends = series.slice(0, 4).map((s) => ({ s, y: y(s.values[n]) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
  ends.forEach((e) => {
    const t = el("text", { x: x(n) + 8, y: e.y + 4, class: "lc-end" }, svg);
    t.textContent = e.s.name;
  });

  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--ink)", "stroke-width": 1, opacity: 0 }, svg);
  const tip = html("div", "lc-tip", null, wrap);
  tip.hidden = true;
  let at = n;
  const show = (i) => {
    at = Math.max(0, Math.min(n, i));
    cross.setAttribute("x1", x(at)); cross.setAttribute("x2", x(at)); cross.setAttribute("opacity", 1);
    tip.textContent = "";
    html("div", "lc-tip-head", xLabels[at], tip);
    series.map((s) => ({ s, v: s.values[at] })).sort((a, b) => b.v - a.v).forEach(({ s, v }) => {
      const row = html("div", "lc-tip-row", null, tip);
      const k = el("svg", { width: 16, height: 8, "aria-hidden": "true" });
      el("line", { x1: 1, x2: 15, y1: 4, y2: 4, stroke: s.color, "stroke-width": 2.5, "stroke-linecap": "round", ...(s.dash ? { "stroke-dasharray": s.dash } : {}) }, k);
      row.append(k);
      html("b", "num", Number.isInteger(v) ? String(v) : v.toFixed(1), row);
      html("span", null, s.name, row);
    });
    tip.hidden = false;
    const left = (x(at) / W) * wrap.clientWidth;
    tip.style.left = `${Math.min(left + 12, wrap.clientWidth - tip.offsetWidth - 4)}px`;
  };
  const hide = () => { cross.setAttribute("opacity", 0); tip.hidden = true; };
  svg.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect();
    show(Math.round((((ev.clientX - r.left) / r.width) * W - m.l) / ((W - m.l - m.r) / n)));
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowRight") { show(at + 1); ev.preventDefault(); }
    if (ev.key === "ArrowLeft") { show(at - 1); ev.preventDefault(); }
    if (ev.key === "Escape") hide();
  });
  svg.addEventListener("blur", hide);

  // table view: every value the tooltip can show
  const details = html("details", "lc-table", null, container);
  html("summary", null, "Show the numbers as a table", details);
  const wrapT = html("div", "tablewrap", null, details);
  const table = html("table", null, null, wrapT);
  const head = html("tr", null, null, html("thead", null, null, table));
  html("th", null, "After round", head);
  series.forEach((s) => html("th", null, s.name, head));
  const body = html("tbody", null, null, table);
  xLabels.forEach((lab, i) => {
    if (i === 0) return;
    const tr = html("tr", null, null, body);
    html("td", null, lab, tr);
    series.forEach((s) => html("td", "num", Number.isInteger(s.values[i]) ? String(s.values[i]) : s.values[i].toFixed(1), tr));
  });
}
