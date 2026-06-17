import { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';
import TrackMap from './TrackMap';

export default function H2H({ year, gp }) {
  const [h2hData, setH2hData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [driver1, setDriver1] = useState('');
  const [driver2, setDriver2] = useState('');
  const [activeTrace, setActiveTrace] = useState('speed');
  
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    setLoading(true);
    fetch(`${apiUrl}/api/h2h/${year}/${encodeURIComponent(gp)}`)
      .then(res => res.json())
      .then(data => {
        if (!data.detail && data.h2h_data && Object.keys(data.h2h_data).length > 0) {
          setH2hData(data.h2h_data);
          const drivers = Object.keys(data.h2h_data);
          if (drivers.length >= 2) {
            setDriver1(drivers[0]);
            setDriver2(drivers[1]);
          } else if (drivers.length === 1) {
            setDriver1(drivers[0]);
            setDriver2(drivers[0]);
          }
        } else {
          setH2hData(null);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch H2H:", err);
        setH2hData(null);
        setLoading(false);
      });
  }, [year, gp]);

  if (loading) {
    return (
      <div className="h-72 mt-8 flex flex-col items-center justify-center font-mono text-zinc-500 animate-pulse bg-zinc-900/40 border border-zinc-800/80 rounded-lg">
        <div className="h-8 w-8 border-2 border-t-yellow-500 border-zinc-800 rounded-full animate-spin mb-4" />
        ANALYZING TELEMETRY DELTAS...
      </div>
    );
  }

  // Safe checks for empty datasets
  if (!h2hData || Object.keys(h2hData).length === 0) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-yellow-500 bg-yellow-950/10 border border-yellow-900/30 rounded-lg">
        ⚠️ TELEMETRY DELTAS UNAVAILABLE FOR THIS GRAND PRIX
      </div>
    );
  }

  const activeDriver1 = h2hData[driver1] ? driver1 : Object.keys(h2hData)[0];
  const activeDriver2 = h2hData[driver2] ? driver2 : (Object.keys(h2hData)[1] || Object.keys(h2hData)[0]);

  const d1 = h2hData[activeDriver1];
  const d2 = h2hData[activeDriver2];

  const compare = (val1, val2, lowerIsBetter = false) => {
    const diff = val1 - val2;
    const diffStr = diff > 0 ? `+${diff.toFixed(3)}` : diff.toFixed(3);
    
    let isBetter = false;
    if (diff < 0) isBetter = lowerIsBetter;
    if (diff > 0) isBetter = !lowerIsBetter;
    
    let color = 'text-zinc-500 bg-zinc-950/40';
    if (diff !== 0) {
        color = isBetter ? 'text-emerald-400 bg-emerald-950/25 border-emerald-900/30' : 'text-rose-400 bg-rose-950/25 border-rose-900/30';
    }

    return { diffStr, color };
  };

  const metrics = [
    { label: "BEST LAP TIME", key: "lap_time", lowerIsBetter: true, format: v => v.toFixed(3) },
    { label: "SECTOR 1 DELTA", key: "s1_time", lowerIsBetter: true, format: v => v.toFixed(3) },
    { label: "SECTOR 3 DELTA", key: "s3_time", lowerIsBetter: true, format: v => v.toFixed(3) },
    { label: "TOP SPEED (KM/H)", key: "top_speed", lowerIsBetter: false, format: v => v.toFixed(0), diffFormat: d => parseFloat(d).toFixed(0) > 0 ? `+${parseFloat(d).toFixed(0)}` : parseFloat(d).toFixed(0) },
    { label: "S1/S3 AERO RATIO", key: "s1_s3_ratio", lowerIsBetter: true, format: v => v.toFixed(3) },
    { label: "ERS EFFICIENCY", key: "ers_efficiency", lowerIsBetter: false, format: v => v.toFixed(3) },
    { label: "LIFT & COAST (S)", key: "lift_and_coast", lowerIsBetter: true, format: v => v.toFixed(3) },
    { label: "STINT DEG RATE", key: "stint_deg_rate", lowerIsBetter: true, format: v => `+${v.toFixed(3)}` }
  ];

  return (
    <div className="bg-zinc-900/50 backdrop-blur-md rounded-lg border border-zinc-800 p-6 shadow-2xl mt-8">
      {/* SECTION HEADER */}
      <h2 className="font-orbitron text-lg font-black mb-6 uppercase tracking-wide border-l-4 border-yellow-500 pl-3 flex items-center gap-2 text-white">
        <span className="text-yellow-500">⚡</span> Driver Telemetry Overlay
      </h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* METRICS COMPARATOR PANEL (5 COLS) */}
        <div className="lg:col-span-5 bg-zinc-950/80 rounded-lg p-5 border border-zinc-800 flex flex-col justify-between">
          {/* DRIVER SELECTION ROW */}
          <div className="flex justify-between items-center mb-6 pb-4 border-b border-zinc-800/80">
            <select 
              value={activeDriver1} 
              onChange={(e) => setDriver1(e.target.value)}
              className="bg-zinc-900 text-blue-400 border border-zinc-800 rounded px-3 py-1.5 font-orbitron font-black text-base w-28 focus:outline-none focus:border-blue-500 cursor-pointer hover:bg-zinc-800 transition-colors"
            >
              {Object.keys(h2hData).map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            
            <div className="text-zinc-500 font-bold font-mono tracking-widest text-xs uppercase px-4 py-1 bg-zinc-900 rounded-full border border-zinc-800">VS</div>
            
            <select 
              value={activeDriver2} 
              onChange={(e) => setDriver2(e.target.value)}
              className="bg-zinc-900 text-yellow-500 border border-zinc-800 rounded px-3 py-1.5 font-orbitron font-black text-base w-28 focus:outline-none focus:border-yellow-500 cursor-pointer hover:bg-zinc-800 transition-colors"
            >
              {Object.keys(h2hData).map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>

          {/* METRICS ROWS */}
          <div className="flex flex-col gap-4 flex-grow">
            {metrics.map(m => {
              const val1 = d1[m.key] || 0;
              const val2 = d2[m.key] || 0;
              const { diffStr, color } = compare(val1, val2, m.lowerIsBetter);
              const finalDiffStr = m.diffFormat ? m.diffFormat(diffStr) : diffStr;

              return (
                <div key={m.key} className="flex justify-between items-center py-2.5 border-b border-zinc-900/40 last:border-0">
                  {/* Driver 1 value */}
                  <div className="w-1/4 text-left font-mono font-bold text-sm text-zinc-300">
                    {m.format(val1)}
                  </div>
                  
                  {/* Metric Label and Badge */}
                  <div className="w-2/4 flex flex-col items-center justify-center">
                    <span className="text-[9px] font-mono text-zinc-500 font-bold tracking-wider uppercase mb-1">{m.label}</span>
                    <span className={`font-mono text-[9px] font-black px-2 py-0.5 rounded border ${color}`}>
                      {finalDiffStr}
                    </span>
                  </div>
                  
                  {/* Driver 2 value */}
                  <div className="w-1/4 text-right font-mono font-bold text-sm text-zinc-300">
                    {m.format(val2)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CHART TRACE PANEL (7 COLS) */}
        <div className="lg:col-span-7 bg-zinc-950/80 rounded-lg p-5 border border-zinc-800 flex flex-col">
          {/* TRACE SWITCHER */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-4 border-b border-zinc-800/80">
            <h3 className="font-mono text-zinc-400 font-bold uppercase tracking-wider text-xs">Qualifying Telemetry Overlay</h3>
            <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 font-mono text-[10px] font-bold">
              {['speed', 'throttle', 'brake', 'gear'].map(trace => (
                <button
                  key={trace}
                  onClick={() => setActiveTrace(trace)}
                  className={`px-3 py-1.5 rounded transition-all ${activeTrace === trace ? 'bg-blue-600 text-white shadow-md font-black' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
                >
                  {trace.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* TELEMETRY CHART */}
          <div className="h-[280px] w-full mt-2">
            {d1.telemetry && d2.telemetry && d1.telemetry.length > 0 && d2.telemetry.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f23" vertical={false} />
                  <XAxis 
                    type="number" 
                    dataKey="distance" 
                    name="Distance" 
                    stroke="#52525b" 
                    tickFormatter={(val) => `${val}m`}
                    domain={['dataMin', 'dataMax']}
                    tick={{ fontSize: 9, fontFamily: 'monospace' }}
                  />
                  <YAxis 
                    type="number" 
                    dataKey={activeTrace} 
                    name={activeTrace.toUpperCase()} 
                    stroke="#52525b"
                    domain={activeTrace === 'throttle' ? [0, 100] : activeTrace === 'brake' ? [0, 1] : ['auto', 'auto']}
                    tick={{ fontSize: 9, fontFamily: 'monospace' }}
                  />
                  <RechartsTooltip 
                    cursor={{ strokeDasharray: '3 3', stroke: '#3f3f46' }}
                    contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', fontFamily: 'monospace', borderRadius: '6px', fontSize: '11px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Legend iconType="circle" wrapperStyle={{ fontFamily: 'monospace', fontSize: '10px', marginTop: '10px' }} />
                  
                  <Scatter name={activeDriver1} data={d1.telemetry} line={{ strokeWidth: 1.5, stroke: '#3b82f6' }} shape={<></>} fill="#3b82f6" />
                  <Scatter name={activeDriver2} data={d2.telemetry} line={{ strokeWidth: 1.5, stroke: '#eab308' }} shape={<></>} fill="#eab308" />
                </ScatterChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full w-full flex items-center justify-center font-mono text-zinc-600 bg-zinc-900/10 rounded border border-zinc-800/80 border-dashed">
                ⚠️ TELEMETRY OVERLAY DATA RETRIEVAL FAILURE
              </div>
            )}
          </div>
        </div>
      </div>
      
      <TrackMap 
        driver1={activeDriver1}
        driver2={activeDriver2}
        d1Telemetry={d1?.telemetry || []}
        d2Telemetry={d2?.telemetry || []}
      />
    </div>
  );
}
