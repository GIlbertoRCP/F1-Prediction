import { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';

export default function H2H({ year, gp }) {
  const [h2hData, setH2hData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [driver1, setDriver1] = useState('NOR');
  const [driver2, setDriver2] = useState('VER'); // Or any default
  const [activeTrace, setActiveTrace] = useState('speed');
  
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    fetch(`${apiUrl}/api/h2h/${year}/${gp}`)
      .then(res => res.json())
      .then(data => {
        if (!data.detail && data.h2h_data) {
          setH2hData(data.h2h_data);
          const drivers = Object.keys(data.h2h_data);
          if (drivers.length >= 2) {
            setDriver1('NOR');
            setDriver2('ANT');
          }
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch H2H:", err);
        setLoading(false);
      });
  }, [year, gp]);

  if (loading) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-zinc-500 animate-pulse bg-zinc-900 border border-zinc-800 rounded-lg">
        ANALYZING TELEMETRY DELTAS...
      </div>
    );
  }

  if (!h2hData || !h2hData[driver1] || !h2hData[driver2]) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-red-500 bg-red-950/20 border border-red-900 rounded-lg">
        H2H DATA UNAVAILABLE
      </div>
    );
  }

  const d1 = h2hData[driver1];
  const d2 = h2hData[driver2];

  const compare = (val1, val2, lowerIsBetter = false) => {
    const diff = val1 - val2;
    // Format diff to string with sign
    const diffStr = diff > 0 ? `+${diff.toFixed(3)}` : diff.toFixed(3);
    
    let isBetter = false;
    if (diff < 0) isBetter = lowerIsBetter;
    if (diff > 0) isBetter = !lowerIsBetter;
    
    // In the mockup, negative deltas in lap time are green, positive are red.
    // However, top speed positive deltas are green.
    let color = 'text-zinc-400';
    if (diff !== 0) {
        color = isBetter ? 'text-green-400' : 'text-red-400';
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
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6 shadow-2xl mt-8">
      <h2 className="text-xl font-bold mb-6 uppercase tracking-wide border-l-4 border-yellow-500 pl-3 flex items-center gap-2">
        <span className="text-yellow-500">⚡</span> H2H Delta Analysis
      </h2>
      
      <div className="bg-zinc-950 rounded-lg p-6 border border-zinc-800">
        {/* DRIVER SELECTION ROW */}
        <div className="flex justify-between items-center mb-8 pb-6 border-b border-zinc-800">
          <select 
            value={driver1} 
            onChange={(e) => setDriver1(e.target.value)}
            className="bg-zinc-800 text-white border border-zinc-700 rounded px-4 py-2 font-mono font-bold text-lg w-32 focus:outline-none focus:border-zinc-500"
          >
            {Object.keys(h2hData).map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          
          <div className="text-zinc-600 font-bold font-mono tracking-widest text-sm">VS</div>
          
          <select 
            value={driver2} 
            onChange={(e) => setDriver2(e.target.value)}
            className="bg-zinc-800 text-white border border-zinc-700 rounded px-4 py-2 font-mono font-bold text-lg w-32 focus:outline-none focus:border-zinc-500"
          >
            {Object.keys(h2hData).map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        {/* METRICS ROWS */}
        <div className="flex flex-col gap-6">
          {metrics.map(m => {
            const val1 = d1[m.key];
            const val2 = d2[m.key];
            const { diffStr, color } = compare(val1, val2, m.lowerIsBetter);
            const finalDiffStr = m.diffFormat ? m.diffFormat(diffStr) : diffStr;

            return (
              <div key={m.key} className="flex justify-between items-center pb-6 border-b border-zinc-800/50 last:border-0 last:pb-0">
                <div className="w-1/3 text-left font-mono text-zinc-300">
                  {m.format(val1)}
                </div>
                
                <div className="w-1/3 flex flex-col items-center justify-center">
                  <span className="text-xs font-mono text-zinc-500 mb-2">{m.label}</span>
                  <span className={`font-mono text-xs font-bold px-2 py-1 rounded bg-zinc-900 border border-zinc-800 ${color}`}>
                    {finalDiffStr}
                  </span>
                </div>
                
                <div className="w-1/3 text-right font-mono text-zinc-300">
                  {m.format(val2)}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* TELEMETRY OVERLAY CHART */}
      <div className="bg-zinc-950 rounded-lg p-6 border border-zinc-800 mt-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="font-mono text-zinc-300 font-bold uppercase tracking-widest text-sm">Fastest Lap Telemetry</h3>
          <div className="flex bg-zinc-900 border border-zinc-700 rounded-lg p-1 font-mono text-xs">
            {['speed', 'throttle', 'brake', 'gear'].map(trace => (
              <button
                key={trace}
                onClick={() => setActiveTrace(trace)}
                className={`px-3 py-1 rounded transition-colors ${activeTrace === trace ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
              >
                {trace.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="h-[300px] w-full">
          {d1.telemetry && d2.telemetry ? (
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis 
                  type="number" 
                  dataKey="distance" 
                  name="Distance" 
                  stroke="#a1a1aa" 
                  tickFormatter={(val) => `${val}m`}
                  domain={['dataMin', 'dataMax']}
                />
                <YAxis 
                  type="number" 
                  dataKey={activeTrace} 
                  name={activeTrace.toUpperCase()} 
                  stroke="#a1a1aa"
                  domain={['auto', 'auto']}
                />
                <RechartsTooltip 
                  cursor={{ strokeDasharray: '3 3', stroke: '#3f3f46' }}
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#3f3f46', fontFamily: 'monospace' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Legend iconType="plainline" wrapperStyle={{ fontFamily: 'monospace', fontSize: '12px' }} />
                
                <Scatter name={driver1} data={d1.telemetry} line={{ strokeWidth: 2 }} shape={<></>} fill="#3b82f6" />
                <Scatter name={driver2} data={d2.telemetry} line={{ strokeWidth: 2 }} shape={<></>} fill="#eab308" />
              </ScatterChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full w-full flex items-center justify-center font-mono text-zinc-500 bg-zinc-900/50 rounded border border-zinc-800 border-dashed">
              TELEMETRY TRACE UNAVAILABLE
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
