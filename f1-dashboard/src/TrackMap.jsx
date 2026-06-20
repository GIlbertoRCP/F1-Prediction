import { useState, useMemo } from 'react';

// Color interpolation helpers
const getSpeedColor = (speed, min, max) => {
  const r = (speed - min) / (max - min || 1);
  let color;
  if (r < 0.5) {
    const t = r * 2;
    // Blue [59, 130, 246] to Indigo/Purple [139, 92, 246]
    color = [
      Math.round(59 + (139 - 59) * t),
      Math.round(130 + (92 - 130) * t),
      Math.round(246 + (246 - 246) * t)
    ];
  } else {
    const t = (r - 0.5) * 2;
    // Purple [139, 92, 246] to Red [239, 68, 68]
    color = [
      Math.round(139 + (239 - 139) * t),
      Math.round(92 + (68 - 92) * t),
      Math.round(246 + (68 - 246) * t)
    ];
  }
  return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
};

const getThrottleColor = (throttle) => {
  const r = throttle / 100;
  // Zinc [63, 63, 70] to Emerald Green [16, 185, 129]
  const color = [
    Math.round(63 + (16 - 63) * r),
    Math.round(63 + (185 - 63) * r),
    Math.round(70 + (129 - 70) * r)
  ];
  return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
};

const getBrakeColor = (brake) => {
  const r = Math.min(Math.max(brake, 0), 1);
  // Zinc [63, 63, 70] to Orange [249, 115, 22]
  const color = [
    Math.round(63 + (249 - 63) * r),
    Math.round(63 + (115 - 63) * r),
    Math.round(70 + (22 - 70) * r)
  ];
  return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
};

const getDeltaColor = (diff) => {
  const limit = 15; // km/h threshold
  const clamped = Math.min(Math.max(diff, -limit), limit);
  const r = (clamped + limit) / (2 * limit); // 0 to 1
  let color;
  if (r < 0.5) {
    const t = r * 2;
    // Gold/Yellow [234, 179, 8] (Driver 2 faster) to Slate [113, 113, 122]
    color = [
      Math.round(234 + (113 - 234) * t),
      Math.round(179 + (113 - 179) * t),
      Math.round(8 + (122 - 8) * t)
    ];
  } else {
    const t = (r - 0.5) * 2;
    // Slate [113, 113, 122] to Neon Blue [59, 130, 246] (Driver 1 faster)
    color = [
      Math.round(113 + (59 - 113) * t),
      Math.round(113 + (130 - 113) * t),
      Math.round(122 + (246 - 122) * t)
    ];
  }
  return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
};

