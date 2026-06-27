import { useState } from 'react';

// Helper to convert time strings (e.g., "1:12:45" or "45:12") to total seconds
const parseTimeToSeconds = (timeStr) => {
  if (!timeStr) return 0;
  const parts = timeStr.split(':').map(Number);
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return Number(timeStr) || 0;
};

export default function RaceTimeline({ logs, gpName, year }) {
  const [activePhase, setActivePhase] = useState(0);

  const hasLogs = logs && logs.length > 0;

  if (!hasLogs) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 p-8 rounded-lg mt-8 text-center max-w-2xl mx-auto flex flex-col items-center gap-6 shadow-2xl relative overflow-hidden">
        <div className="absolute -top-12 -right-12 w-48 h-48 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />
        
        <div className="h-14 w-14 bg-blue-950/40 text-blue-400 border border-blue-900 rounded-full flex items-center justify-center text-xs font-bold animate-pulse font-mono">
          TIME
        </div>
        <div>
          <h2 className="font-orbitron font-black text-lg text-white mb-2 uppercase tracking-wide">Pre-Race Event Bulletin</h2>
          <p className="text-zinc-400 text-sm font-sans leading-relaxed">
            The {gpName} {year} has not started yet, or is currently in progress. Race control messages and timing log timeline feeds will go live as soon as the checkered flag falls.
          </p>
        </div>
        <div className="w-full bg-zinc-950/80 border border-zinc-800 rounded p-4 text-left font-mono text-[11px] leading-relaxed">
          <div className="text-blue-400 font-bold uppercase mb-2">// PREDICTIVE ANALYSIS INDICATORS</div>
          <div>· Model status: <span className="text-emerald-400 font-bold">XGBRanker calibrated</span></div>
          <div>· Track classification: <span className="text-white font-bold">{gpName} circuit profile merged</span></div>
          <div>· System recommendation: <span className="text-yellow-500 font-bold">Check Aero Setup & Grid tabs for practice pace analytics</span></div>
        </div>
      </div>
    );
  }

  // Parse times of all logs
  const logsWithSeconds = logs.map(log => ({
    ...log,
    seconds: parseTimeToSeconds(log.Time)
  }));
  
  // Divide total elapsed time into 4 equal quarters
  const maxSec = Math.max(...logsWithSeconds.map(l => l.seconds), 1);
  const quarter = maxSec / 4;

  const phases = [
    {
      id: 0,
      title: "Opening Phase",
      subtitle: "Start & Early Battles",
      desc: `The opening quarter of the ${gpName} saw teams managing heavy fuel loads and cold tyres. Drivers focused on securing track positions and settling into tyre conservation routines.`,
      logRange: [0, quarter],
      stats: [
        { label: "Safety Cars", val: logs.filter(l => l.Category === "SafetyCar" && parseTimeToSeconds(l.Time) <= quarter).length },
        { label: "Penalties", val: logs.filter(l => l.Category === "Penalty" && parseTimeToSeconds(l.Time) <= quarter).length },
        { label: "Active Logs", val: logsWithSeconds.filter(l => l.seconds <= quarter).length }
      ]
    },
    {
      id: 1,
      title: "Mid-Race Phase",
      subtitle: "Strategy & First Stops",
      desc: `As tyre degradation set in, the pit window opened. Drivers fought to optimize tyre life, manage hybrid battery charge, and execute clean overtakes inside the DRS zones.`,
      logRange: [quarter, quarter * 2],
      stats: [
        { label: "Safety Cars", val: logs.filter(l => l.Category === "SafetyCar" && parseTimeToSeconds(l.Time) > quarter && parseTimeToSeconds(l.Time) <= quarter * 2).length },
        { label: "Penalties", val: logs.filter(l => l.Category === "Penalty" && parseTimeToSeconds(l.Time) > quarter && parseTimeToSeconds(l.Time) <= quarter * 2).length },
        { label: "Active Logs", val: logsWithSeconds.filter(l => l.seconds > quarter && l.seconds <= quarter * 2).length }
      ]
    },
    {
      id: 2,
      title: "Tricky Transitions",
      subtitle: "Tire Cliffs & Setup Adaptations",
      desc: `The third quarter introduced track evolution shifts and potential weather adjustments. Power units were pushed hard, and some drivers faced reliability issues or tactical changes.`,
      logRange: [quarter * 2, quarter * 3],
      stats: [
        { label: "Safety Cars", val: logs.filter(l => l.Category === "SafetyCar" && parseTimeToSeconds(l.Time) > quarter * 2 && parseTimeToSeconds(l.Time) <= quarter * 3).length },
        { label: "Penalties", val: logs.filter(l => l.Category === "Penalty" && parseTimeToSeconds(l.Time) > quarter * 2 && parseTimeToSeconds(l.Time) <= quarter * 3).length },
        { label: "Active Logs", val: logsWithSeconds.filter(l => l.seconds > quarter * 2 && l.seconds <= quarter * 3).length }
      ]
    },
    {
      id: 3,
      title: "Closing Sprints",
      subtitle: "Podium Shootout & Checkered Flag",
      desc: `Low fuel loads unlocked peak performance. The final quarter was a race-to-the-line sprint as drivers exhausted their ERS hybrid batteries to claim valuable points.`,
      logRange: [quarter * 3, maxSec + 1],
      stats: [
        { label: "Safety Cars", val: logs.filter(l => l.Category === "SafetyCar" && parseTimeToSeconds(l.Time) > quarter * 3).length },
        { label: "Penalties", val: logs.filter(l => l.Category === "Penalty" && parseTimeToSeconds(l.Time) > quarter * 3).length },
        { label: "Active Logs", val: logsWithSeconds.filter(l => l.seconds > quarter * 3).length }
      ]
    }
  ];

  const active = phases.find(p => p.id === activePhase) || phases[0];

  // Slice logs according to the active phase's time boundary
  const displayLogs = logsWithSeconds.filter(
    log => log.seconds >= active.logRange[0] && log.seconds < active.logRange[1]
  );

  return (
    <div className="flex flex-col lg:flex-row gap-8 mt-8">
      {/* LEFT COLUMN: PHASE SELECTION */}
      <div className="w-full lg:w-1/4 flex flex-col gap-4">
        {phases.map((phase) => {
          const isActive = activePhase === phase.id;
          return (
            <div 
              key={phase.id}
              onClick={() => setActivePhase(phase.id)}
              className={`border rounded-lg p-4 cursor-pointer transition-all flex items-center justify-between shadow-md
                ${isActive ? 'bg-zinc-900 border-yellow-600/50 scale-102' : 'bg-zinc-900/35 border-zinc-800 hover:bg-zinc-900/70'}`}
            >
              <div>
                <div className="text-[10px] font-mono text-zinc-500 mb-1 uppercase tracking-widest">{phase.title}</div>
                <div className={`font-orbitron font-bold text-xs ${isActive ? 'text-yellow-500 animate-pulse' : 'text-zinc-400'}`}>
                  {phase.subtitle}
                </div>
              </div>
              {isActive && <span className="text-yellow-500 font-bold font-mono">[ACTIVE]</span>}
            </div>
          );
        })}
      </div>

      {/* RIGHT COLUMN: PHASE DETAILS */}
      <div className="w-full lg:w-3/4">
        <div className="bg-zinc-900/50 backdrop-blur-md border border-zinc-800 rounded-lg p-6 sm:p-8 shadow-2xl">
          {/* Phase Badge Header */}
          <div className="flex items-center gap-3 mb-6">
            <span className="bg-zinc-800/80 text-zinc-400 font-mono text-[10px] px-3 py-1 rounded-full border border-zinc-700/60 uppercase tracking-widest">
              Stage {active.id + 1} of 4
            </span>
            <span className="text-yellow-500 font-bold font-orbitron text-xs tracking-wider uppercase">{active.title}</span>
          </div>
          
          <h2 className="text-xl font-orbitron font-black text-white mb-4 uppercase tracking-wide border-b border-zinc-800 pb-3">{active.subtitle}</h2>
          
          <p className="text-zinc-400 text-sm leading-relaxed mb-8 font-sans">
            {active.desc}
          </p>

          {/* Stats Grid */}
          <div className="mb-8">
            <h3 className="text-zinc-500 font-mono text-[10px] font-bold mb-4 uppercase tracking-wider">// Phase Analytics Summary</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {active.stats.map((stat, idx) => {
                let cardStyle = "bg-zinc-950/60 border-zinc-800/50 text-zinc-300";
                let labelColor = "text-zinc-500";
                let valColor = "text-white";

                if (stat.label === "Safety Cars" && stat.val > 0) {
                  cardStyle = "bg-yellow-950/20 border-yellow-900/30";
                  labelColor = "text-yellow-600";
                  valColor = "text-yellow-400";
                } else if (stat.label === "Penalties" && stat.val > 0) {
                  cardStyle = "bg-red-950/20 border-red-900/30";
                  labelColor = "text-red-500";
                  valColor = "text-red-400";
                } else if (stat.label === "Active Logs") {
                  cardStyle = "bg-blue-950/25 border-blue-900/30";
                  labelColor = "text-blue-400";
                  valColor = "text-blue-300";
                }

                return (
                  <div key={idx} className={`p-4 rounded-lg border flex flex-col justify-between ${cardStyle}`}>
                    <div className={`font-mono text-[9px] mb-2 uppercase font-bold tracking-widest ${labelColor}`}>
                      {stat.label}
                    </div>
                    <div className={`font-orbitron font-black text-2xl ${valColor}`}>
                      {stat.val}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Chronological Event Log Stream */}
          <div className="mt-8 pt-8 border-t border-zinc-800/60">
            <h3 className="text-zinc-500 font-mono text-[10px] font-bold mb-4 uppercase tracking-wider">// Chronological Control Log Stream</h3>
            <div className="h-[250px] overflow-y-auto pr-4 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
              {displayLogs.length > 0 ? (
                <div className="flex flex-col gap-3 font-mono text-[11px]">
                  {displayLogs.map((log, idx) => {
                    let logStyle = "bg-zinc-950/40 border-zinc-800 text-zinc-300";
                    let badge = "bg-zinc-800 text-zinc-400 border-zinc-700";
                    
                    if (log.Category === "Penalty") {
                      logStyle = "bg-red-950/10 border-red-950 text-red-200";
                      badge = "bg-red-900/40 text-red-400 border-red-800/50";
                    } else if (log.Category === "SafetyCar") {
                      logStyle = "bg-yellow-950/10 border-yellow-950 text-yellow-200";
                      badge = "bg-yellow-900/40 text-yellow-400 border-yellow-800/50";
                    } else if (log.Category === "Flag") {
                      logStyle = "bg-emerald-950/10 border-emerald-950 text-emerald-200";
                      badge = "bg-emerald-900/40 text-emerald-400 border-emerald-800/50";
                    } else if (log.Category === "Drs") {
                      logStyle = "bg-blue-950/10 border-blue-950 text-blue-200";
                      badge = "bg-blue-900/40 text-blue-400 border-blue-800/50";
                    }

                    return (
                      <div key={idx} className={`p-3 rounded border flex flex-col sm:flex-row items-start sm:items-center gap-3 ${logStyle}`}>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-zinc-500 font-bold select-none">{log.Time}</span>
                          <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border ${badge}`}>
                            {log.Category}
                          </span>
                        </div>
                        <div className="leading-relaxed break-words font-sans text-xs text-zinc-300">
                          {log.Message}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center font-mono text-[11px] text-zinc-600 bg-zinc-950/20 border border-dashed border-zinc-800/60 rounded">
                  NO RACE CONTROL BULLETINS LOGGED IN THIS TIMESTEP
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
