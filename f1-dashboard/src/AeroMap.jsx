import { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

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
      <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-lg shadow-xl font-mono text-sm w-48">
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

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/api/aero/${year}/${gp}`)
      .then(res => res.json())
      .then(data => {
        // FIX: Check if the backend sent an error message
        if (data.detail || !data.aero_data) {
          console.error("Aero API Error:", data.detail);
          setAeroData([]); // Fallback to an empty array to prevent crashing
        } else {
          setAeroData(data.aero_data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch aero map", err);
        setAeroData([]);
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

  // FIX: If the data failed to load entirely, show a clean error instead of crashing
  // 1. First, check if the API failed or returned empty
  if (!aeroData || aeroData.length === 0) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-red-500 bg-red-950/20 border border-red-900 rounded-lg">
        TELEMETRY UNAVAILABLE FOR AERO MAP
      </div>
    );
  }

  // 2. THE FIX: Aggressively filter out any drivers with NaN or null speeds
  const validData = aeroData.filter(d => 
    d && 
    typeof d.s1_s3_ratio === 'number' && !isNaN(d.s1_s3_ratio) && 
    typeof d.max_speed === 'number' && !isNaN(d.max_speed)
  );

  // 3. Check if we have any drivers left after filtering!
  if (validData.length === 0) {
    return (
      <div className="h-64 mt-8 flex items-center justify-center font-mono text-red-500 bg-red-950/20 border border-red-900 rounded-lg">
        TELEMETRY CORRUPTED (NaN VALUES DETECTED)
      </div>
    );
  }

  // 4. Safely calculate domains ONLY using the valid data
  const minX = Math.min(...validData.map(d => d.s1_s3_ratio)) - 0.05;
  const maxX = Math.max(...validData.map(d => d.s1_s3_ratio)) + 0.05;
  const minY = Math.floor(Math.min(...validData.map(d => d.max_speed)) - 3);
  const maxY = Math.ceil(Math.max(...validData.map(d => d.max_speed)) + 3);

  return (
    <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg shadow-2xl mt-8">
      <h2 className="text-xl font-bold mb-1 uppercase tracking-wide border-l-4 border-blue-500 pl-3 text-white">
        Aero Setup Configuration
      </h2>
      <p className="text-xs font-mono text-zinc-500 mb-6 pl-4">QUALIFYING FASTEST LAP | CORNERING GRIP VS STRAIGHT LINE DRAG</p>
      
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
              label={{ value: "HIGH DOWNFORCE / HIGH DRAG                                     LOW DOWNFORCE / HIGH TOP SPEED", position: "bottom", fill: "#52525b", fontSize: 12 }} 
            />
            
            <YAxis 
              type="number" 
              dataKey="max_speed" 
              name="Top Speed" 
              domain={[minY, maxY]} 
              stroke="#a1a1aa"
              label={{ value: "Top Speed (km/h)", angle: -90, position: "insideLeft", fill: "#52525b", fontSize: 12 }} 
            />
            
            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#3f3f46' }} />
            
            {/* Make sure we map over validData, not the raw aeroData */}
            <Scatter name="Drivers" data={validData}>
              {validData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={teamColors[entry.team] || "#ffffff"} stroke="#000" strokeWidth={1} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}