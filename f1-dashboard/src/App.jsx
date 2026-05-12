import { useState, useEffect } from 'react';
import AeroMap from './AeroMap';
import DataGrid from './DataGrid';
import RaceTimeline from './RaceTimeline';
import H2H from './H2H';
import ErrorBoundary from './ErrorBoundary';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('timeline');

  useEffect(() => {
    // Fetch from your FastAPI backend
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    fetch(`${apiUrl}/api/race/2026/Miami`)
      .then(res => res.json())
      .then(json => {
        if (json.detail) {
          console.error("Backend Error:", json.detail);
          setData({ error: json.detail });
        } else {
          setData(json);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch:", err);
        setData({ error: "Network connection failed." });
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950">
        <div className="text-2xl font-mono animate-pulse text-zinc-400">
          INITIALIZING TELEMETRY...
        </div>
      </div>
    );
  }

  if (data && data.error) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 p-8">
        <div className="text-red-500 font-mono bg-red-950/30 p-6 rounded border border-red-900 shadow-2xl">
          <h2 className="text-xl font-bold mb-2">TELEMETRY ERROR</h2>
          <p>{data.error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 bg-zinc-950 text-white font-sans">
      {/* HEADER & TABS */}
      <header className="mb-8 border-b border-zinc-800 pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <span className="text-blue-500">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M4 12H8L10 8L14 16L16 12H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </span>
            Advanced Telemetry Analytics
          </h1>
          <p className="text-zinc-500 font-mono text-xs mt-2 uppercase tracking-widest">
            ENGINEERING ACCESS TERMINAL // POST-RACE LOGS // {data.race}
          </p>
        </div>
        
        <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1 font-mono text-xs font-bold">
          <button 
            onClick={() => setActiveTab('timeline')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-colors ${activeTab === 'timeline' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
          >
            ⏱ Race Timeline
          </button>
          <button 
            onClick={() => setActiveTab('grid')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-colors ${activeTab === 'grid' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
          >
            📈 Data Grid
          </button>
          <button 
            onClick={() => setActiveTab('aero')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-colors ${activeTab === 'aero' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
          >
            🎯 Aero Setup Map
          </button>
          <button 
            onClick={() => setActiveTab('h2h')}
            className={`px-4 py-2 rounded flex items-center gap-2 transition-colors ${activeTab === 'h2h' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
          >
            📊 H2H Deltas
          </button>
        </div>
      </header>

      {/* TAB CONTENT */}
      <ErrorBoundary>
        <div className="transition-opacity duration-300">
          {activeTab === 'timeline' && <RaceTimeline logs={data.logs} />}
          {activeTab === 'grid' && <DataGrid data={data} />}
          {activeTab === 'aero' && <AeroMap year={2026} gp="Miami" />}
          {activeTab === 'h2h' && <H2H year={2026} gp="Miami" />}
        </div>
      </ErrorBoundary>
      
    </div>
  );
}

export default App;