import { useState, useEffect, useMemo } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList, AreaChart, Area, ReferenceDot } from 'recharts';

// Official team colors for the scatter dots
const teamColors = {
  "Red Bull Racing": "#3671C6",
  "McLaren": "#FF8000",
  "Ferrari": "#E80020",
  "Mercedes": "#27F4D2",
  "Aston Martin": "#229971",
  "Alpine": "#0093CC",
  "Williams": "#64C4FF",
  "Racing Bulls": "#6692FF",
  "Kick Sauber": "#52E252",
  "Haas": "#B6BABD",
  "Audi": "#F50537" 
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    // Provide a simple deterministic mock for deg rate
    const degMock = ((data.max_speed * 0.01) % 0.05).toFixed(3);
    return (
      <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-lg shadow-xl font-mono text-sm w-48 text-left">
        <p className="font-bold text-white mb-2">{data.driver} <span className="text-zinc-500 text-xs">({data.team})</span></p>
        <div className="flex justify-between items-center mb-1">
          <span className="text-zinc-400">Ratio:</span>
          <span className="text-purple-400 font-bold">{data.s1_s3_ratio.toFixed(3)}</span>
        </div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-zinc-400">Speed:</span>
          <span className="text-yellow-400 font-bold">{data.max_speed.toFixed(0)} km/h</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-zinc-400">Degradation:</span>
          <span className="text-red-400 font-bold">+{degMock}</span>
        </div>
      </div>
    );
  }
  return null;
};

