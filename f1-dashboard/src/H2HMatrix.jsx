import { useState, useEffect } from 'react';

export default function H2HMatrix({ year, gp }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [driverA, setDriverA] = useState('');
  const [driverB, setDriverB] = useState('');
  
  const [hoveredRow, setHoveredRow] = useState(null);
  const [hoveredCol, setHoveredCol] = useState(null);
  const [showAllDrivers, setShowAllDrivers] = useState(false);

  useEffect(() => {
    if (!year || !gp) return;

    setLoading(true);
    setError(null);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    fetch(`${apiUrl}/api/probability/${year}/${encodeURIComponent(gp)}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Failed to load win probability data');
        }
        return res.json();
      })
      .then(json => {
        setData(json);
        if (json.drivers && json.drivers.length >= 2) {
          setDriverA(json.drivers[0].driver);
          setDriverB(json.drivers[1].driver);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load win probability:", err);
        setError(err.message);
        setLoading(false);
      });
  }, [year, gp]);

  if (loading) {
    return (
      <div className="h-[40vh] flex flex-col items-center justify-center font-mono text-zinc-400 gap-4">
        <div className="relative flex h-8 w-8">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-8 w-8 bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.8)]"></span>
        </div>
        <span className="text-xs uppercase tracking-widest animate-pulse">Running Bradley-Terry Logistic Calibration...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-950/20 border border-red-900/50 p-6 rounded-lg font-mono text-red-500 text-xs max-w-lg mx-auto flex flex-col gap-2">
        <h3 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2 text-red-500">
          Calibration Error
        </h3>
        <p className="text-zinc-300">{error}</p>
        <span className="text-[10px] text-zinc-500 border-t border-red-900/20 pt-2 uppercase">
          Ensure model cache is available on backend
        </span>
      </div>
    );
  }

  if (!data || !data.drivers || data.drivers.length === 0) return null;

  const allDrivers = data.drivers;
  const activeDrivers = showAllDrivers ? allDrivers : allDrivers.slice(0, 12);

  // Retrieve selected drivers objects
  const drAObj = allDrivers.find(d => d.driver === driverA);
  const drBObj = allDrivers.find(d => d.driver === driverB);

  // Calculate matchup probability
  let winProbA = 0.5;
  if (drAObj && drBObj) {
    const delta = drAObj.rank_score - drBObj.rank_score;
    // Logistic function (calibration constant c = 1.0)
    winProbA = 1 / (1 + Math.exp(-delta));
  }
  const winProbB = 1 - winProbA;

  // Function to calculate cell win probability
  const getWinProbability = (scoreA, scoreB) => {
    const delta = scoreA - scoreB;
    return 1 / (1 + Math.exp(-delta));
  };

  // Color gradient coding based on win probability
  const getCellColor = (prob) => {
    if (Math.abs(prob - 0.5) < 0.01) return 'bg-zinc-900 text-zinc-500 border-zinc-800/40';
    
    if (prob > 0.5) {
      const intensity = Math.round((prob - 0.5) * 2 * 9); // 0 to 9 index
      const bgColors = [
        'bg-emerald-950/10 text-emerald-600 border-zinc-850',
        'bg-emerald-950/20 text-emerald-500 border-zinc-850',
        'bg-emerald-950/30 text-emerald-400 border-zinc-850',
        'bg-emerald-950/40 text-emerald-400 border-zinc-850',
        'bg-emerald-950/50 text-emerald-300 border-emerald-900/20',
        'bg-emerald-950/60 text-emerald-300 border-emerald-900/30',
        'bg-emerald-900/30 text-emerald-200 border-emerald-900/40',
        'bg-emerald-900/45 text-emerald-200 border-emerald-900/50',
        'bg-emerald-900/60 text-emerald-100 border-emerald-900/60',
        'bg-emerald-600/80 text-white font-bold border-emerald-500/50'
      ];
      return bgColors[Math.min(9, intensity)];
    } else {
      const intensity = Math.round((0.5 - prob) * 2 * 9); // 0 to 9 index
      const bgColors = [
        'bg-red-950/10 text-red-650 border-zinc-850',
        'bg-red-950/25 text-red-500 border-zinc-850',
        'bg-red-950/35 text-red-400 border-zinc-850',
        'bg-red-950/45 text-red-400 border-zinc-850',
        'bg-red-950/55 text-red-300 border-red-900/20',
        'bg-red-950/65 text-red-355 border-red-900/30',
        'bg-red-900/30 text-red-200 border-red-900/40',
        'bg-red-900/45 text-red-200 border-red-900/50',
        'bg-red-900/60 text-red-100 border-red-900/60',
        'bg-red-600/80 text-white font-bold border-red-500/50'
      ];
      return bgColors[Math.min(9, intensity)];
    }
  };

  const handleCellClick = (rowDriver, colDriver) => {
    if (rowDriver !== colDriver) {
      setDriverA(rowDriver);
      setDriverB(colDriver);
      
      // Scroll smoothly to matchup card
      const element = document.getElementById("direct-matchup-card");
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <div className="w-full flex flex-col gap-8">
      {/* SECTION HEADER */}
      <div>
        <h2 className="text-xl font-bold uppercase tracking-wide border-l-4 border-blue-600 pl-3">
          Driver Head-to-Head Beat-Probability Matrix
        </h2>
        <p className="text-xs text-zinc-500 font-mono mt-1 uppercase tracking-widest">
          XGBRanker Bradley-Terry Calibrated Odds for {data.gp}
        </p>
      </div>

      {/* DIRECT MATCHUP SELECTOR CARD */}
      <div 
        id="direct-matchup-card" 
        className="relative bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 hover:border-zinc-700/80 transition-colors rounded-2xl p-6 shadow-2xl overflow-hidden flex flex-col gap-6"
      >
        {/* Glowing border accents */}
        <div className="absolute top-0 left-0 w-3 h-full bg-gradient-to-b from-blue-600 to-indigo-600" />
        <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-bl-full pointer-events-none" />

        <h3 className="font-orbitron text-xs font-bold text-zinc-400 uppercase tracking-widest border-b border-zinc-800/60 pb-3">
          Head-to-Head Matchup Simulator
        </h3>

        {/* SELECTORS ROW */}
        <div className="flex flex-col sm:flex-row items-center gap-6 justify-between">
          {/* Driver A Select */}
          <div className="flex flex-col gap-1.5 w-full sm:w-[45%]">
            <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">Driver A</label>
            <select
              value={driverA}
              onChange={(e) => setDriverA(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white font-mono font-bold text-sm focus:outline-none focus:border-blue-500 transition-colors cursor-pointer"
            >
              {allDrivers.map(d => (
                <option key={d.driver} value={d.driver} disabled={d.driver === driverB}>
                  P{d.position} - {d.driver} ({d.team})
                </option>
              ))}
            </select>
          </div>

          {/* VS Divider */}
          <div className="font-orbitron font-black text-lg text-zinc-700">VS</div>

          {/* Driver B Select */}
          <div className="flex flex-col gap-1.5 w-full sm:w-[45%]">
            <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">Driver B</label>
            <select
              value={driverB}
              onChange={(e) => setDriverB(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white font-mono font-bold text-sm focus:outline-none focus:border-blue-500 transition-colors cursor-pointer"
            >
              {allDrivers.map(d => (
                <option key={d.driver} value={d.driver} disabled={d.driver === driverA}>
                  P{d.position} - {d.driver} ({d.team})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* COMPARISON RESULTS GRAPHIC */}
        {drAObj && drBObj && (
          <div className="flex flex-col gap-5 mt-2 bg-zinc-950/55 border border-zinc-800/80 rounded-xl p-5">
            {/* Main Probability Display */}
            <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-center sm:text-left">
              <div className="flex flex-col">
                <span className="font-sans font-bold text-zinc-400 text-sm">Matchup Result Probability</span>
                <span className="font-orbitron text-lg font-black text-white mt-1 uppercase tracking-tight">
                  <strong className="text-blue-400">{driverA}</strong> is predicted to finish ahead of <strong className="text-indigo-400">{driverB}</strong>
                </span>
              </div>
              <div className="font-orbitron text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400 shadow-sm drop-shadow-[0_0_10px_rgba(99,102,241,0.2)] animate-pulse">
                {(winProbA * 100).toFixed(1)}%
              </div>
            </div>

            {/* Split Progress Bar */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between font-mono text-[9px] text-zinc-500 uppercase">
                <span>{driverA}: {(winProbA * 100).toFixed(1)}%</span>
                <span>{driverB}: {(winProbB * 100).toFixed(1)}%</span>
              </div>
              
              <div className="w-full bg-zinc-950 rounded-full h-3 border border-zinc-800/80 p-0.5 shadow-inner flex overflow-hidden">
                <div 
                  className="bg-blue-600 h-1.5 rounded-l-full transition-all duration-700 ease-out"
                  style={{ width: `${winProbA * 100}%` }}
                />
                <div 
                  className="bg-indigo-600 h-1.5 rounded-r-full transition-all duration-700 ease-out"
                  style={{ width: `${winProbB * 100}%` }}
                />
              </div>
            </div>

            {/* Micro Details */}
            <div className="grid grid-cols-2 gap-4 font-mono text-[10px] text-zinc-500 uppercase border-t border-zinc-900 pt-3">
              <div>
                Driver A score: <span className="text-zinc-300 font-bold">{drAObj.rank_score.toFixed(3)}</span>
              </div>
              <div className="text-right">
                Driver B score: <span className="text-zinc-300 font-bold">{drBObj.rank_score.toFixed(3)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* MATRIX TABLE CONTAINER */}
      <div className="bg-zinc-900/40 backdrop-blur-md border border-zinc-800/80 rounded-xl p-6 shadow-xl flex flex-col gap-5">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-zinc-800/60 pb-4">
          <div className="flex flex-col">
            <h3 className="font-orbitron text-sm font-bold text-white uppercase tracking-wider">
              Pairwise Probability Matrix
            </h3>
            <span className="text-[10px] text-zinc-500 font-mono mt-0.5 uppercase tracking-widest">
              Hover over cells to inspect, click to select in simulator
            </span>
          </div>

          {/* Toggle Driver Grid Count */}
          <button
            onClick={() => setShowAllDrivers(!showAllDrivers)}
            className="bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-white px-3 py-1.5 rounded font-mono text-[10px] font-bold uppercase tracking-wider transition-all"
          >
            {showAllDrivers ? "Show Top 12 (Compact)" : "Show All 22 (Full Grid)"}
          </button>
        </div>

        {/* MATRIX SCROLL BOX */}
        <div className="w-full overflow-x-auto custom-scrollbar border border-zinc-800/60 rounded-lg bg-zinc-950/20">
          <table className="min-w-max border-collapse font-mono text-[10px] text-center select-none w-full">
            <thead>
              <tr className="bg-zinc-950 border-b border-zinc-800">
                {/* Top-left corner spacer */}
                <th className="p-3 w-16 text-zinc-500 font-black uppercase text-left border-r border-zinc-800">
                  ROW BEATS
                </th>
                {activeDrivers.map((d, colIdx) => (
                  <th
                    key={d.driver}
                    onMouseEnter={() => setHoveredCol(colIdx)}
                    onMouseLeave={() => setHoveredCol(null)}
                    className={`p-3 w-12 font-bold uppercase transition-all ${
                      hoveredCol === colIdx ? 'bg-zinc-900/80 text-white font-extrabold shadow-inner' : 'text-zinc-400'
                    }`}
                  >
                    {d.driver}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeDrivers.map((rowDriver, rowIdx) => (
                <tr 
                  key={rowDriver.driver}
                  className={`border-b border-zinc-900 hover:bg-zinc-900/20 transition-all ${
                    hoveredRow === rowIdx ? 'bg-zinc-900/30' : ''
                  }`}
                >
                  {/* Row header */}
                  <td
                    onMouseEnter={() => setHoveredRow(rowIdx)}
                    onMouseLeave={() => setHoveredRow(null)}
                    className={`p-3 font-bold uppercase text-left border-r border-zinc-850 font-sans text-xs ${
                      hoveredRow === rowIdx ? 'text-white' : 'text-zinc-400'
                    }`}
                  >
                    {rowDriver.driver}
                  </td>
                  
                  {/* Pairwise Cells */}
                  {activeDrivers.map((colDriver, colIdx) => {
                    const isSelf = rowDriver.driver === colDriver.driver;
                    const p = isSelf ? 0.5 : getWinProbability(rowDriver.rank_score, colDriver.rank_score);
                    const cellColor = getCellColor(p);
                    const highlight = (hoveredRow === rowIdx || hoveredCol === colIdx) && !isSelf;

                    return (
                      <td
                        key={colDriver.driver}
                        onMouseEnter={() => {
                          setHoveredRow(rowIdx);
                          setHoveredCol(colIdx);
                        }}
                        onMouseLeave={() => {
                          setHoveredRow(null);
                          setHoveredCol(null);
                        }}
                        onClick={() => handleCellClick(rowDriver.driver, colDriver.driver)}
                        className={`p-3 w-12 transition-all cursor-pointer border-r border-zinc-900/50 ${cellColor} ${
                          highlight ? 'brightness-125' : ''
                        }`}
                        title={
                          isSelf 
                            ? `${rowDriver.driver} Matchup` 
                            : `Chance of ${rowDriver.driver} beating ${colDriver.driver}: ${(p * 100).toFixed(1)}%`
                        }
                      >
                        {isSelf ? "-" : `${Math.round(p * 100)}%`}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