export default function TrackMap({ driver1, driver2, d1Telemetry = [], d2Telemetry = [], syncDistance = null, onPointSelect = null }) {
  const [activeMetric, setActiveMetric] = useState('speed'); // speed, throttle, brake
  const [activeMode, setActiveMode] = useState('delta'); // driver1, driver2, delta
  const [hoveredPoint, setHoveredPoint] = useState(null);

  // 1. Process coordinates to fit in SVG
  const { points, bounds, speedRange } = useMemo(() => {
    const hasD1 = d1Telemetry && d1Telemetry.length > 0;
    const hasD2 = d2Telemetry && d2Telemetry.length > 0;
    
    // Choose trace for coordinate outline mapping
    const baseTrace = hasD1 ? d1Telemetry : d2Telemetry;
    if (baseTrace.length === 0) return { points: [], bounds: null, speedRange: { min: 0, max: 0 } };

    const xCoords = baseTrace.map(t => t.x);
    const yCoords = baseTrace.map(t => t.y);

    const minX = Math.min(...xCoords);
    const maxX = Math.max(...xCoords);
    const minY = Math.min(...yCoords);
    const maxY = Math.max(...yCoords);

    const dx = maxX - minX || 1;
    const dy = maxY - minY || 1;

    // Center in 420x420 window (inside 500x500 svg)
    const maxD = Math.max(dx, dy);
    const scale = 420 / maxD;

    // Find speed bounds for scaling color gradients
    const allSpeeds = [...d1Telemetry.map(t => t.speed), ...d2Telemetry.map(t => t.speed)].filter(s => !isNaN(s));
    const minSpeed = allSpeeds.length > 0 ? Math.min(...allSpeeds) : 50;
    const maxSpeed = allSpeeds.length > 0 ? Math.max(...allSpeeds) : 340;

    const scaledPoints = baseTrace.map((t, idx) => {
      // Find matching point on Driver 2's telemetry by matching closest distance
      let d2Point = null;
      if (hasD1 && hasD2) {
        let closest = d2Telemetry[0];
        let minDiff = Math.abs(closest.distance - t.distance);
        for (let i = 1; i < d2Telemetry.length; i++) {
          const diff = Math.abs(d2Telemetry[i].distance - t.distance);
          if (diff < minDiff) {
            minDiff = diff;
            closest = d2Telemetry[i];
          }
        }
        d2Point = closest;
      }

      // Coordinates mapping
      const scaledX = 40 + (t.x - minX) * scale + (420 - dx * scale) / 2;
      // Invert Y axis so north is north
      const scaledY = 40 + (maxY - t.y) * scale + (420 - dy * scale) / 2;

      return {
        ...t,
        d2Point,
        scaledX,
        scaledY,
        index: idx
      };
    });

    return {
      points: scaledPoints,
      bounds: { minX, maxX, minY, maxY },
      speedRange: { min: minSpeed, max: maxSpeed }
    };
  }, [d1Telemetry, d2Telemetry]);

  // Compute syncPoint as closest coordinate point to syncDistance
  const syncPoint = useMemo(() => {
    if (syncDistance === null || points.length === 0) return null;
    let closest = points[0];
    let minDiff = Math.abs(closest.distance - syncDistance);
    for (let i = 1; i < points.length; i++) {
      const diff = Math.abs(points[i].distance - syncDistance);
      if (diff < minDiff) {
        minDiff = diff;
        closest = points[i];
      }
    }
    return closest;
  }, [points, syncDistance]);

  // 2. Build colored segments
  const segments = useMemo(() => {
    if (points.length < 2) return [];
    
    const list = [];
    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      let val = 0;
      let color = '#71717a'; // Default slate

      if (activeMode === 'driver1') {
        if (activeMetric === 'speed') {
          color = getSpeedColor(p1.speed, speedRange.min, speedRange.max);
          val = p1.speed;
        } else if (activeMetric === 'throttle') {
          color = getThrottleColor(p1.throttle);
          val = p1.throttle;
        } else if (activeMetric === 'brake') {
          color = getBrakeColor(p1.brake);
          val = p1.brake;
        }
      } else if (activeMode === 'driver2' && p1.d2Point) {
        const d2 = p1.d2Point;
        if (activeMetric === 'speed') {
          color = getSpeedColor(d2.speed, speedRange.min, speedRange.max);
          val = d2.speed;
        } else if (activeMetric === 'throttle') {
          color = getThrottleColor(d2.throttle);
          val = d2.throttle;
        } else if (activeMetric === 'brake') {
          color = getBrakeColor(d2.brake);
          val = d2.brake;
        }
      } else if (activeMode === 'delta') {
        const speedD1 = p1.speed;
        const speedD2 = p1.d2Point ? p1.d2Point.speed : p1.speed;
        const diff = speedD1 - speedD2;
        color = getDeltaColor(diff);
        val = diff;
      }

      list.push({
        x1: p1.scaledX,
        y1: p1.scaledY,
        x2: p2.scaledX,
        y2: p2.scaledY,
        color,
        val,
        originalPoint: p1
      });
    }
    return list;
  }, [points, activeMetric, activeMode, speedRange]);

  // 3. Euclidean distance hover snap logic
  const handleMouseMove = (e) => {
    if (points.length === 0) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * 500;
    const mouseY = ((e.clientY - rect.top) / rect.height) * 500;

    let closestPt = null;
    let minDistance = Infinity;

    points.forEach((pt) => {
      const dist = Math.pow(pt.scaledX - mouseX, 2) + Math.pow(pt.scaledY - mouseY, 2);
      if (dist < minDistance) {
        minDistance = dist;
        closestPt = pt;
      }
    });

    // Hover snap sensitivity radius threshold (within 40px)
    if (minDistance < 1600) {
      setHoveredPoint(closestPt);
    } else {
      setHoveredPoint(null);
    }
  };

  const handleMouseLeave = () => {
    setHoveredPoint(null);
  };

  if (points.length === 0) {
    return null;
  }

  // Hovered metrics details
  const d1Speed = hoveredPoint ? hoveredPoint.speed : 0;
  const d1Throttle = hoveredPoint ? hoveredPoint.throttle : 0;
  const d1Brake = hoveredPoint ? hoveredPoint.brake : 0;
  const d1Gear = hoveredPoint ? hoveredPoint.gear : 0;

  const d2Speed = hoveredPoint && hoveredPoint.d2Point ? hoveredPoint.d2Point.speed : 0;
  const d2Throttle = hoveredPoint && hoveredPoint.d2Point ? hoveredPoint.d2Point.throttle : 0;
  const d2Brake = hoveredPoint && hoveredPoint.d2Point ? hoveredPoint.d2Point.brake : 0;
  const d2Gear = hoveredPoint && hoveredPoint.d2Point ? hoveredPoint.d2Point.gear : 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-lg p-6 shadow-2xl mt-8">
      {/* HEADER CONTROLS */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6 border-b border-zinc-800 pb-4">
        <div>
          <h2 className="font-orbitron text-lg font-black uppercase tracking-wide border-l-4 border-emerald-500 pl-3 text-white flex items-center gap-2">
            Spatial Track Telemetry Map
          </h2>
          <p className="text-[10px] font-mono text-zinc-500 pl-4 mt-0.5">2D POSITION OVERLAY | SHAPING TELEMETRY ACROSS CORNERS</p>
        </div>
        
        <div className="flex flex-wrap gap-3 font-mono text-[10px] font-bold">
          {/* COMPARISON MODES */}
          <div className="flex bg-zinc-950 border border-zinc-800/80 p-0.5 rounded-lg">
            <button
              onClick={() => setActiveMode('driver1')}
              className={`px-3 py-1.5 rounded transition-all ${activeMode === 'driver1' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-white'}`}
            >
              {driver1 || 'Driver 1'}
            </button>
            <button
              onClick={() => setActiveMode('driver2')}
              className={`px-3 py-1.5 rounded transition-all ${activeMode === 'driver2' ? 'bg-yellow-500 text-white shadow' : 'text-zinc-400 hover:text-white'}`}
            >
              {driver2 || 'Driver 2'}
            </button>
            <button
              onClick={() => setActiveMode('delta')}
              className={`px-3 py-1.5 rounded transition-all ${activeMode === 'delta' ? 'bg-purple-600 text-white shadow' : 'text-zinc-400 hover:text-white'}`}
            >
              Speed Delta
            </button>
          </div>

          {/* TELEMETRY METRICS */}
          {activeMode !== 'delta' && (
            <div className="flex bg-zinc-950 border border-zinc-800/80 p-0.5 rounded-lg">
              {['speed', 'throttle', 'brake'].map((m) => (
                <button
                  key={m}
                  onClick={() => setActiveMetric(m)}
                  className={`px-3 py-1.5 rounded transition-all capitalize ${activeMetric === m ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* INTERACTIVE TRACK PLOT (7 COLS) */}
        <div className="lg:col-span-7 flex justify-center items-center bg-zinc-950/60 rounded-xl border border-zinc-800/80 p-4 relative overflow-hidden h-[420px] sm:h-[480px]">
          {/* Ambient Glows */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />

          <svg
            viewBox="0 0 500 500"
            className="w-full h-full cursor-crosshair max-w-[440px] select-none"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            onClick={() => {
              if (hoveredPoint && onPointSelect) {
                onPointSelect(hoveredPoint.distance);
              }
            }}
          >
            {/* Outline Underlayer path for glow */}
            <path
              d={segments.map((seg, idx) => `${idx === 0 ? 'M' : 'L'} ${seg.x1} ${seg.y1}`).join(' ')}
              fill="none"
              stroke="#ffffff"
              strokeWidth={3}
              className="opacity-5 blur-sm"
            />

            {/* Colored segments */}
            {segments.map((seg, idx) => (
              <line
                key={idx}
                x1={seg.x1}
                y1={seg.y1}
                x2={seg.x2}
                y2={seg.y2}
                stroke={seg.color}
                strokeWidth={hoveredPoint && Math.abs(hoveredPoint.index - idx) < 3 ? 6 : 3}
                strokeLinecap="round"
                className="transition-all duration-150"
              />
            ))}

            {/* Hover Dot Snap Overlay */}
            {hoveredPoint && (
              <>
                {/* Glowing ring */}
                <circle
                  cx={hoveredPoint.scaledX}
                  cy={hoveredPoint.scaledY}
                  r={10}
                  fill="transparent"
                  stroke={activeMode === 'delta' ? getDeltaColor(hoveredPoint.speed - (hoveredPoint.d2Point?.speed || 0)) : (activeMode === 'driver1' ? '#3b82f6' : '#eab308')}
                  strokeWidth={2}
                  className="animate-ping"
                />
                {/* Center dot */}
                <circle
                  cx={hoveredPoint.scaledX}
                  cy={hoveredPoint.scaledY}
                  r={5}
                  fill={activeMode === 'delta' ? getDeltaColor(hoveredPoint.speed - (hoveredPoint.d2Point?.speed || 0)) : (activeMode === 'driver1' ? '#3b82f6' : '#eab308')}
                  stroke="#ffffff"
                  strokeWidth={1.5}
                />
              </>
            )}

            {/* Sync Dot Overlay */}
            {syncPoint && (
              <>
                {/* Glowing ring */}
                <circle
                  cx={syncPoint.scaledX}
                  cy={syncPoint.scaledY}
                  r={12}
                  fill="transparent"
                  stroke="#10b981"
                  strokeWidth={2}
                  className="animate-pulse"
                />
                {/* Center dot */}
                <circle
                  cx={syncPoint.scaledX}
                  cy={syncPoint.scaledY}
                  r={6}
                  fill="#10b981"
                  stroke="#ffffff"
                  strokeWidth={1.5}
                />
              </>
            )}
          </svg>
        </div>

        {/* DETAILS/LEGEND CORNER (5 COLS) */}
        <div className="lg:col-span-5 flex flex-col gap-6 justify-between self-stretch">
          {/* DYNAMIC TELEMETRY POPUP */}
          <div className="bg-zinc-950/80 rounded-xl p-5 border border-zinc-800/80 flex-grow flex flex-col justify-between shadow-inner">
            <h3 className="font-mono text-zinc-500 font-bold uppercase tracking-wider text-[10px] mb-4">// Positional Metric Inspector</h3>
            
            {hoveredPoint ? (
              <div className="flex flex-col gap-4 font-mono">
                {/* Lap Distance Location */}
                <div className="flex justify-between items-center text-xs pb-3 border-b border-zinc-800/60">
                  <span className="text-zinc-500">Track Location:</span>
                  <span className="text-white font-bold">{hoveredPoint.distance.toFixed(0)}m / {points[points.length - 1].distance.toFixed(0)}m</span>
                </div>

                {/* Driver 1 Stats */}
                <div className="flex flex-col gap-2 p-3 bg-blue-950/20 border border-blue-900/30 rounded-lg">
                  <div className="font-orbitron font-bold text-xs text-blue-400 flex justify-between items-center">
                    <span>{driver1 || 'Driver 1'}</span>
                    <span className="text-[10px] font-mono text-zinc-400 font-bold">Gear {d1Gear}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">SPEED</div>
                      <div className="font-bold text-white">{d1Speed.toFixed(0)} <span className="text-[9px] text-zinc-400">km/h</span></div>
                    </div>
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">THROTTLE</div>
                      <div className="font-bold text-emerald-400">{d1Throttle.toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">BRAKE</div>
                      <div className={`font-bold ${d1Brake > 0.1 ? 'text-red-500' : 'text-zinc-500'}`}>{d1Brake > 0.1 ? 'ACTIVE' : 'OFF'}</div>
                    </div>
                  </div>
                </div>

                {/* Driver 2 Stats */}
                <div className="flex flex-col gap-2 p-3 bg-yellow-950/15 border border-yellow-900/30 rounded-lg">
                  <div className="font-orbitron font-bold text-xs text-yellow-500 flex justify-between items-center">
                    <span>{driver2 || 'Driver 2'}</span>
                    <span className="text-[10px] font-mono text-zinc-400 font-bold">Gear {d2Gear}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">SPEED</div>
                      <div className="font-bold text-white">{d2Speed.toFixed(0)} <span className="text-[9px] text-zinc-400">km/h</span></div>
                    </div>
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">THROTTLE</div>
                      <div className="font-bold text-emerald-400">{d2Throttle.toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-zinc-500 mb-0.5">BRAKE</div>
                      <div className={`font-bold ${d2Brake > 0.1 ? 'text-red-500' : 'text-zinc-500'}`}>{d2Brake > 0.1 ? 'ACTIVE' : 'OFF'}</div>
                    </div>
                  </div>
                </div>

                {/* Comparison Delta */}
                <div className="mt-2 p-3 bg-zinc-900/60 border border-zinc-800/80 rounded-lg flex items-center justify-between text-xs">
                  <span className="text-zinc-400 font-semibold">Speed Delta:</span>
                  {d1Speed - d2Speed > 0 ? (
                    <span className="text-blue-400 font-bold">▲ +{(d1Speed - d2Speed).toFixed(1)} km/h ({driver1})</span>
                  ) : d1Speed - d2Speed < 0 ? (
                    <span className="text-yellow-500 font-bold">▼ {(d1Speed - d2Speed).toFixed(1)} km/h ({driver2})</span>
                  ) : (
                    <span className="text-zinc-500 font-bold">EQUAL</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-grow flex flex-col items-center justify-center text-center font-mono text-zinc-500 border border-dashed border-zinc-800 rounded-lg p-6">
                <span className="text-[10px] text-zinc-500 font-bold tracking-wider uppercase mb-2">Select Apex</span>
                <span className="text-[10px] uppercase tracking-widest leading-relaxed">Hover or click any corner of the 2D circuit map to sync telemetry lines</span>
              </div>
            )}
          </div>

          {/* DYNAMIC METRIC LEGEND */}
          <div className="bg-zinc-950/80 rounded-xl p-5 border border-zinc-800/80 font-mono text-xs flex flex-col gap-3">
            <h4 className="text-zinc-500 font-bold uppercase tracking-wider text-[10px]">// Map Legend</h4>
            
            {activeMode === 'delta' ? (
              <div className="flex flex-col gap-2">
                <div className="flex justify-between items-center text-[10px] text-zinc-400 font-bold">
                  <span>{driver2 || 'Driver 2'} Faster</span>
                  <span>Equal</span>
                  <span>{driver1 || 'Driver 1'} Faster</span>
                </div>
                <div className="h-3 w-full rounded bg-gradient-to-r from-yellow-500 via-zinc-500 to-blue-500 shadow-inner" />
                <p className="text-[9px] text-zinc-500 leading-normal mt-1">
                  Colors show local qualifying speed difference. Yellow/Gold means {driver2} is faster, Blue means {driver1} is faster. Grey indicates within ±1 km/h.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {activeMetric === 'speed' && (
                  <>
                    <div className="flex justify-between items-center text-[10px] text-zinc-400 font-bold">
                      <span>Slow ({speedRange.min.toFixed(0)} km/h)</span>
                      <span>Mid</span>
                      <span>Fast ({speedRange.max.toFixed(0)} km/h)</span>
                    </div>
                    <div className="h-3 w-full rounded bg-gradient-to-r from-blue-500 via-purple-500 to-red-500 shadow-inner" />
                  </>
                )}
                {activeMetric === 'throttle' && (
                  <>
                    <div className="flex justify-between items-center text-[10px] text-zinc-400 font-bold">
                      <span>Off (0%)</span>
                      <span>Part Throttle</span>
                      <span>Full (100%)</span>
                    </div>
                    <div className="h-3 w-full rounded bg-gradient-to-r from-zinc-700 to-emerald-500 shadow-inner" />
                  </>
                )}
                {activeMetric === 'brake' && (
                  <>
                    <div className="flex justify-between items-center text-[10px] text-zinc-400 font-bold">
                      <span>Off (0%)</span>
                      <span>Braking</span>
                    </div>
                    <div className="h-3 w-full rounded bg-gradient-to-r from-zinc-700 to-orange-500 shadow-inner" />
                  </>
                )}
                <p className="text-[9px] text-zinc-500 leading-normal mt-1">
                  Track segments are colored by driver metric intensity. Darker zones represent off-pedal / slow speed zones.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