export default function AeroMap({ year, gp }) {
  const [aeroData, setAeroData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDriver, setSelectedDriver] = useState(null);
  const [wingAdjustment, setWingAdjustment] = useState(0);

  useEffect(() => {
    setWingAdjustment(0);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    setLoading(true);
    fetch(`${apiUrl}/api/aero/${year}/${encodeURIComponent(gp)}`)
      .then(res => res.json())
      .then(data => {
        if (data.detail || !data.aero_data) {
          console.error("Aero API Error:", data.detail);
          setAeroData([]);
          setSelectedDriver(null);
        } else {
          setAeroData(data.aero_data);
          const valid = data.aero_data.filter(d => 
            d && 
            typeof d.s1_s3_ratio === 'number' && !isNaN(d.s1_s3_ratio) && 
            typeof d.max_speed === 'number' && !isNaN(d.max_speed)
          );
          if (valid.length > 0) {
            setSelectedDriver(valid[0]);
          } else {
            setSelectedDriver(null);
          }
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch aero map", err);
        setAeroData([]);
        setSelectedDriver(null);
        setLoading(false);
      });
  }, [year, gp]);

  // Handle loading state
  if (loading) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-zinc-500 animate-pulse bg-zinc-900 border border-zinc-800 rounded-lg">
        ANALYZING QUALIFYING TELEMETRY...
      </div>
    );
  }

  if (!aeroData || aeroData.length === 0) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-red-500 bg-red-950/20 border border-red-900 rounded-lg">
        TELEMETRY UNAVAILABLE FOR AERO MAP
      </div>
    );
  }

  const validData = aeroData.filter(d => 
    d && 
    typeof d.s1_s3_ratio === 'number' && !isNaN(d.s1_s3_ratio) && 
    typeof d.max_speed === 'number' && !isNaN(d.max_speed)
  );

  if (validData.length === 0) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-red-500 bg-red-950/20 border border-red-900 rounded-lg">
        TELEMETRY CORRUPTED (NaN VALUES DETECTED)
      </div>
    );
  }

  const minX = Math.min(...validData.map(d => d.s1_s3_ratio)) - 0.05;
  const maxX = Math.max(...validData.map(d => d.s1_s3_ratio)) + 0.05;
  const minY = Math.floor(Math.min(...validData.map(d => d.max_speed)) - 3);
  const maxY = Math.ceil(Math.max(...validData.map(d => d.max_speed)) + 3);

  // Active driver calculation (fallback to first valid driver)
  const activeDriver = selectedDriver || validData[0];

  // Track profiling logic based on field speeds
  const avgTrackSpeed = validData.reduce((acc, d) => acc + d.max_speed, 0) / validData.length;
  const trackType = avgTrackSpeed > 322 ? 'high-speed' : avgTrackSpeed < 305 ? 'high-downforce' : 'balanced';
  const bestClick = trackType === 'high-speed' ? -3 : trackType === 'high-downforce' ? 3 : 0;

  // Simulated metrics
  const simSpeed = activeDriver ? activeDriver.max_speed - (wingAdjustment * 1.5) : 0;
  const simRatio = activeDriver ? activeDriver.s1_s3_ratio + (wingAdjustment * 0.012) : 0;
  const simDelta = activeDriver ? (0.015 * Math.pow(wingAdjustment - bestClick, 2) - 0.015 * Math.pow(bestClick, 2)) : 0;

  // Tradeoff curve data mapping
  const tradeoffCurveData = [];
  for (let c = -5; c <= 5; c++) {
    const lapDelta = 0.015 * Math.pow(c - bestClick, 2) - 0.015 * Math.pow(bestClick, 2);
    tradeoffCurveData.push({
      clicks: c,
      lapDelta: parseFloat(lapDelta.toFixed(3))
    });
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg shadow-2xl mt-8 flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold uppercase tracking-wide border-l-4 border-blue-500 pl-3 text-white">
          Aero Setup Configuration
        </h2>
        <p className="text-xs font-mono text-zinc-500 mt-1 pl-4 uppercase">
          Qualifying Fastest Lap | Cornering Grip vs Straight Line Drag
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* PLOT CARD CONTAINER (7 COLS) */}
        <div className="lg:col-span-7 bg-zinc-950/40 border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between shadow-lg">
          <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                
                <XAxis 
                  type="number" 
                  dataKey="s1_s3_ratio" 
                  name="S1/S3 TIME RATIO" 
                  domain={[minX, maxX]} 
                  stroke="#a1a1aa"
                  label={{ value: "High Downforce / High Drag                     Low Downforce / High Top Speed", position: "bottom", fill: "#52525b", fontSize: 10, fontFamily: 'monospace' }} 
                />
                
                <YAxis 
                  type="number" 
                  dataKey="max_speed" 
                  name="Top Speed" 
                  domain={[minY, maxY]} 
                  stroke="#a1a1aa"
                  label={{ value: "Top Speed (km/h)", angle: -90, position: "insideLeft", fill: "#52525b", fontSize: 10, fontFamily: 'monospace' }} 
                />
                
                <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#3f3f46' }} />
                
                <Scatter 
                  name="Drivers" 
                  data={validData}
                  onClick={(data) => {
                    if (data && data.payload) {
                      setSelectedDriver(data.payload);
                    }
                  }}
                >
                  {validData.map((entry, index) => {
                    const isSelected = activeDriver && activeDriver.driver === entry.driver;
                    return (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={teamColors[entry.team] || "#ffffff"} 
                        stroke={isSelected ? "#ffffff" : "#000000"} 
                        strokeWidth={isSelected ? 2.5 : 1}
                        r={isSelected ? 8 : 5.5}
                        className="cursor-pointer transition-all duration-200"
                      />
                    );
                  })}
                  <LabelList dataKey="driver" position="top" fill="#a1a1aa" fontSize={10} fontWeight="bold" />
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* SIMULATOR CARD CONTAINER (5 COLS) */}
        <div className="lg:col-span-5 bg-zinc-950/80 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between shadow-lg">
          {activeDriver ? (
            <div className="flex flex-col gap-5 h-full">
              {/* Header Info */}
              <div className="flex justify-between items-center pb-3 border-b border-zinc-800/80">
                <div className="flex items-center gap-3">
                  <div 
                    className="h-10 w-10 rounded-lg flex items-center justify-center font-orbitron font-black text-sm border transition-all"
                    style={{ 
                      borderColor: teamColors[activeDriver.team] || '#52525b',
                      color: teamColors[activeDriver.team] || '#ffffff',
                      backgroundColor: `${teamColors[activeDriver.team] || '#52525b'}20`
                    }}
                  >
                    {activeDriver.driver}
                  </div>
                  <div>
                    <h3 className="font-orbitron text-sm font-black tracking-tight text-white uppercase">
                      Setup Simulator
                    </h3>
                    <p className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">
                      {activeDriver.team}
                    </p>
                  </div>
                </div>
                
                <div className="text-right">
                  <span className="text-[8px] text-zinc-500 font-mono uppercase tracking-widest block">Track Layout</span>
                  <span className="text-[9px] font-mono text-zinc-300 font-bold uppercase bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded">
                    {trackType.replace('-', ' ')}
                  </span>
                </div>
              </div>

              {/* Selector Dropdown */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] font-mono text-zinc-500 font-bold uppercase tracking-wider">Selected Driver</label>
                <select
                  value={activeDriver.driver}
                  onChange={(e) => {
                    const selected = validData.find(d => d.driver === e.target.value);
                    if (selected) {
                      setSelectedDriver(selected);
                    }
                  }}
                  className="bg-zinc-900 text-zinc-300 border border-zinc-800 rounded px-3 py-1.5 font-mono text-xs focus:outline-none focus:border-blue-500 cursor-pointer hover:bg-zinc-800 transition-colors w-full"
                >
                  {validData.map(d => (
                    <option key={d.driver} value={d.driver}>{d.driver} ({d.team})</option>
                  ))}
                </select>
              </div>

              {/* Setup Adjustment Controls */}
              <div className="flex flex-col gap-2 bg-zinc-900/40 p-4 rounded-lg border border-zinc-800/60">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className="text-zinc-400 font-semibold">Rear Wing Angle:</span>
                  <span className={`font-bold ${wingAdjustment === 0 ? 'text-zinc-400' : wingAdjustment > 0 ? 'text-blue-400' : 'text-amber-500'}`}>
                    {wingAdjustment === 0 ? 'Neutral (0)' : wingAdjustment > 0 ? `+${wingAdjustment} clicks (Downforce)` : `${wingAdjustment} clicks (Drag)`}
                  </span>
                </div>
                <input
                  type="range"
                  min="-5"
                  max="5"
                  value={wingAdjustment}
                  onChange={(e) => setWingAdjustment(parseInt(e.target.value))}
                  className="w-full accent-blue-500 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer mt-2"
                />
                <div className="flex justify-between text-[9px] font-mono text-zinc-500 mt-1 uppercase font-bold">
                  <span>Low Drag (-5)</span>
                  <span>Base Setup</span>
                  <span>High Downforce (+5)</span>
                </div>
              </div>

              {/* Simulated Metrics Grid */}
              <div className="grid grid-cols-3 gap-3">
                {/* Top Speed */}
                <div className="bg-zinc-900/40 p-3 rounded-lg border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider">Top Speed</span>
                  <div className="mt-1 flex flex-col font-mono">
                    <span className="text-sm font-black text-white">{simSpeed.toFixed(0)} <span className="text-[9px] text-zinc-400">km/h</span></span>
                    <span className={`text-[9px] font-bold ${wingAdjustment === 0 ? 'text-zinc-500' : wingAdjustment > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                      {wingAdjustment === 0 ? 'No change' : wingAdjustment > 0 ? `-${(wingAdjustment * 1.5).toFixed(1)}` : `+${(wingAdjustment * -1.5).toFixed(1)}`}
                    </span>
                  </div>
                </div>

                {/* Aero Balance */}
                <div className="bg-zinc-900/40 p-3 rounded-lg border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider">S1/S3 Balance</span>
                  <div className="mt-1 flex flex-col font-mono">
                    <span className="text-sm font-black text-white">{simRatio.toFixed(3)}</span>
                    <span className="text-[9px] text-zinc-500 font-bold uppercase">
                      {simRatio > activeDriver.s1_s3_ratio ? 'Wing Down' : simRatio < activeDriver.s1_s3_ratio ? 'Wing Up' : 'Standard'}
                    </span>
                  </div>
                </div>

                {/* Lap Time Delta */}
                <div className="bg-zinc-900/40 p-3 rounded-lg border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[9px] text-zinc-500 font-bold uppercase tracking-wider">Est. Lap Delta</span>
                  <div className="mt-1 flex flex-col font-mono">
                    <span className={`text-sm font-black ${simDelta === 0 ? 'text-zinc-300' : simDelta < 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {simDelta === 0 ? '0.000s' : `${simDelta > 0 ? '+' : ''}${simDelta.toFixed(3)}s`}
                    </span>
                    <span className="text-[9px] text-zinc-500 font-bold uppercase">
                      {simDelta < 0 ? 'Net Gain' : simDelta > 0 ? 'Net Loss' : 'Baseline'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Area Chart of Tradeoff */}
              <div className="flex-grow flex flex-col justify-end mt-2">
                <span className="text-[9px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-2 block">// Setup Sensitivity Tradeoff Curve (Lap Delta)</span>
                <div className="h-[120px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={tradeoffCurveData} margin={{ top: 5, right: 5, bottom: 5, left: -25 }}>
                      <defs>
                        <linearGradient id="colorDelta" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f1f23" vertical={false} />
                      <XAxis 
                        dataKey="clicks" 
                        stroke="#52525b" 
                        tick={{ fontSize: 8, fontFamily: 'monospace' }} 
                        tickFormatter={(val) => val === 0 ? '0' : val > 0 ? `+${val}` : val}
                      />
                      <YAxis 
                        stroke="#52525b" 
                        tick={{ fontSize: 8, fontFamily: 'monospace' }} 
                        tickFormatter={(val) => `${val > 0 ? '+' : ''}${val.toFixed(2)}s`}
                      />
                      <Area type="monotone" dataKey="lapDelta" stroke="#3b82f6" strokeWidth={1.5} fillOpacity={1} fill="url(#colorDelta)" />
                      
                      <ReferenceDot 
                        x={wingAdjustment} 
                        y={simDelta} 
                        r={4.5} 
                        fill={simDelta === 0 ? '#d4d4d8' : simDelta < 0 ? '#10b981' : '#f43f5e'} 
                        stroke="#ffffff" 
                        strokeWidth={1.5} 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full w-full flex items-center justify-center font-mono text-zinc-500 border border-dashed border-zinc-800 rounded-lg p-6 text-center">
              Click a driver on the plot to start simulation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}