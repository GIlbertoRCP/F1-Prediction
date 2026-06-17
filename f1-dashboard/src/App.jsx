import { useState, useEffect } from 'react';
import AeroMap from './AeroMap';
import DataGrid from './DataGrid';
import RaceTimeline from './RaceTimeline';
import H2H from './H2H';
import ModelInsights from './ModelInsights';
import EngineBattle from './EngineBattle';
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
        // Default to current year (2026) and first available completed/interesting GP
        if (json.races && json.races['2026']) {
          setSelectedYear('2026');
          // If Miami is in the list, default to it, else default to first
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

    setSimulatedPercent(5); // Start at 5%
    
    const interval = setInterval(() => {
      setSimulatedPercent(prev => {
        if (prev < 15) {
          return prev + 2; // Speed through setup
        } else if (prev < 80) {
          // Slow down during heavy FastF1 data loading
          return prev + (Math.random() > 0.6 ? 1 : 0); 
        } else if (prev < 95) {
          // Speed up slightly during training / inference
          return prev + 1;
        } else {
          return 95; // Hold at 95% until loaded
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [loadingData]);

  // Filter GPs for selected year
  const availableGps = schedule && schedule.races ? schedule.races[selectedYear] || [] : [];

  const activePercent = Math.max(progress.percent, simulatedPercent);

  // Dynamic step message based on progress
  let displayMessage = statusMessage;
  if (activePercent > 0) {
    if (progress.message && progress.message !== 'Ready' && progress.message !== 'System ready') {
      displayMessage = progress.message;
    } else {
      if (activePercent < 15) {
        displayMessage = `Initializing neural model for ${selectedGp}...`;
      } else if (activePercent < 50) {
        displayMessage = `Downloading telemetry & sector data for ${selectedGp} (first run may take a moment)...`;
      } else if (activePercent < 80) {
        displayMessage = `Extracting fuel-corrected pace, compound averages & ERS metrics...`;
      } else if (activePercent < 90) {
        displayMessage = `Fitting XGBoost pairwise ranking model on historical race context...`;
      } else if (activePercent < 100) {
        displayMessage = `Running inference to predict final grid positions...`;
      } else {
        displayMessage = `Telemetry analysis finished!`;
      }
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* GLOWING AMBIENT BACKGROUNDS */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-red-600/5 rounded-full blur-3xl pointer-events-none" />

      {/* HEADER BAR */}
      <header className="relative z-10 border-b border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md px-6 py-4 flex flex-col lg:flex-row items-center justify-between gap-6 shadow-lg">
        {/* BRAND & TITLE */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 bg-gradient-to-tr from-blue-600 to-red-600 rounded-lg flex items-center justify-center shadow-md shadow-blue-500/20">
            <span className="font-orbitron font-black text-lg text-white">Ω</span>
          </div>
          <div>
            <h1 className="font-orbitron text-xl font-black tracking-tight text-white flex items-center gap-2">
              F1 ORACLE <span className="text-xs bg-zinc-800 text-blue-400 border border-zinc-700 px-2 py-0.5 rounded font-mono font-bold tracking-widest uppercase">v2.0</span>
            </h1>
            <p className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mt-0.5">
              Telemetry Analytics & Pairwise XGBRanker Predictor
            </p>
          </div>
        </div>

        {/* SELECTORS & CONTROL PANEL */}
        <div className="flex flex-wrap items-center gap-3 bg-zinc-900/90 border border-zinc-800 p-2 rounded-lg font-mono text-xs shadow-inner">
          {/* YEAR SELECTOR */}
          <div className="flex items-center gap-1">
            <span className="text-zinc-500 uppercase tracking-widest text-[9px] px-2">Season:</span>
            <select
              value={selectedYear}
              onChange={(e) => {
                setSelectedYear(e.target.value);
                const firstGpOfNewYear = schedule?.races[e.target.value]?.[0]?.gp || '';
                setSelectedGp(firstGpOfNewYear);
              }}
              className="bg-zinc-950 hover:bg-zinc-800 text-white border border-zinc-800 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-bold cursor-pointer"
            >
              {schedule?.years?.map(y => (
                <option key={y} value={y}>{y} Season</option>
              )) || <option value="2026">2026</option>}
            </select>
          </div>

          <div className="h-5 w-[1px] bg-zinc-800" />

          {/* GRAND PRIX SELECTOR */}
          <div className="flex items-center gap-1">
            <span className="text-zinc-500 uppercase tracking-widest text-[9px] px-2">GP:</span>
            <select
              value={selectedGp}
              onChange={(e) => setSelectedGp(e.target.value)}
              className="bg-zinc-950 hover:bg-zinc-800 text-white border border-zinc-800 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-bold max-w-[180px] sm:max-w-none cursor-pointer"
            >
              {availableGps.map(g => (
                <option key={g.gp} value={g.gp}>
                  [{g.date}] {g.gp} {g.status === 'upcoming' ? ' (Upcoming)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* SUB-HEADER / TAB NAVIGATION */}
      <nav className="relative z-10 border-b border-zinc-800/50 bg-zinc-900/20 px-6 py-2 flex flex-col sm:flex-row justify-between items-center gap-4 shadow-sm">
        {/* CURRENT LOCATION BADGE */}
        <div className="flex items-center gap-2 font-mono text-xs text-zinc-400">
          <span className="h-2 w-2 rounded-full bg-green-500 animate-ping" />
          <span className="uppercase text-[10px] tracking-wider text-zinc-500">LIVE FEED:</span>
          <span className="font-bold text-white font-orbitron">{selectedGp} {selectedYear}</span>
          {availableGps.find(g => g.gp === selectedGp)?.status === 'upcoming' && (
            <span className="bg-blue-950/50 text-blue-400 border border-blue-900 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider">Upcoming Race</span>
          )}
        </div>

        {/* TABS CONTROLS */}
        <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1 font-mono text-xs font-bold shadow-inner">
          <button 
            onClick={() => setActiveTab('grid')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'grid' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Grid Predictions
          </button>
          <button 
            onClick={() => setActiveTab('timeline')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'timeline' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Race Events
          </button>
          <button 
            onClick={() => setActiveTab('aero')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'aero' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Aero Setup
          </button>
          <button 
            onClick={() => setActiveTab('h2h')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'h2h' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            H2H Telemetry
          </button>
          <button 
            onClick={() => setActiveTab('engine')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'engine' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Engine Battle
          </button>
          <button 
            onClick={() => setActiveTab('insights')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'insights' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Model Insights
          </button>
          <button 
            onClick={() => setActiveTab('probability')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'probability' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Win Probability
          </button>
          <button 
            onClick={() => setActiveTab('montecarlo')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-all ${activeTab === 'montecarlo' ? 'bg-blue-600 text-white shadow-md' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
          >
            Monte Carlo
          </button>
        </div>
      </nav>

      {/* MAIN CONTENT AREA */}
      <main className="flex-grow p-6 relative z-10 max-w-7xl mx-auto w-full">
        {loadingData ? (
          /* PRECISE TIMING SCREEN LOADER */
          <div className="h-[60vh] flex flex-col items-center justify-center relative px-4">
            {/* Glassmorphic Panel */}
            <div className="relative w-full max-w-xl bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-8 shadow-[0_0_50px_rgba(37,99,235,0.15)] overflow-hidden">
              
              {/* Corner accent decorations */}
              <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-blue-500 rounded-tl-md" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-red-500 rounded-tr-md" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-red-500 rounded-bl-md" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-blue-500 rounded-br-md" />

              {/* Status Header with Heartbeat */}
              <div className="flex items-center justify-between mb-6 border-b border-zinc-800/60 pb-4">
                <div className="flex items-center gap-2.5">
                  {/* Heartbeat indicator light */}
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

              {/* Central Progress Reading */}
              <div className="flex flex-col items-center justify-center my-8">
                {/* Large animated Orbitron numerical readout */}
                <div className="font-orbitron text-7xl font-black tracking-tighter bg-gradient-to-r from-blue-400 via-zinc-100 to-red-400 bg-clip-text text-transparent drop-shadow-[0_0_15px_rgba(59,130,246,0.3)] animate-pulse">
                  {activePercent}%
                </div>
                
                {/* Subtitle / Status message */}
                <div className="mt-4 text-center font-mono text-xs font-semibold text-zinc-200 tracking-wide max-w-sm h-10 flex items-center justify-center leading-relaxed">
                  {displayMessage}
                </div>
              </div>

              {/* Glowing horizontal progress bar */}
              <div className="w-full bg-zinc-950/80 rounded-full h-3.5 p-0.5 border border-zinc-800/50 shadow-inner">
                <div 
                  className="bg-gradient-to-r from-blue-600 via-indigo-500 to-red-600 h-2 rounded-full transition-all duration-500 ease-out relative shadow-[0_0_15px_rgba(37,99,235,0.7)]"
                  style={{ width: `${activePercent}%` }}
                >
                  <div className="absolute inset-0 bg-stripes animate-[progressbar-stripes_1s_linear_infinite] rounded-full" />
                </div>
              </div>

              {/* Dynamic Step Logs beneath progress bar */}
              <div className="mt-6 flex justify-between items-center font-mono text-[9px] text-zinc-500 uppercase tracking-wider">
                <div className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${activePercent >= 5 ? 'bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.6)]' : 'bg-zinc-700'}`} />
                  <span>Setup</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${activePercent >= 15 ? 'bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.6)]' : 'bg-zinc-700'}`} />
                  <span>FE Engine</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${activePercent >= 80 ? 'bg-indigo-500 shadow-[0_0_6px_rgba(99,102,241,0.6)]' : 'bg-zinc-700'}`} />
                  <span>Training</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${activePercent >= 90 ? 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]' : 'bg-zinc-700'}`} />
                  <span>Inference</span>
                </div>
              </div>
            </div>
            
            {/* Bottom auxiliary message */}
            <p className="mt-4 font-mono text-[9px] text-zinc-600 uppercase tracking-widest text-center max-w-sm">
              Note: Telemetry parsing utilizes fastf1 API. First runs may require several minutes to cache data from FIA servers.
            </p>
          </div>
        ) : raceData && raceData.error ? (
          /* DEFENSIVE ERROR DISPLAY */
          <div className="h-[50vh] flex items-center justify-center p-4">
            <div className="max-w-md w-full text-red-500 font-mono bg-red-950/20 p-6 rounded-lg border border-red-900/50 shadow-2xl flex flex-col gap-4">
              <div className="flex items-center gap-2 border-b border-red-900/50 pb-3">
                <span className="text-sm font-bold uppercase tracking-widest text-red-500">Warning</span>
                <h2 className="text-sm font-bold uppercase tracking-widest">Pipeline Compile Error</h2>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans">{raceData.error}</p>
              <div className="text-[9px] text-zinc-600 border-t border-red-900/30 pt-3">
                PRO TIP: Upcoming races might require FP sessions to finish before telemetry data can be computed.
              </div>
            </div>
          </div>
        ) : (
          /* DYNAMIC DASHBOARD VIEWS */
          <ErrorBoundary>
            <div className="animate-fadeIn duration-500">
              {activeTab === 'grid' && <DataGrid data={raceData} />}
              {activeTab === 'timeline' && <RaceTimeline logs={raceData.logs} gpName={selectedGp} year={selectedYear} />}
              {activeTab === 'aero' && <AeroMap year={parseInt(selectedYear)} gp={selectedGp} />}
              {activeTab === 'h2h' && <H2H year={parseInt(selectedYear)} gp={selectedGp} />}
              {activeTab === 'engine' && <EngineBattle year={parseInt(selectedYear)} gp={selectedGp} />}
              {activeTab === 'insights' && <ModelInsights year={parseInt(selectedYear)} gp={selectedGp} />}
              {activeTab === 'probability' && <H2HMatrix year={parseInt(selectedYear)} gp={selectedGp} />}
              {activeTab === 'montecarlo' && <MonteCarlo year={parseInt(selectedYear)} gp={selectedGp} />}
            </div>
          </ErrorBoundary>
        )}
      </main>

      {/* FOOTER PANNEL */}
      <footer className="border-t border-zinc-800/60 bg-zinc-950 py-4 px-6 text-center font-mono text-[9px] text-zinc-600 flex justify-between items-center uppercase tracking-widest">
        <div>SECURITY ACCESS LEVEL: FIA_REPRESENTATIVE_06</div>
        <div>F1 ORACLE SYSTEM TERMINAL // JUNE 2026</div>
      </footer>
    </div>
  );
}

export default App;