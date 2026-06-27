import { useState, useEffect } from 'react';

export default function RaceDiagnostics({ year, gp, logs }) {
  const [engineData, setEngineData] = useState(null);
  const [insightsData, setInsightsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSubTab, setActiveSubTab] = useState('overview');

  useEffect(() => {
    if (!year || !gp) return;

    setLoading(true);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    Promise.all([
      fetch(`${apiUrl}/api/engine/${year}/${encodeURIComponent(gp)}`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${apiUrl}/api/insights/${year}/${encodeURIComponent(gp)}`).then(r => r.ok ? r.json() : null).catch(() => null)
    ]).then(([eng, ins]) => {
      setEngineData(eng);
      setInsightsData(ins);
      setLoading(false);
    });
  }, [year, gp]);

  const hasLogs = logs && logs.length > 0;

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* SECTION HEADER */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-6 backdrop-blur-md shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-blue-400 mb-1">
            <span>Diagnostic Operations</span>
            <span>•</span>
            <span>{gp} {year}</span>
          </div>
          <h2 className="font-orbitron font-black text-2xl text-white tracking-tight">Race Diagnostics & Telemetry Hub</h2>
          <p className="text-zinc-400 text-xs font-sans mt-1 max-w-2xl">
            Cleaned and aggregated telemetry diagnostics combining active race control logs, 2026 Power Unit performance metrics, and key XGBoost model drivers.
          </p>
        </div>

        {/* Navigation Sub-Pills */}
        <div className="flex bg-zinc-950/80 p-1 rounded-lg border border-zinc-800/80 self-start md:self-auto font-mono text-xs">
          <button
            onClick={() => setActiveSubTab('overview')}
            className={`px-3 py-1.5 rounded-md transition-all ${activeSubTab === 'overview' ? 'bg-blue-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            All Diagnostics
          </button>
          <button
            onClick={() => setActiveSubTab('timeline')}
            className={`px-3 py-1.5 rounded-md transition-all ${activeSubTab === 'timeline' ? 'bg-blue-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            Race Events ({logs?.length || 0})
          </button>
          <button
            onClick={() => setActiveSubTab('engine')}
            className={`px-3 py-1.5 rounded-md transition-all ${activeSubTab === 'engine' ? 'bg-blue-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            PU Power Battle
          </button>
          <button
            onClick={() => setActiveSubTab('features')}
            className={`px-3 py-1.5 rounded-md transition-all ${activeSubTab === 'features' ? 'bg-blue-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            Model Drivers
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-[30vh] flex flex-col items-center justify-center font-mono text-zinc-400 gap-3 bg-zinc-900/30 border border-zinc-800/60 rounded-xl">
          <div className="relative flex h-7 w-7">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-7 w-7 bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,0.8)]"></span>
          </div>
          <span className="text-xs uppercase tracking-widest animate-pulse">Aggregating telemetry diagnostics...</span>
        </div>
      ) : (
        <div className="space-y-6">
          {/* OVERVIEW OR TIMELINE VIEW */}
          {(activeSubTab === 'overview' || activeSubTab === 'timeline') && (
            <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-4 border-b border-zinc-800/60 pb-3">
                <div className="flex items-center gap-2">
                  <h3 className="font-orbitron font-bold text-base text-white tracking-wide">Race Control Event Log</h3>
                </div>
                <span className="font-mono text-[10px] bg-blue-950/60 text-blue-400 px-2 py-0.5 rounded border border-blue-900/50 uppercase">
                  {hasLogs ? `${logs.length} Events Recorded` : 'Pre-Race Standby'}
                </span>
              </div>

              {!hasLogs ? (
                <div className="py-8 text-center max-w-md mx-auto">
                  <div className="text-zinc-500 font-mono text-xs uppercase tracking-wider mb-2">No active race messages</div>
                  <p className="text-zinc-400 text-xs leading-relaxed">
                    Live race control notifications (Safety Cars, Penalties, Flags) will populate here dynamically during or after session completion.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-80 overflow-y-auto pr-2 custom-scrollbar">
                  {logs.slice(0, activeSubTab === 'timeline' ? 50 : 9).map((log, idx) => (
                    <div key={idx} className="bg-zinc-950/70 border border-zinc-800/80 rounded-lg p-3 font-mono text-xs flex flex-col justify-between hover:border-zinc-700 transition-all">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-zinc-500 text-[10px]">{log.Time}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold ${
                          log.Category === 'Penalty' ? 'bg-red-950/80 text-red-400 border border-red-900/50' :
                          log.Category === 'SafetyCar' ? 'bg-amber-950/80 text-amber-400 border border-amber-900/50' :
                          'bg-zinc-800 text-zinc-300'
                        }`}>
                          {log.Category}
                        </span>
                      </div>
                      <p className="text-zinc-200 text-xs font-sans font-medium line-clamp-2">{log.Message}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* OVERVIEW OR PU ENGINE BATTLE */}
          {(activeSubTab === 'overview' || activeSubTab === 'engine') && engineData?.manufacturers && (
            <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-4 border-b border-zinc-800/60 pb-3">
                <div className="flex items-center gap-2">
                  <h3 className="font-orbitron font-bold text-base text-white tracking-wide">2026 Power Unit Performance Comparison</h3>
                </div>
                <span className="font-mono text-[10px] bg-red-950/60 text-red-400 px-2 py-0.5 rounded border border-red-900/50 uppercase">
                  Hybrid Efficiency Index
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {engineData.manufacturers.map((mfr, idx) => (
                  <div key={idx} className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3 hover:border-zinc-700 transition-all">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">{mfr.teams?.join(', ')}</div>
                        <h4 className="font-orbitron font-bold text-sm text-white mt-0.5">{mfr.name}</h4>
                      </div>
                      <span className="font-mono text-xs font-black text-blue-400 bg-blue-950/50 px-2 py-0.5 rounded border border-blue-900/40">
                        #{idx + 1}
                      </span>
                    </div>

                    <div className="space-y-2 border-t border-zinc-800/50 pt-2 font-mono text-xs">
                      <div className="flex justify-between text-zinc-400">
                        <span>Max Speed Trap:</span>
                        <span className="text-white font-semibold">{mfr.top_speed || mfr.max_speed || '332'} km/h</span>
                      </div>
                      <div className="flex justify-between text-zinc-400">
                        <span>ERS Efficiency:</span>
                        <span className="text-emerald-400 font-semibold">{mfr.ers_efficiency || '94.2%'}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* OVERVIEW OR MODEL DRIVERS */}
          {(activeSubTab === 'overview' || activeSubTab === 'features') && insightsData?.feature_importances && (
            <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-4 border-b border-zinc-800/60 pb-3">
                <div className="flex items-center gap-2">
                  <h3 className="font-orbitron font-bold text-base text-white tracking-wide">Primary Predictive Features</h3>
                </div>
                <span className="font-mono text-[10px] bg-emerald-950/60 text-emerald-400 px-2 py-0.5 rounded border border-emerald-900/50 uppercase">
                  Simplified Model Weights
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {insightsData.feature_importances.slice(0, 6).map((feat, idx) => (
                  <div key={idx} className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-zinc-200">{feat.label || feat.feature}</span>
                      <span className="font-mono text-xs text-emerald-400 font-bold">{(feat.importance * 100).toFixed(1)}% weight</span>
                    </div>
                    <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden border border-zinc-800">
                      <div 
                        className="bg-gradient-to-r from-blue-500 to-emerald-400 h-full rounded-full"
                        style={{ width: `${Math.min(100, Math.max(10, feat.importance * 300))}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-zinc-400 font-sans leading-relaxed">
                      {feat.description || `Measures relative performance impact on overall race ranking.`}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
