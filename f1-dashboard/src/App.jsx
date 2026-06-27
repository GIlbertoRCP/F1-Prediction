import { useState, useEffect } from 'react';
import AeroMap from './AeroMap';
import DataGrid from './DataGrid';
import RaceDiagnostics from './RaceDiagnostics';
import PredictionTracker from './PredictionTracker';
import H2H from './H2H';
import H2HMatrix from './H2HMatrix';
import MonteCarlo from './MonteCarlo';
import ErrorBoundary from './ErrorBoundary';

function App() {
  const [schedule, setSchedule] = useState(null);
  const [selectedYear, setSelectedYear] = useState('2026');
  const [selectedGp, setSelectedGp] = useState('Miami');
  
  const [raceData, setRaceData] = useState(null);
  const [loadingData, setLoadingData] = useState(true);
  const [activeTab, setActiveTab] = useState('grid');
  const [statusMessage, setStatusMessage] = useState('Initializing telemetries...');
  const [progress, setProgress] = useState({ status: 'idle', message: 'Ready', percent: 0 });
  const [simulatedPercent, setSimulatedPercent] = useState(0);

  // 1. Fetch available races and seasons schedule
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    setStatusMessage('Loading FIA Calendar...');
    fetch(`${apiUrl}/api/races`)
      .then(res => res.json())
      .then(json => {
        setSchedule(json);
        if (json.races && json.races['2026']) {
          setSelectedYear('2026');
          const miami = json.races['2026'].find(g => g.gp.toLowerCase().includes('miami'));
          if (miami) {
            setSelectedGp(miami.gp);
          } else if (json.races['2026'].length > 0) {
            setSelectedGp(json.races['2026'][0].gp);
          }
        }
      })
      .catch(err => {
        console.error("Failed to fetch calendar:", err);
      });
  }, []);

  const handleYearChange = (newYear) => {
    setSelectedYear(newYear);
    if (schedule && schedule.races && schedule.races[newYear] && schedule.races[newYear].length > 0) {
      const matching = schedule.races[newYear].find(g => g.gp.toLowerCase().includes(selectedGp.toLowerCase()) || selectedGp.toLowerCase().includes(g.gp.toLowerCase()));
      if (matching) {
        setSelectedGp(matching.gp);
      } else {
        setSelectedGp(schedule.races[newYear][0].gp);
      }
    }
  };

  // 2. Fetch data for selected GP and Year
  useEffect(() => {
    if (!selectedYear || !selectedGp) return;

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    setLoadingData(true);
    setStatusMessage(`Training XGBRanker on ${selectedGp} context...`);
    
    fetch(`${apiUrl}/api/race/${selectedYear}/${encodeURIComponent(selectedGp)}`)
      .then(res => res.json())
      .then(json => {
        if (json.detail) {
          console.error("Backend Error:", json.detail);
          setRaceData({ error: json.detail });
        } else {
          setRaceData(json);
        }
        setLoadingData(false);
      })
      .catch(err => {
        console.error("Failed to fetch race predictions:", err);
        setRaceData({ error: "Failed to connect to predictive pipeline. Please ensure the backend is running." });
        setLoadingData(false);
      });
  }, [selectedYear, selectedGp]);

  // 3. Poll progress when loadingData is true
  useEffect(() => {
    if (!loadingData) {
      setProgress({ status: 'idle', message: 'Ready', percent: 0 });
      return;
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    const fetchProgress = () => {
      fetch(`${apiUrl}/api/progress`)
        .then(res => res.json())
        .then(json => {
          if (json && typeof json.percent === 'number') {
            setProgress(json);
          }
        })
        .catch(err => {
          console.error("Failed to fetch progress:", err);
        });
    };

    fetchProgress();
    const interval = setInterval(fetchProgress, 800);
    return () => clearInterval(interval);
  }, [loadingData]);

  // 4. Simulated progress for smooth UI updates
  useEffect(() => {
    if (!loadingData) {
      setSimulatedPercent(0);
      return;
    }

    setSimulatedPercent(5);
    const interval = setInterval(() => {
      setSimulatedPercent(prev => {
        if (prev < 15) return prev + 2;
        else if (prev < 80) return prev + (Math.random() > 0.6 ? 1 : 0);
        else if (prev < 95) return prev + 1;
        else return 95;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [loadingData]);

  const availableGps = schedule && schedule.races ? schedule.races[selectedYear] || [] : [];
  const activePercent = Math.max(progress.percent, simulatedPercent);

  let displayMessage = statusMessage;
  if (activePercent > 0) {
    if (progress.message && progress.message !== 'Ready' && progress.message !== 'System ready') {
      displayMessage = progress.message;
    } else {
      if (activePercent < 15) displayMessage = `Initializing neural model for ${selectedGp}...`;
      else if (activePercent < 50) displayMessage = `Downloading telemetry & sector data for ${selectedGp}...`;
      else if (activePercent < 80) displayMessage = `Extracting fuel-corrected pace, compound averages & ERS metrics...`;
      else if (activePercent < 90) displayMessage = `Fitting XGBoost pairwise ranking model on historical race context...`;
      else if (activePercent < 100) displayMessage = `Generating stochastic outcome probabilities...`;
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-red-500 selection:text-white">
      {/* HEADER BAR */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/80 backdrop-blur-md px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 sticky top-0 z-50 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 bg-gradient-to-tr from-red-600 to-red-500 rounded-lg flex items-center justify-center font-orbitron font-black text-white text-lg shadow-md shadow-red-600/30">
            F1
          </div>
          <div>
            <h1 className="font-orbitron font-black text-xl tracking-wider text-white flex items-center gap-2">
              ORACLE <span className="text-xs font-mono font-normal bg-red-950/80 text-red-400 px-2 py-0.5 rounded border border-red-900/50 uppercase">2026 Regs</span>
            </h1>
            <p className="text-[10px] font-mono text-zinc-400 uppercase tracking-widest">Pairwise XGBRanker Telemetry Analytics</p>
          </div>
        </div>

        {/* GP & YEAR SELECTORS */}
        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="flex items-center bg-zinc-950 rounded-lg p-1 border border-zinc-800">
            <span className="px-2 text-zinc-500 uppercase text-[10px]">Season</span>
            {['2026', '2025', '2024'].map(yr => (
              <button
                key={yr}
                onClick={() => handleYearChange(yr)}
                className={`px-2.5 py-1 rounded transition-all ${selectedYear === yr ? 'bg-red-600 text-white font-bold shadow-sm' : 'text-zinc-400 hover:text-white'}`}
              >
                {yr}
              </button>
            ))}
          </div>

          <div className="flex items-center bg-zinc-900 rounded-lg p-1 border border-zinc-700">
            <span className="px-2 text-zinc-400 uppercase text-[10px] font-bold">GP</span>
            <select
              value={selectedGp}
              onChange={(e) => setSelectedGp(e.target.value)}
              className="bg-zinc-950 text-white font-mono text-xs focus:outline-none cursor-pointer px-2 py-1 rounded border border-zinc-800"
            >
              {availableGps.map((g, idx) => (
                <option key={idx} value={g.gp} className="bg-zinc-900 text-white">
                  {g.gp} ({g.status})
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* BODY WITH LEFT SIDEBAR LAYOUT */}
      <div className="flex flex-grow relative">
        {/* LEFT SIDEBAR NAVIGATION */}
        <aside className="w-64 bg-zinc-900/40 border-r border-zinc-800/80 p-4 flex flex-col justify-between shrink-0 font-mono text-xs">
          <div className="space-y-6">
            <div>
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-3 mb-2">// Race Analytics</div>
              <nav className="space-y-1">
                <button
                  onClick={() => setActiveTab('grid')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'grid' ? 'bg-red-600 text-white shadow-md shadow-red-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Grid & Predictions</span>
                </button>
                <button
                  onClick={() => setActiveTab('aero')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'aero' ? 'bg-red-600 text-white shadow-md shadow-red-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Aero Setup</span>
                </button>
                <button
                  onClick={() => setActiveTab('h2h')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'h2h' ? 'bg-red-600 text-white shadow-md shadow-red-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>H2H Telemetry</span>
                </button>
                <button
                  onClick={() => setActiveTab('probability')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'probability' ? 'bg-red-600 text-white shadow-md shadow-red-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Win Probability</span>
                </button>
                <button
                  onClick={() => setActiveTab('montecarlo')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'montecarlo' ? 'bg-red-600 text-white shadow-md shadow-red-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Monte Carlo</span>
                </button>
              </nav>
            </div>

            <div>
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-3 mb-2">// System & Diagnostics</div>
              <nav className="space-y-1">
                <button
                  onClick={() => setActiveTab('diagnostics')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'diagnostics' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Race Diagnostics</span>
                </button>
                <button
                  onClick={() => setActiveTab('tracker')}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left font-semibold ${activeTab === 'tracker' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
                >
                  <span>Prediction Lab</span>
                </button>
              </nav>
            </div>
          </div>

          <div className="border-t border-zinc-800/80 pt-4 text-[10px] text-zinc-500 space-y-1">
            <div>TARGET: <span className="text-zinc-300 font-bold">{selectedGp}</span></div>
            <div>STATUS: <span className="text-emerald-400 font-bold">ONLINE</span></div>
          </div>
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-grow p-6 relative z-10 max-w-7xl w-full mx-auto">
          {loadingData ? (
            <div className="h-[60vh] flex flex-col items-center justify-center relative px-4">
              <div className="relative w-full max-w-xl bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-8 shadow-[0_0_50px_rgba(37,99,235,0.15)] overflow-hidden">
                <div className="flex items-center justify-between mb-6 border-b border-zinc-800/60 pb-4">
                  <div className="flex items-center gap-2.5">
                    <span className="relative flex h-3.5 w-3.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></span>
                    </span>
                    <span className="font-mono text-xs uppercase tracking-widest text-zinc-400">System Telemetry Connection</span>
                  </div>
                  <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest bg-zinc-950/80 px-2.5 py-1 rounded border border-zinc-800/80">
                    {progress.status || 'initializing'}
                  </div>
                </div>

                <div className="flex flex-col items-center justify-center my-8">
                  <div className="font-orbitron text-7xl font-black tracking-tighter bg-gradient-to-r from-blue-400 via-zinc-100 to-red-400 bg-clip-text text-transparent drop-shadow-[0_0_15px_rgba(59,130,246,0.3)] animate-pulse">
                    {activePercent}%
                  </div>
                  <div className="mt-4 text-center font-mono text-xs font-semibold text-zinc-200 tracking-wide max-w-sm h-10 flex items-center justify-center leading-relaxed">
                    {displayMessage}
                  </div>
                </div>

                <div className="w-full bg-zinc-950/80 rounded-full h-3.5 p-0.5 border border-zinc-800/50 shadow-inner">
                  <div 
                    className="bg-gradient-to-r from-blue-600 via-indigo-500 to-red-600 h-2 rounded-full transition-all duration-500 ease-out relative shadow-[0_0_15px_rgba(37,99,235,0.7)]"
                    style={{ width: `${activePercent}%` }}
                  />
                </div>
              </div>
            </div>
          ) : raceData && raceData.error ? (
            <div className="h-[50vh] flex items-center justify-center p-4">
              <div className="max-w-md w-full text-red-500 font-mono bg-red-950/20 p-6 rounded-lg border border-red-900/50 shadow-2xl flex flex-col gap-4">
                <div className="flex items-center gap-2 border-b border-red-900/50 pb-3">
                  <span className="text-sm font-bold uppercase tracking-widest text-red-500">Warning</span>
                  <h2 className="text-sm font-bold uppercase tracking-widest">Pipeline Compile Error</h2>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed font-sans">{raceData.error}</p>
              </div>
            </div>
          ) : (
            <ErrorBoundary>
              <div className="animate-fadeIn duration-500">
                {activeTab === 'grid' && <DataGrid data={raceData} />}
                {activeTab === 'aero' && <AeroMap year={parseInt(selectedYear)} gp={selectedGp} />}
                {activeTab === 'h2h' && <H2H year={parseInt(selectedYear)} gp={selectedGp} />}
                {activeTab === 'probability' && <H2HMatrix year={parseInt(selectedYear)} gp={selectedGp} />}
                {activeTab === 'montecarlo' && <MonteCarlo year={parseInt(selectedYear)} gp={selectedGp} />}
                {activeTab === 'diagnostics' && <RaceDiagnostics year={parseInt(selectedYear)} gp={selectedGp} logs={raceData?.logs} />}
                {activeTab === 'tracker' && <PredictionTracker raceData={raceData} year={parseInt(selectedYear)} gp={selectedGp} />}
              </div>
            </ErrorBoundary>
          )}
        </main>
      </div>

      {/* FOOTER */}
      <footer className="border-t border-zinc-800/60 bg-zinc-950 py-3 px-6 text-center font-mono text-[9px] text-zinc-600 flex justify-between items-center uppercase tracking-widest z-20">
        <div>SECURITY ACCESS LEVEL: FIA_REPRESENTATIVE_06</div>
        <div>F1 ORACLE SYSTEM TERMINAL // JUNE 2026</div>
      </footer>
    </div>
  );
}

export default App;