import { useState, useEffect } from 'react';

export default function EngineBattle({ year, gp }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!year || !gp) return;

    setLoading(true);
    setError(null);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    fetch(`${apiUrl}/api/engine/${year}/${encodeURIComponent(gp)}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Failed to load engine battle analytics');
        }
        return res.json();
      })
      .then(json => {
        setData(json);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load engine battle:", err);
        setError(err.message);
        setLoading(false);
      });
  }, [year, gp]);

  if (loading) {
    return (
      <div className="h-[40vh] flex flex-col items-center justify-center font-mono text-zinc-400 gap-4">
        <div className="relative flex h-8 w-8">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-8 w-8 bg-red-500 shadow-[0_0_15px_rgba(239,68,68,0.8)]"></span>
        </div>
        <span className="text-xs uppercase tracking-widest animate-pulse">Aggregating MGU-K & MGU-H Telemetry...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-950/20 border border-red-900/50 p-6 rounded-lg font-mono text-red-500 text-xs max-w-lg mx-auto flex flex-col gap-2">
        <h3 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2">
          <span>[!]</span> Engine Analytics Error
        </h3>
        <p className="text-zinc-300">{error}</p>
        <span className="text-[10px] text-zinc-500 border-t border-red-900/20 pt-2 uppercase">
          Ensure telemetry data exists on backend
        </span>
      </div>
    );
  }

  if (!data || !data.manufacturers) return null;

  // Find the top manufacturer
  const leader = data.manufacturers[0];

  // Colors mapping for manufacturers
  const mfrColors = {
    "Mercedes": {
      text: "text-teal-400",
      border: "border-teal-500/30",
      glow: "shadow-[0_0_20px_rgba(45,212,191,0.15)]",
      bar: "from-teal-600 to-emerald-500",
      badge: "bg-teal-950/50 text-teal-400 border-teal-900/50",
    },
    "Ferrari": {
      text: "text-red-500",
      border: "border-red-500/30",
      glow: "shadow-[0_0_20px_rgba(239,68,68,0.15)]",
      bar: "from-red-600 to-orange-500",
      badge: "bg-red-950/50 text-red-400 border-red-900/50",
    },
    "Red Bull Powertrains": {
      text: "text-blue-400",
      border: "border-blue-500/30",
      glow: "shadow-[0_0_20px_rgba(96,165,250,0.15)]",
      bar: "from-blue-600 to-indigo-500",
      badge: "bg-blue-950/50 text-blue-400 border-blue-900/50",
    },
    "Honda": {
      text: "text-amber-500",
      border: "border-amber-500/30",
      glow: "shadow-[0_0_20px_rgba(245,158,11,0.15)]",
      bar: "from-amber-500 to-yellow-500",
      badge: "bg-amber-950/50 text-amber-400 border-amber-900/50",
    },
    "Audi": {
      text: "text-zinc-300",
      border: "border-zinc-500/30",
      glow: "shadow-[0_0_20px_rgba(212,212,216,0.15)]",
      bar: "from-zinc-500 to-zinc-400",
      badge: "bg-zinc-800/50 text-zinc-300 border-zinc-700/50",
    },
    "Cadillac": {
      text: "text-white",
      border: "border-zinc-300/30",
      glow: "shadow-[0_0_20px_rgba(255,255,255,0.15)]",
      bar: "from-zinc-400 to-zinc-200",
      badge: "bg-zinc-950/50 text-white border-zinc-800",
    }
  };

  const defaultColor = {
    text: "text-zinc-400",
    border: "border-zinc-800",
    glow: "shadow-none",
    bar: "from-zinc-700 to-zinc-600",
    badge: "bg-zinc-950 text-zinc-400 border-zinc-800"
  };

  return (
    <div className="w-full flex flex-col gap-8">
      {/* SECTION HEADER */}
      <div>
        <h2 className="text-xl font-bold uppercase tracking-wide border-l-4 border-red-600 pl-3">
          2026 Engine Regulation Manufacturer Battle
        </h2>
        <p className="text-xs text-zinc-500 font-mono mt-1 uppercase tracking-widest">
          Telemetry-Aggregated Hybrid Deployment & ERS Efficiency for {data.gp}
        </p>
      </div>

      {/* LEADER NARRATIVE SUMMARY */}
      {leader && (
        <div className="relative bg-zinc-900/40 backdrop-blur-md border border-zinc-800/80 rounded-xl p-6 shadow-xl overflow-hidden">
          <div className="absolute top-0 left-0 w-2 h-full bg-gradient-to-b from-red-600 to-orange-600" />
          <h3 className="text-sm font-bold font-mono text-zinc-300 uppercase tracking-widest mb-3">
            Grand Prix Engine Analysis
          </h3>
          <p className="text-sm text-zinc-400 leading-relaxed font-sans">
            At the <strong className="text-zinc-100">{data.gp}</strong>, telemetry indicates that <strong className="text-white">{leader.manufacturer}</strong> power units have registered the highest overall hybrid performance rating of <strong className="text-red-500">{leader.overall_performance_score.toFixed(2)}/10.00</strong>. This score represents superior MGU-K electrical deployment and maximum battery clipping resistance (averaging <strong className="text-zinc-200">{leader.avg_top_speed.toFixed(1)} km/h</strong> across speed traps). The telemetry groups performance values across works and customer squads to isolate aerodynamic drag from pure power unit efficiency.
          </p>
        </div>
      )}

      {/* LEADERBOARD CARD GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {data.manufacturers.map((mfr) => {
          const style = mfrColors[mfr.manufacturer] || defaultColor;
          
          let rankColor = "text-zinc-500 border-zinc-800";
          let cardBorder = "border-zinc-800/80";
          if (mfr.rank === 1) {
            rankColor = "text-yellow-500 border-yellow-500/20 bg-yellow-500/5";
            cardBorder = "border-yellow-500/30 shadow-[0_0_25px_rgba(234,179,8,0.06)]";
          } else if (mfr.rank === 2) {
            rankColor = "text-zinc-400 border-zinc-400/20 bg-zinc-400/5";
          } else if (mfr.rank === 3) {
            rankColor = "text-amber-600 border-amber-600/20 bg-amber-600/5";
          }

          return (
            <div 
              key={mfr.manufacturer}
              className={`bg-zinc-900/60 backdrop-blur-md border rounded-2xl p-6 flex flex-col gap-5 relative overflow-hidden transition-all duration-300 hover:border-zinc-700/80 shadow-lg ${cardBorder}`}
            >
              {/* TOP CARD DETAIL BAR */}
              <div className="flex justify-between items-center pb-3 border-b border-zinc-800/60">
                <div className="flex items-center gap-3">
                  <div className={`h-8 w-8 rounded-lg border flex items-center justify-center font-orbitron font-black text-sm ${rankColor}`}>
                    #{mfr.rank}
                  </div>
                  <div>
                    <h3 className={`font-orbitron text-base font-black tracking-tight ${style.text}`}>
                      {mfr.manufacturer}
                    </h3>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {mfr.teams.map(t => (
                        <span key={t} className="text-[8px] bg-zinc-950 text-zinc-500 px-1.5 py-0.5 rounded font-mono font-bold uppercase tracking-wider">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                
                {/* OVERALL PERFORMANCE BADGE */}
                <div className="text-right flex flex-col items-end">
                  <span className="text-[8px] text-zinc-500 font-mono uppercase tracking-widest">Perf Index</span>
                  <div className={`font-orbitron text-xl font-black ${style.text}`}>
                    {mfr.overall_performance_score.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* GAUGES & METRICS */}
              <div className="flex flex-col gap-4 font-mono text-xs">
                {/* Metric 1: Top Speed */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-[10px] text-zinc-400 uppercase">
                    <span>Avg Straight-Line Velocity</span>
                    <span className="font-bold text-white">{mfr.avg_top_speed} km/h</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-2.5 p-0.5 border border-zinc-800/60">
                    <div 
                      className={`bg-gradient-to-r ${style.bar} h-1.5 rounded-full`}
                      style={{ width: `${Math.max(10, ((mfr.avg_top_speed - 300) / 50) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* Metric 2: ERS Efficiency */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-[10px] text-zinc-400 uppercase">
                    <span>MGU-K Hybrid Deployment Efficiency</span>
                    <span className="font-bold text-white">{mfr.ers_efficiency_score.toFixed(2)}/10</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-2.5 p-0.5 border border-zinc-800/60">
                    <div 
                      className={`bg-gradient-to-r ${style.bar} h-1.5 rounded-full`}
                      style={{ width: `${mfr.ers_efficiency_score * 10}%` }}
                    />
                  </div>
                </div>

                {/* Metric 3: Clipping Resistance */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-[10px] text-zinc-400 uppercase">
                    <span>Battery Derate / Clipping Resistance</span>
                    <span className="font-bold text-white">{mfr.clipping_resistance_score.toFixed(2)}/10</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-2.5 p-0.5 border border-zinc-800/60">
                    <div 
                      className={`bg-gradient-to-r ${style.bar} h-1.5 rounded-full`}
                      style={{ width: `${mfr.clipping_resistance_score * 10}%` }}
                    />
                  </div>
                </div>

                {/* Metric 4: Baseline PU Rating */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-[10px] text-zinc-400 uppercase">
                    <span>PU Baseline Combustion Rating</span>
                    <span className="font-bold text-white">{mfr.baseline_pu_rating.toFixed(1)}/5.0</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-2.5 p-0.5 border border-zinc-800/60">
                    <div 
                      className={`bg-gradient-to-r ${style.bar} h-1.5 rounded-full`}
                      style={{ width: `${(mfr.baseline_pu_rating / 5) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
