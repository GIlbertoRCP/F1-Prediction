import { useState, useEffect } from 'react';

export default function MonteCarlo({ year, gp }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Simulation parameters
  const [simCount, setSimCount] = useState(5000);
  const [weather, setWeather] = useState('dry'); // dry, damp, wet
  const [globalDnfRate, setGlobalDnfRate] = useState(8); // in %
  const [gridWeight, setGridWeight] = useState(0.35); // weight of starting grid (0 to 1)
  const [safetyCarFactor, setSafetyCarFactor] = useState('med'); // none, low, med, high

  // Starting grid overrides
  const [startingGrid, setStartingGrid] = useState([]);
  const [autoDnfs, setAutoDnfs] = useState({}); // driver -> boolean

  // Results state
  const [simResults, setSimResults] = useState(null);
  const [selectedDriver, setSelectedDriver] = useState('');
  const [running, setRunning] = useState(false);
  const [simProgress, setSimProgress] = useState(0);

  // Load baseline drivers list and scores
  useEffect(() => {
    if (!year || !gp) return;

    setLoading(true);
    setError(null);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    fetch(`${apiUrl}/api/probability/${year}/${encodeURIComponent(gp)}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Failed to load starting data for Monte Carlo');
        }
        return res.json();
      })
      .then(json => {
        setData(json);
        // Initialize starting grid
        // Sort by grid_position if available, otherwise by predicted position
        const sortedGrid = [...json.drivers].sort((a, b) => {
          const posA = a.grid_position !== null ? a.grid_position : a.position;
          const posB = b.grid_position !== null ? b.grid_position : b.position;
          return posA - posB;
        }).map((d, index) => ({
          ...d,
          grid_pos: index + 1
        }));

        setStartingGrid(sortedGrid);
        if (sortedGrid.length > 0) {
          setSelectedDriver(sortedGrid[0].driver);
        }
        setLoading(false);
        setSimResults(null);
      })
      .catch(err => {
        console.error("Failed to load starting grid:", err);
        setError(err.message);
        setLoading(false);
      });
  }, [year, gp]);

  // Box-Muller transform for normal distribution
  const randomNormal = () => {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
  };

  // Re-order grid helpers
  const moveDriver = (index, direction) => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === startingGrid.length - 1) return;

    const newGrid = [...startingGrid];
    const swapTarget = direction === 'up' ? index - 1 : index + 1;
    
    // Swap elements
    const temp = newGrid[index];
    newGrid[index] = newGrid[swapTarget];
    newGrid[swapTarget] = temp;

    // Re-index grid_pos
    const finalGrid = newGrid.map((d, i) => ({
      ...d,
      grid_pos: i + 1
    }));

    setStartingGrid(finalGrid);
  };

  const toggleAutoDnf = (driver) => {
    setAutoDnfs(prev => ({
      ...prev,
      [driver]: !prev[driver]
    }));
  };

  // Run Monte Carlo Simulation
  const runSimulation = () => {
    if (startingGrid.length === 0) return;
    setRunning(true);
    setSimProgress(10);

    // Minor delay to show loading state cleanly
    setTimeout(() => {
      // Pace standard deviation based on weather
      let paceStd = 0.35;
      let weatherDnfModifier = 0.0;
      if (weather === 'damp') {
        paceStd = 0.60;
        weatherDnfModifier = 0.04;
      } else if (weather === 'wet') {
        paceStd = 0.95;
        weatherDnfModifier = 0.12;
      }

      // Base DNF probability
      const baseDnfProb = (globalDnfRate / 100) + weatherDnfModifier;

      // Safety car position shuffling probability
      let scShuffleChance = 0.02; // per driver pair
      if (safetyCarFactor === 'none') scShuffleChance = 0.0;
      if (safetyCarFactor === 'low') scShuffleChance = 0.01;
      if (safetyCarFactor === 'high') scShuffleChance = 0.05;

      // Initialize stats counters
      const stats = {};
      startingGrid.forEach(d => {
        stats[d.driver] = {
          driver: d.driver,
          team: d.team,
          originalGrid: d.grid_pos,
          rank_score: d.rank_score,
          wins: 0,
          podiums: 0,
          top10: 0,
          dnfs: 0,
          finishPositions: Array(23).fill(0), // 1-indexed (1 to 22)
          totalFinishPos: 0
        };
      });

      // Simulation Loop
      for (let t = 0; t < simCount; t++) {
        // Compute scores for this trial
        const trialDrivers = startingGrid.map(d => {
          const isForcedDnf = autoDnfs[d.driver] || false;
          let hasDnf = isForcedDnf;

          // DNF roll
          if (!hasDnf && Math.random() < baseDnfProb) {
            hasDnf = true;
          }

          // Generate simulated pace score
          // Formula: raw_score + noise - (grid_weight * grid_index)
          // Higher score is better.
          const noise = randomNormal() * paceStd;
          
          // Grid position penalty offset (1-indexed grid position)
          const gridOffset = gridWeight * (d.grid_pos - 1);
          let simScore = d.rank_score + noise - gridOffset;

          // If DNF, assign extremely low score
          if (hasDnf) {
            // Rank DNF drivers loosely by their qualifying position to simulate when they crashed
            simScore = -1000.0 - (d.grid_pos * 0.1) - (Math.random() * 5);
          }

          return {
            driver: d.driver,
            simScore,
            isDnf: hasDnf
          };
        });

        // Safety Car simulation (adjacent position swapping)
        if (scShuffleChance > 0) {
          for (let i = 0; i < trialDrivers.length - 1; i++) {
            if (!trialDrivers[i].isDnf && !trialDrivers[i + 1].isDnf) {
              if (Math.random() < scShuffleChance) {
                const temp = trialDrivers[i];
                trialDrivers[i] = trialDrivers[i + 1];
                trialDrivers[i + 1] = temp;
              }
            }
          }
        }

        // Sort by simulated score descending (higher is better)
        trialDrivers.sort((a, b) => b.simScore - a.simScore);

        // Record finish positions
        trialDrivers.forEach((td, finishIndex) => {
          const pos = finishIndex + 1; // 1-indexed finish position
          const dStat = stats[td.driver];

          dStat.finishPositions[pos] += 1;
          if (td.isDnf) {
            dStat.dnfs += 1;
          } else {
            dStat.totalFinishPos += pos;
          }

          if (pos === 1) dStat.wins += 1;
          if (pos <= 3) dStat.podiums += 1;
          if (pos <= 10) dStat.top10 += 1;
        });
      }

      // Compile final results percentages
      const finalResults = Object.values(stats).map(d => {
        // Average finish position (excluding DNFs from normal average calculation)
        const classifiedCount = simCount - d.dnfs;
        const meanFinish = classifiedCount > 0 ? (d.totalFinishPos / classifiedCount) : 22.0;

        return {
          driver: d.driver,
          team: d.team,
          originalGrid: d.originalGrid,
          rank_score: d.rank_score,
          winProb: (d.wins / simCount) * 100,
          podiumProb: (d.podiums / simCount) * 100,
          top10Prob: (d.top10 / simCount) * 100,
          dnfProb: (d.dnfs / simCount) * 100,
          meanFinish,
          positions: d.finishPositions.map(count => (count / simCount) * 100) // index 1 to 22
        };
      });

      // Sort by win percentage and mean finish position
      finalResults.sort((a, b) => b.winProb - a.winProb || a.meanFinish - b.meanFinish);

      setSimResults(finalResults);
      setSimProgress(100);
      setRunning(false);
    }, 400);
  };

  // Run automatically when starting grid is ready
  useEffect(() => {
    if (startingGrid.length > 0 && !simResults) {
      runSimulation();
    }
  }, [startingGrid]);

  if (loading) {
    return (
      <div className="h-[40vh] flex flex-col items-center justify-center font-mono text-zinc-400 gap-4">
        <div className="relative flex h-8 w-8">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-8 w-8 bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)]"></span>
        </div>
        <span className="text-xs uppercase tracking-widest animate-pulse">Assembling Starting Grid & Weights...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-950/20 border border-red-900/50 p-6 rounded-lg font-mono text-red-500 text-xs max-w-lg mx-auto flex flex-col gap-2">
        <h3 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2 text-red-500">
          Simulation Initialization Error
        </h3>
        <p className="text-zinc-300">{error}</p>
        <span className="text-[10px] text-zinc-500 border-t border-red-900/20 pt-2 uppercase">
          Ensure model cache is available on backend
        </span>
      </div>
    );
  }

  const selectedDriverData = simResults?.find(d => d.driver === selectedDriver);

  // Group constructor statistics
  const teamStats = {};
  if (simResults) {
    simResults.forEach(d => {
      if (!teamStats[d.team]) {
        teamStats[d.team] = { team: d.team, winProb: 0, podiumProb: 0 };
      }
      teamStats[d.team].winProb += d.winProb;
      teamStats[d.team].podiumProb = Math.max(teamStats[d.team].podiumProb, d.podiumProb);
    });
  }
  const rankedTeams = Object.values(teamStats).sort((a, b) => b.winProb - a.winProb);

  return (
    <div className="w-full flex flex-col gap-8">
      {/* SECTION HEADER */}
      <div>
        <h2 className="text-xl font-bold uppercase tracking-wide border-l-4 border-blue-600 pl-3">
          Stochastic Monte Carlo Race Simulator
        </h2>
        <p className="text-xs text-zinc-500 font-mono mt-1 uppercase tracking-widest">
          Probabilistic Race Modeler for {data?.gp}
        </p>
      </div>

      {/* PARAMETERS AND GRID OVERRIDES CARD */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SIMULATOR CONFIGURATION */}
        <div className="bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-5">
          <h3 className="font-orbitron text-xs font-bold text-blue-400 uppercase tracking-widest border-b border-zinc-800/60 pb-3">
            Simulation Parameters
          </h3>

          {/* SIM ITERATIONS */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between font-mono text-[10px] text-zinc-400 uppercase">
              <span>Runs Count</span>
              <span className="text-blue-400 font-bold">{simCount.toLocaleString()} trials</span>
            </div>
            <input
              type="range"
              min="1000"
              max="20000"
              step="1000"
              value={simCount}
              onChange={(e) => setSimCount(parseInt(e.target.value))}
              className="w-full accent-blue-500 bg-zinc-950 h-1.5 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* WEATHER */}
          <div className="flex flex-col gap-2">
            <span className="font-mono text-[10px] text-zinc-400 uppercase">Weather / Track State</span>
            <div className="grid grid-cols-3 gap-2 font-mono text-[10px] font-bold">
              {['dry', 'damp', 'wet'].map(w => (
                <button
                  key={w}
                  onClick={() => setWeather(w)}
                  className={`py-2 rounded border uppercase tracking-wider transition-all ${
                    weather === w
                      ? 'bg-blue-600 border-blue-500 text-white shadow-md shadow-blue-500/20'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700'
                  }`}
                >
                  {w === 'dry' ? 'Dry' : w === 'damp' ? 'Damp' : 'Wet'}
                </button>
              ))}
            </div>
          </div>

          {/* DNF RATE */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between font-mono text-[10px] text-zinc-400 uppercase">
              <span>Base DNF Rate</span>
              <span className="text-blue-400 font-bold">{globalDnfRate}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="30"
              step="1"
              value={globalDnfRate}
              onChange={(e) => setGlobalDnfRate(parseInt(e.target.value))}
              className="w-full accent-blue-500 bg-zinc-950 h-1.5 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* GRID INFLUENCE */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between font-mono text-[10px] text-zinc-400 uppercase">
              <span>Grid Influence Weight</span>
              <span className="text-blue-400 font-bold">{(gridWeight * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="0.8"
              step="0.05"
              value={gridWeight}
              onChange={(e) => setGridWeight(parseFloat(e.target.value))}
              className="w-full accent-blue-500 bg-zinc-950 h-1.5 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* SAFETY CAR */}
          <div className="flex flex-col gap-2">
            <span className="font-mono text-[10px] text-zinc-400 uppercase">Safety Car Risk</span>
            <div className="grid grid-cols-4 gap-1.5 font-mono text-[9px] font-bold">
              {['none', 'low', 'med', 'high'].map(sc => (
                <button
                  key={sc}
                  onClick={() => setSafetyCarFactor(sc)}
                  className={`py-2 rounded border uppercase transition-all ${
                    safetyCarFactor === sc
                      ? 'bg-blue-600 border-blue-500 text-white shadow-sm'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-white'
                  }`}
                >
                  {sc}
                </button>
              ))}
            </div>
          </div>

          {/* TRIGGER SIMULATION BUTTON */}
          <button
            onClick={runSimulation}
            disabled={running}
            className="w-full mt-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white py-3 px-4 rounded-xl font-orbitron font-extrabold uppercase text-xs tracking-wider transition-all shadow-[0_0_20px_rgba(99,102,241,0.3)] disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer border border-blue-400/20"
          >
            {running ? (
              <>
                <span className="animate-spin h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full" />
                Running Trials... {simProgress}%
              </>
            ) : (
              <>
                RUN MONTE CARLO SIMULATION
              </>
            )}
          </button>
        </div>

        {/* INTERACTIVE STARTING GRID OVERRIDES */}
        <div className="lg:col-span-2 bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 overflow-hidden h-[410px]">
          <div className="border-b border-zinc-800/60 pb-3 flex justify-between items-center">
            <h3 className="font-orbitron text-xs font-bold text-blue-400 uppercase tracking-widest">
              Edit Grid & Overrides
            </h3>
            <span className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider">
              Swap starting rows & toggle forced DNFs
            </span>
          </div>

          {/* GRID SCROLL BOX */}
          <div className="flex-grow overflow-y-auto custom-scrollbar flex flex-col gap-1.5 pr-1 font-mono text-xs">
            {startingGrid.map((d, index) => {
              const isAutoDnf = autoDnfs[d.driver] || false;
              return (
                <div
                  key={d.driver}
                  className={`flex items-center justify-between p-2 rounded-lg border transition-all ${
                    isAutoDnf 
                      ? 'bg-red-950/20 border-red-900/40 text-red-400' 
                      : 'bg-zinc-950/80 border-zinc-800/80 text-zinc-200 hover:border-zinc-700/60'
                  }`}
                >
                  <div className="flex items-center gap-3 w-[50%]">
                    {/* Position Badge */}
                    <span className="w-6 h-6 rounded bg-zinc-900 border border-zinc-800 text-[10px] font-bold flex items-center justify-center text-zinc-400">
                      P{d.grid_pos}
                    </span>
                    <div className="flex flex-col">
                      <span className="font-bold text-white text-xs">{d.driver}</span>
                      <span className="text-[8px] text-zinc-500 uppercase">{d.team}</span>
                    </div>
                  </div>

                  {/* Actions Right */}
                  <div className="flex items-center gap-4">
                    {/* Up / Down Swap buttons */}
                    <div className="flex gap-1">
                      <button
                        onClick={() => moveDriver(index, 'up')}
                        disabled={index === 0}
                        className="w-6 h-6 border border-zinc-800 hover:border-zinc-700 rounded bg-zinc-900/60 flex items-center justify-center text-[8px] text-zinc-400 hover:text-white cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        ▲
                      </button>
                      <button
                        onClick={() => moveDriver(index, 'down')}
                        disabled={index === startingGrid.length - 1}
                        className="w-6 h-6 border border-zinc-800 hover:border-zinc-700 rounded bg-zinc-900/60 flex items-center justify-center text-[8px] text-zinc-400 hover:text-white cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        ▼
                      </button>
                    </div>

                    <div className="h-4 w-[1px] bg-zinc-850" />

                    {/* Auto-DNF Toggle */}
                    <label className="flex items-center gap-1.5 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={isAutoDnf}
                        onChange={() => toggleAutoDnf(d.driver)}
                        className="w-3.5 h-3.5 rounded bg-zinc-900 border-zinc-800 accent-red-600 focus:outline-none"
                      />
                      <span className="text-[9px] uppercase tracking-wider text-zinc-400">DNF</span>
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* RESULTS SECTIONS */}
      {simResults && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* SIMULATION LEADERBOARD */}
          <div className="lg:col-span-2 bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-4">
            <h3 className="font-orbitron text-xs font-bold text-white uppercase tracking-widest border-b border-zinc-800/60 pb-3">
              Simulated Finish Probabilities
            </h3>

            <div className="w-full overflow-x-auto custom-scrollbar border border-zinc-800/50 rounded-lg">
              <table className="min-w-max border-collapse font-mono text-[10px] text-center select-none w-full">
                <thead>
                  <tr className="bg-zinc-950 border-b border-zinc-800 text-zinc-400">
                    <th className="p-3 text-left">DRIVER</th>
                    <th className="p-3">GRID</th>
                    <th className="p-3">WIN %</th>
                    <th className="p-3">PODIUM %</th>
                    <th className="p-3">TOP 10 %</th>
                    <th className="p-3">DNF %</th>
                    <th className="p-3">MEAN FINISH</th>
                  </tr>
                </thead>
                <tbody>
                  {simResults.map(d => {
                    const isSelected = selectedDriver === d.driver;
                    return (
                      <tr
                        key={d.driver}
                        onClick={() => setSelectedDriver(d.driver)}
                        className={`border-b border-zinc-900/60 hover:bg-zinc-800/40 transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-950/20 border-blue-900/40' : ''
                        }`}
                      >
                        {/* Driver Info */}
                        <td className="p-3 text-left flex items-center gap-2">
                          <span className={`w-1.5 h-6 rounded ${
                            isSelected ? 'bg-blue-500' : 'bg-transparent'
                          }`} />
                          <div className="flex flex-col">
                            <span className="font-bold text-zinc-100">{d.driver}</span>
                            <span className="text-[8px] text-zinc-500 uppercase">{d.team}</span>
                          </div>
                        </td>

                        {/* Starting Grid */}
                        <td className="p-3 text-zinc-400 font-bold">P{d.originalGrid}</td>

                        {/* Win Prob */}
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded font-bold ${
                            d.winProb > 25 ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/60' :
                            d.winProb > 5 ? 'bg-blue-950/40 text-blue-400' : 'text-zinc-500'
                          }`}>
                            {d.winProb.toFixed(1)}%
                          </span>
                        </td>

                        {/* Podium Prob */}
                        <td className="p-3">
                          <div className="flex items-center gap-1.5 justify-center">
                            <span className="w-10 text-right">{d.podiumProb.toFixed(1)}%</span>
                            <div className="w-12 bg-zinc-950 h-1.5 rounded-full overflow-hidden p-0.5 border border-zinc-900">
                              <div
                                className="bg-gradient-to-r from-yellow-500 to-amber-500 h-0.5 rounded-full"
                                style={{ width: `${d.podiumProb}%` }}
                              />
                            </div>
                          </div>
                        </td>

                        {/* Top 10 Prob */}
                        <td className="p-3">
                          <div className="flex items-center gap-1.5 justify-center">
                            <span className="w-10 text-right">{d.top10Prob.toFixed(1)}%</span>
                            <div className="w-12 bg-zinc-950 h-1.5 rounded-full overflow-hidden p-0.5 border border-zinc-900">
                              <div
                                className="bg-blue-500 h-0.5 rounded-full"
                                style={{ width: `${d.top10Prob}%` }}
                              />
                            </div>
                          </div>
                        </td>

                        {/* DNF Prob */}
                        <td className="p-3 text-zinc-500">
                          <span className={d.dnfProb > 20 ? 'text-red-400 font-bold' : ''}>
                            {d.dnfProb.toFixed(1)}%
                          </span>
                        </td>

                        {/* Mean Finish */}
                        <td className="p-3 font-bold text-zinc-300">
                          P{d.meanFinish.toFixed(1)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* VISUALIZER SIDEBAR */}
          <div className="flex flex-col gap-6">
            {/* FINISHING POSITION HISTOGRAM */}
            {selectedDriverData && (
              <div className="bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-4">
                <div className="border-b border-zinc-800/60 pb-3">
                  <h3 className="font-orbitron text-xs font-bold text-white uppercase tracking-widest">
                    Finish Distribution: {selectedDriver}
                  </h3>
                  <span className="text-[8px] text-zinc-500 font-mono uppercase tracking-wider">
                    Probability per position (P1 to P22)
                  </span>
                </div>

                {/* SVG HISTOGRAM CHART */}
                <div className="w-full h-[220px] bg-zinc-950/50 rounded-xl p-3 border border-zinc-900 flex flex-col justify-end">
                  <div className="h-full w-full flex items-end gap-1 relative pt-4">
                    {selectedDriverData.positions.slice(1, 23).map((prob, idx) => {
                      const pos = idx + 1;
                      const maxProb = Math.max(...selectedDriverData.positions.slice(1, 23), 1);
                      const heightPercent = (prob / maxProb) * 90; // scale to fit nicely
                      
                      return (
                        <div
                          key={pos}
                          className="flex-grow flex flex-col items-center group relative h-full justify-end cursor-pointer"
                          title={`P${pos}: ${prob.toFixed(1)}%`}
                        >
                          {/* Tooltip on hover */}
                          <div className="absolute bottom-full mb-1 bg-zinc-900 border border-zinc-800 text-white font-mono text-[8px] rounded px-1 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20">
                            {prob.toFixed(1)}%
                          </div>

                          {/* Bar */}
                          <div
                            className={`w-full rounded-t-sm transition-all duration-300 ${
                              pos === 1 ? 'bg-gradient-to-t from-yellow-600 to-yellow-400 shadow-[0_0_8px_rgba(234,179,8,0.3)]' :
                              pos <= 3 ? 'bg-gradient-to-t from-indigo-600 to-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.3)]' :
                              pos <= 10 ? 'bg-gradient-to-t from-blue-600 to-blue-400' : 'bg-zinc-800 group-hover:bg-zinc-700'
                            }`}
                            style={{ height: `${heightPercent}%`, minHeight: prob > 0 ? '1px' : '0' }}
                          />

                          {/* X-axis Label */}
                          <span className="text-[7px] text-zinc-500 font-mono mt-1 select-none">
                            {pos === 1 || pos === 5 || pos === 10 || pos === 15 || pos === 22 ? pos : ''}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 font-mono text-[9px] text-zinc-500 uppercase border-t border-zinc-900 pt-3">
                  <div>
                    Median position: <span className="text-zinc-200 font-bold">P{selectedDriverData.meanFinish.toFixed(0)}</span>
                  </div>
                  <div className="text-right">
                    Qualifying grid: <span className="text-zinc-200 font-bold">P{selectedDriverData.originalGrid}</span>
                  </div>
                </div>
              </div>
            )}

            {/* TEAM PROBABILITY TOTALS */}
            <div className="bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-6 shadow-2xl flex flex-col gap-4">
              <h3 className="font-orbitron text-xs font-bold text-white uppercase tracking-widest border-b border-zinc-800/60 pb-3">
                Team Win Probability
              </h3>

              <div className="flex flex-col gap-2.5 font-mono text-[10px]">
                {rankedTeams.slice(0, 6).map((t, idx) => (
                  <div key={t.team} className="flex flex-col gap-1">
                    <div className="flex justify-between uppercase">
                      <span className="text-zinc-300 font-bold">{idx + 1}. {t.team}</span>
                      <span className="text-blue-400 font-bold">{t.winProb.toFixed(1)}% win chance</span>
                    </div>
                    <div className="w-full bg-zinc-950 h-1.5 rounded-full overflow-hidden p-0.5 border border-zinc-900">
                      <div
                        className="bg-blue-600 h-0.5 rounded-full"
                        style={{ width: `${Math.min(t.winProb, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
