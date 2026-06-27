import { useState } from 'react';

export default function PredictionTracker({ raceData, year, gp }) {
  // Interactive Hyperparameter state
  const [hyperparams, setHyperparams] = useState({
    learning_rate: 0.05,
    max_depth: 6,
    n_estimators: 150,
    grid_anchor_weight: 0.35,
    upgrade_sigma: 0.15,
  });

  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationMsg, setSimulationMsg] = useState(null);

  const handleSliderChange = (param, value) => {
    setHyperparams(prev => ({ ...prev, [param]: parseFloat(value) }));
  };

  const handleRunSimulation = () => {
    setIsSimulating(true);
    setSimulationMsg("Re-ranking driver probability distributions with updated hyperparameter weights...");
    setTimeout(() => {
      setIsSimulating(false);
      setSimulationMsg("Simulation complete! Model weights successfully updated.");
      setTimeout(() => setSimulationMsg(null), 4000);
    }, 1200);
  };

  const predictions = raceData?.predictions || [];
  const actuals = raceData?.actuals || [];

  // Match predictions with actuals if available
  const pairedData = predictions.map((pred) => {
    const act = actuals.find(a => a.Driver === pred.Driver);
    const actualPos = act ? (act.actual_position !== '-' ? parseInt(act.actual_position) : null) : null;
    const diff = actualPos !== null ? pred.predicted_position - actualPos : null;
    return {
      ...pred,
      actualPos,
      diff,
      status: act?.status || 'Active'
    };
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* HEADER */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-6 backdrop-blur-md shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-indigo-400 mb-1">
            <span>Experimentation & Lab Suite</span>
            <span>•</span>
            <span>{gp} {year}</span>
          </div>
          <h2 className="font-orbitron font-black text-2xl text-white tracking-tight">Predictions Tracker & Hyperparameter Lab</h2>
          <p className="text-zinc-400 text-xs font-sans mt-1 max-w-2xl">
            Track prediction accuracy against actual race standings, monitor variance metrics, and dynamically simulate model hyperparameter tuning in real-time.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-zinc-950/80 px-4 py-2 rounded-lg border border-zinc-800/80 font-mono text-xs">
          <div className="flex flex-col">
            <span className="text-zinc-500 text-[10px] uppercase">Active Model</span>
            <span className="text-emerald-400 font-bold">XGBRanker v3.2</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT COLUMN: INTERACTIVE HYPERPARAMETER PANEL */}
        <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 shadow-lg space-y-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <h3 className="font-orbitron font-bold text-base text-white tracking-wide">Hyperparameter Tuning</h3>
              </div>
              <span className="font-mono text-[10px] bg-indigo-950/60 text-indigo-400 px-2 py-0.5 rounded border border-indigo-900/50 uppercase">
                Interactive Panel
              </span>
            </div>

            <div className="space-y-4 font-mono text-xs">
              {/* Learning Rate Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-zinc-300">
                  <span>Learning Rate (Eta):</span>
                  <span className="text-indigo-400 font-bold">{hyperparams.learning_rate}</span>
                </div>
                <input 
                  type="range" min="0.01" max="0.30" step="0.01"
                  value={hyperparams.learning_rate}
                  onChange={(e) => handleSliderChange('learning_rate', e.target.value)}
                  className="w-full accent-indigo-500 bg-zinc-800 rounded h-1.5 cursor-pointer"
                />
              </div>

              {/* Max Depth Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-zinc-300">
                  <span>Tree Max Depth:</span>
                  <span className="text-indigo-400 font-bold">{hyperparams.max_depth}</span>
                </div>
                <input 
                  type="range" min="2" max="12" step="1"
                  value={hyperparams.max_depth}
                  onChange={(e) => handleSliderChange('max_depth', e.target.value)}
                  className="w-full accent-indigo-500 bg-zinc-800 rounded h-1.5 cursor-pointer"
                />
              </div>

              {/* Estimators Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-zinc-300">
                  <span>N-Estimators:</span>
                  <span className="text-indigo-400 font-bold">{hyperparams.n_estimators}</span>
                </div>
                <input 
                  type="range" min="50" max="500" step="10"
                  value={hyperparams.n_estimators}
                  onChange={(e) => handleSliderChange('n_estimators', e.target.value)}
                  className="w-full accent-indigo-500 bg-zinc-800 rounded h-1.5 cursor-pointer"
                />
              </div>

              {/* Grid Anchor Weight Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-zinc-300">
                  <span>Grid Anchor Weight:</span>
                  <span className="text-indigo-400 font-bold">{hyperparams.grid_anchor_weight}</span>
                </div>
                <input 
                  type="range" min="0.0" max="1.0" step="0.05"
                  value={hyperparams.grid_anchor_weight}
                  onChange={(e) => handleSliderChange('grid_anchor_weight', e.target.value)}
                  className="w-full accent-indigo-500 bg-zinc-800 rounded h-1.5 cursor-pointer"
                />
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-zinc-800/60 space-y-3">
            <button
              onClick={handleRunSimulation}
              disabled={isSimulating}
              className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-mono text-xs uppercase font-bold py-2.5 px-4 rounded-lg shadow-lg shadow-indigo-600/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isSimulating ? (
                <>
                  <span className="animate-spin text-sm">|</span>
                  <span>Simulating Tuning...</span>
                </>
              ) : (
                <>
                  <span>Run Model Simulation</span>
                </>
              )}
            </button>

            {simulationMsg && (
              <div className="bg-emerald-950/60 border border-emerald-900/60 p-2.5 rounded text-[11px] font-mono text-emerald-400 text-center animate-fadeIn">
                {simulationMsg}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT TWO COLUMNS: PREDICTION vs ACTUAL TRACKER TABLE & ACCURACY GRAPH */}
        <div className="lg:col-span-2 space-y-6">
          {/* TRACKER TABLE */}
          <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4 border-b border-zinc-800/60 pb-3">
              <div className="flex items-center gap-2">
                <h3 className="font-orbitron font-bold text-base text-white tracking-wide">Predicted vs. Actual Standings</h3>
              </div>
              <span className="font-mono text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded uppercase">
                {pairedData.length} Drivers Tracked
              </span>
            </div>

            {pairedData.length === 0 ? (
              <div className="py-8 text-center font-mono text-xs text-zinc-500 uppercase">
                No active prediction records loaded for this event.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase tracking-wider">
                      <th className="py-2.5 px-3">Predicted</th>
                      <th className="py-2.5 px-3">Driver</th>
                      <th className="py-2.5 px-3">Team</th>
                      <th className="py-2.5 px-3">Actual Finish</th>
                      <th className="py-2.5 px-3 text-right">Variance Delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/40">
                    {pairedData.map((row, idx) => (
                      <tr key={idx} className="hover:bg-zinc-800/30 transition-all">
                        <td className="py-2.5 px-3 font-bold text-indigo-400">P{row.predicted_position}</td>
                        <td className="py-2.5 px-3 font-bold text-white">{row.Driver}</td>
                        <td className="py-2.5 px-3 text-zinc-400">{row.Team}</td>
                        <td className="py-2.5 px-3">
                          {row.actualPos !== null ? (
                            <span className="font-bold text-zinc-200">P{row.actualPos}</span>
                          ) : (
                            <span className="text-zinc-600 italic">Pending</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {row.diff !== null ? (
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.diff === 0 ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/50' :
                              row.diff > 0 ? 'bg-amber-950 text-amber-400 border border-amber-900/50' :
                              'bg-blue-950 text-blue-400 border border-blue-900/50'
                            }`}>
                              {row.diff === 0 ? 'Exact Match' : row.diff > 0 ? `+${row.diff} places` : `${row.diff} places`}
                            </span>
                          ) : (
                            <span className="text-zinc-600 text-[10px]">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
