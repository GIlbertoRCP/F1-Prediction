// Display names and colours shared by the page, the share picture and the link-preview picture.

export const TEAM_COLOURS = {
  red_bull: "#4a6bff", mercedes: "#27d1c0", ferrari: "#ef1a2d", mclaren: "#ff8000",
  aston_martin: "#2aa58f", alpine: "#ff87bc", williams: "#3ab4ee", rb: "#7da0ff",
  alphatauri: "#7aa6c6", toro_rosso: "#7aa6c6", haas: "#b58ae6", sauber: "#52e252",
  alfa: "#d8465c", audi: "#e0334f", cadillac: "#9aa5b8", renault: "#ffd800",
  racing_point: "#f596c8", force_india: "#f596c8",
};
export const CIRCUIT_NAMES = {
  albert_park: "Albert Park, Melbourne", shanghai: "Shanghai International Circuit", suzuka: "Suzuka", bahrain: "Bahrain International Circuit",
  jeddah: "Jeddah Corniche Circuit", miami: "Miami International Autodrome", villeneuve: "Circuit Gilles Villeneuve, Montréal",
  monaco: "Circuit de Monaco", catalunya: "Circuit de Barcelona-Catalunya", madring: "Madring, Madrid", red_bull_ring: "Red Bull Ring, Spielberg",
  silverstone: "Silverstone", spa: "Spa-Francorchamps", hungaroring: "Hungaroring, Budapest", zandvoort: "Zandvoort",
  monza: "Monza", baku: "Baku City Circuit", marina_bay: "Marina Bay, Singapore", sepang: "Sepang", americas: "Circuit of the Americas, Austin",
  rodriguez: "Autódromo Hermanos Rodríguez, Mexico City", interlagos: "Interlagos, São Paulo", vegas: "Las Vegas Strip Circuit",
  losail: "Lusail International Circuit", yas_marina: "Yas Marina, Abu Dhabi", imola: "Imola", istanbul: "Istanbul Park",
};
export const colour = (team) => TEAM_COLOURS[team] || "#8a8f98";
export const TEAM_NAMES = { mclaren: "McLaren", rb: "Racing Bulls", alphatauri: "AlphaTauri", toro_rosso: "Toro Rosso", alfa: "Alfa Romeo",
  haas: "Haas", sauber: "Sauber", audi: "Audi", cadillac: "Cadillac", racing_point: "Racing Point", force_india: "Force India" };
export const teamName = (t) => TEAM_NAMES[t] || t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const venue = (race) => `Round ${race.round}${CIRCUIT_NAMES[race.circuit] ? ` · ${CIRCUIT_NAMES[race.circuit]}` : ""}`;
