// Circuit outlines drawn from real car positions (data/circuits.json, made by scripts/extract_circuits.py).
// Returns "" when a circuit has no outline yet, so the page simply shows no map.

export function circuitFigure(circuits, id, caption = "") {
  const c = circuits && id ? circuits[id] : null;
  if (!c || !c.d) return "";
  const pad = 40;
  const [sx, sy] = c.start;
  return `<figure class="circuit">
    <svg viewBox="${-pad} ${-pad} ${c.w + pad * 2} ${c.h + pad * 2}" role="img" aria-label="Outline of the circuit${caption ? `: ${caption}` : ""}">
      <path class="trk-bed" d="${c.d}"/>
      <path class="trk" d="${c.d}"/>
      <rect class="sf" x="${sx - 9}" y="${sy - 26}" width="18" height="52" transform="rotate(0 ${sx} ${sy})"/>
    </svg>
    ${caption ? `<figcaption>${caption}</figcaption>` : ""}
  </figure>`;
}
